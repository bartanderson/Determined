"""
Tests for LanguageWalker wire-in: persist_all → functions + graph_edges for JS/TS files.
Uses an in-memory SQLite DB and a temp directory with two JS files.
"""

import sqlite3
import tempfile
import textwrap
from pathlib import Path

import pytest

from determined.persistence.persistence_engine import persist_all, ensure_schema


# ---------------------------------------------------------------------------
# Fixture: minimal in-memory DB + temp project with two JS files
# ---------------------------------------------------------------------------

JS_A = textwrap.dedent("""\
    function buildDungeon(config) {
        return generateRooms(config.size);
    }
    function generateRooms(n) {
        return [];
    }
""")

JS_B = textwrap.dedent("""\
    const controller = {
        run: function() {
            buildDungeon({ size: 10 });
        }
    };
""")


@pytest.fixture()
def js_project(tmp_path):
    (tmp_path / "dungeon.js").write_text(JS_A, encoding="utf-8")
    (tmp_path / "controller.js").write_text(JS_B, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def db_with_js(js_project):
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    # persist_all needs file_analyses and graph; pass empty stubs
    class _EmptyGraph:
        edges = []
    persist_all(
        connection=conn,
        file_analyses=[],
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(js_project),
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Tests: functions table
# ---------------------------------------------------------------------------

def test_js_symbols_in_functions(db_with_js):
    rows = db_with_js.execute("SELECT name FROM functions").fetchall()
    names = {r[0] for r in rows}
    assert "dungeon.buildDungeon" in names
    assert "dungeon.generateRooms" in names


def test_js_object_method_in_functions(db_with_js):
    rows = db_with_js.execute("SELECT name FROM functions").fetchall()
    names = {r[0] for r in rows}
    assert "controller.run" in names


def test_js_file_path_stored(db_with_js, js_project):
    rows = db_with_js.execute(
        "SELECT file_path FROM functions WHERE name = 'dungeon.buildDungeon'"
    ).fetchall()
    assert len(rows) == 1
    assert "dungeon.js" in rows[0][0]


# ---------------------------------------------------------------------------
# Tests: graph_edges table
# ---------------------------------------------------------------------------

def test_js_call_edge_stored(db_with_js):
    rows = db_with_js.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type = 'static'"
    ).fetchall()
    pairs = {(r[0], r[1]) for r in rows}
    # dungeon.buildDungeon calls generateRooms (callee upgraded to qualified name after resolution)
    assert ("dungeon.buildDungeon", "dungeon.generateRooms") in pairs


def test_js_cross_file_call_edge(db_with_js):
    rows = db_with_js.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type = 'static'"
    ).fetchall()
    pairs = {(r[0], r[1]) for r in rows}
    # controller.run calls buildDungeon (callee upgraded to qualified name after resolution)
    assert ("controller.run", "dungeon.buildDungeon") in pairs


# ---------------------------------------------------------------------------
# Tests: RM62 - resolution post-pass writes back qualified callee name
# ---------------------------------------------------------------------------

def test_cross_file_callee_upgraded_to_qualified_name(db_with_js):
    """After the resolution post-pass, bare callees are upgraded to the qualified FQDN.
    controller.run -> 'buildDungeon' (bare) must become 'dungeon.buildDungeon' (qualified)."""
    rows = db_with_js.execute(
        "SELECT callee, resolved FROM graph_edges WHERE caller = 'controller.run'"
    ).fetchall()
    assert rows, "No edges from controller.run found"
    callee, resolved = rows[0]
    assert callee == "dungeon.buildDungeon", f"Expected qualified callee, got '{callee}'"
    assert resolved == 1


def test_same_file_callee_upgraded_to_qualified_name(db_with_js):
    """Within-file callees are also upgraded: buildDungeon -> generateRooms (bare)
    becomes dungeon.generateRooms (qualified)."""
    rows = db_with_js.execute(
        "SELECT callee FROM graph_edges WHERE caller = 'dungeon.buildDungeon'"
    ).fetchall()
    assert rows, "No edges from dungeon.buildDungeon found"
    assert rows[0][0] == "dungeon.generateRooms", f"Expected qualified callee, got '{rows[0][0]}'"


# ---------------------------------------------------------------------------
# Tests: re-ingest idempotency
# ---------------------------------------------------------------------------

def test_reingest_does_not_duplicate(db_with_js, js_project):
    class _EmptyGraph:
        edges = []
    # Run persist_all a second time
    persist_all(
        connection=db_with_js,
        file_analyses=[],
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(js_project),
    )
    db_with_js.commit()
    # Symbol count should be the same (scoped delete + re-insert)
    rows = db_with_js.execute(
        "SELECT COUNT(*) FROM functions WHERE name LIKE 'dungeon.%'"
    ).fetchone()[0]
    assert rows == 2  # buildDungeon + generateRooms, not 4


# ---------------------------------------------------------------------------
# Tests: C header stub dedup post-pass
# ---------------------------------------------------------------------------

C_HEADER = """\
int movePlayer(int dx, int dy);
int unimplementedFn(void);
"""

C_IMPL = """\
int movePlayer(int dx, int dy) {
    return dx + dy;
}
"""


