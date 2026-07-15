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