@pytest.fixture()
def c_project(tmp_path):
    (tmp_path / "game.h").write_text(C_HEADER, encoding="utf-8")
    (tmp_path / "game.c").write_text(C_IMPL, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def db_with_c(c_project):
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    class _EmptyGraph:
        edges = []
    persist_all(
        connection=conn,
        file_analyses=[],
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(c_project),
    )
    conn.commit()
    return conn


def test_c_header_dedup_removes_matched_declaration(db_with_c):
    """Header declarations with a .c implementation must be deduplicated."""
    rows = db_with_c.execute(
        "SELECT name, is_stub FROM functions ORDER BY name"
    ).fetchall()
    by_name = {r[0]: r[1] for r in rows}
    # game::movePlayer should exist once (from game.c, is_stub=0)
    matching = [n for n in by_name if "movePlayer" in n]
    assert len(matching) == 1, f"Expected 1 movePlayer, got {matching}"
    assert by_name[matching[0]] == 0, "movePlayer should not be a stub"


def test_c_header_dedup_keeps_true_stubs(db_with_c):
    """Header declarations with no .c implementation are kept as stubs."""
    rows = db_with_c.execute(
        "SELECT name, is_stub FROM functions ORDER BY name"
    ).fetchall()
    by_name = {r[0]: r[1] for r in rows}
    matching = [n for n in by_name if "unimplementedFn" in n]
    assert len(matching) == 1, f"Expected 1 unimplementedFn, got {matching}"
    assert by_name[matching[0]] == 1, "unimplementedFn should remain a stub"


def test_c_total_symbol_count_after_dedup(db_with_c):
    """After dedup: 1 .c impl (movePlayer) + 1 true stub (unimplementedFn) = 2 total."""
    count = db_with_c.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# Tests: CUDA persist — .cu symbols appear in functions, kernel launches as edges
# ---------------------------------------------------------------------------

CUDA_KERN = """\
__global__ void layernorm_kernel(float* out, const float* inp, int N) {
    int i = blockIdx.x;
    out[i] = scale(inp[i]);
}

__device__ float scale(float x) {
    return x * 2.0f;
}

void launch_layernorm(float* out, const float* inp, int N) {
    layernorm_kernel<<<N, 256>>>(out, inp, N);
}
"""


@pytest.fixture()
def cuda_project(tmp_path):
    (tmp_path / "layernorm.cu").write_text(CUDA_KERN, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def db_with_cuda(cuda_project):
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    class _EmptyGraph:
        edges = []
    persist_all(
        connection=conn,
        file_analyses=[],
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(cuda_project),
    )
    conn.commit()
    return conn


def test_cuda_global_kernel_in_functions(db_with_cuda):
    rows = db_with_cuda.execute("SELECT name FROM functions").fetchall()
    names = {r[0] for r in rows}
    assert "layernorm::layernorm_kernel" in names


def test_cuda_device_fn_in_functions(db_with_cuda):
    rows = db_with_cuda.execute("SELECT name FROM functions").fetchall()
    names = {r[0] for r in rows}
    assert "layernorm::scale" in names


def test_cuda_global_marked_as_tool(db_with_cuda):
    row = db_with_cuda.execute(
        "SELECT is_tool FROM functions WHERE name = 'layernorm::layernorm_kernel'"
    ).fetchone()
    assert row is not None and row[0] == 1


def test_cuda_kernel_launch_edge_stored(db_with_cuda):
    rows = db_with_cuda.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type = 'static'"
    ).fetchall()
    pairs = {(r[0], r[1]) for r in rows}
    # Callee is upgraded to qualified FQN by the cross-file resolution post-pass
    assert ("layernorm::launch_layernorm", "layernorm::layernorm_kernel") in pairs


# ---------------------------------------------------------------------------
# Tests: ctypes linker — Python → C cross-language edges
# ---------------------------------------------------------------------------

CTYPES_PY = """\
import ctypes

lib = ctypes.CDLL("./libgame.so")

def run_physics(dt):
    lib.physics_step(dt)
    lib.collide_all()
"""

C_IMPL_FOR_CTYPES = """\
void physics_step(float dt) { }
void collide_all(void) { }
"""


@pytest.fixture()
def ctypes_project(tmp_path):
    (tmp_path / "physics.py").write_text(CTYPES_PY, encoding="utf-8")
    (tmp_path / "physics.c").write_text(C_IMPL_FOR_CTYPES, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def db_with_ctypes(ctypes_project):
    import sys
    sys.path.insert(0, str(ctypes_project))
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    from determined.ingestion.scan_project_files import scan_project_files
    file_analyses = list(scan_project_files(
        project_root=str(ctypes_project),
        project_prefixes=[],
        repo_root=str(ctypes_project),
    ))
    class _EmptyGraph:
        edges = []
    persist_all(
        connection=conn,
        file_analyses=file_analyses,
        graph=_EmptyGraph(),
        project_prefixes=[],
        project_root=str(ctypes_project),
    )
    conn.commit()
    return conn


def test_ctypes_call_edges_emitted(db_with_ctypes):
    rows = db_with_ctypes.execute(
        "SELECT caller, callee, edge_type FROM graph_edges WHERE edge_type = 'ctypes_call'"
    ).fetchall()
    callees = {r[1] for r in rows}
    assert "physics_step" in callees
    assert "collide_all" in callees


def test_ctypes_caller_is_python_fn(db_with_ctypes):
    rows = db_with_ctypes.execute(
        "SELECT caller FROM graph_edges WHERE edge_type = 'ctypes_call' AND callee = 'physics_step'"
    ).fetchall()
    assert rows, "No ctypes_call edge to physics_step"
    assert "run_physics" in rows[0][0]
