"""
Tests for Level-4 edge tools: edges_of, edge_detail, list_import_deps.

Uses the harrow corpus DB when available; skips gracefully if not found.
"""
import os
import pytest

HARROW_DB = "C_Users_bartl_dev_harrow.db"
DETERMINED_DB = "C_Users_bartl_dev_Determined.db"


def _find_db():
    """Return path to an available corpus DB, or None."""
    for db in [HARROW_DB, DETERMINED_DB]:
        if os.path.exists(db):
            return db
    return None


@pytest.fixture
def oracle():
    db = _find_db()
    if not db:
        pytest.skip("No corpus DB available (run ingestion first)")
    from determined.oracle.db_oracle import DBOracle
    return DBOracle(db)


# ---------------------------------------------------------------------------
# Module resolution
# ---------------------------------------------------------------------------

def test_resolve_internal_module(oracle):
    from determined.agent.edge_tools import _resolve_module_to_file
    db = _find_db()
    if "harrow" in db:
        # harrow.engine should resolve to engine/__init__.py or engine/*.py
        result = _resolve_module_to_file(oracle, "harrow.engine")
        assert result is not None, "harrow.engine should resolve to a project file"
        assert result.endswith(".py")
    else:
        # For Determined corpus
        result = _resolve_module_to_file(oracle, "determined.oracle")
        assert result is not None, "determined.oracle should resolve"
        assert result.endswith(".py")


def test_resolve_external_module_returns_none(oracle):
    from determined.agent.edge_tools import _resolve_module_to_file
    # stdlib modules should not resolve to corpus files
    result = _resolve_module_to_file(oracle, "os")
    assert result is None
    result = _resolve_module_to_file(oracle, "sqlite3")
    assert result is None


# ---------------------------------------------------------------------------
# list_import_deps
# ---------------------------------------------------------------------------

def _text(result) -> str:
    """Unpack (text, items) or plain string from a tool return."""
    return result[0] if isinstance(result, tuple) else result


def test_list_import_deps_whole_corpus(oracle):
    from determined.agent.edge_tools import list_import_deps
    result = _text(list_import_deps(oracle, {}))
    assert "ERROR" not in result
    assert "import" in result.lower() or "edge" in result.lower()


def test_list_import_deps_scoped_to_file(oracle):
    from determined.agent.edge_tools import list_import_deps
    result = _text(list_import_deps(oracle, {"file_path": "this_file_does_not_exist.py"}))
    assert "No imports found" in result or "ERROR" not in result


def test_list_import_deps_labels_internal_and_external(oracle):
    from determined.agent.edge_tools import list_import_deps
    result = _text(list_import_deps(oracle, {}))
    if "No project-internal" in result:
        pytest.skip("Corpus has no internal import edges")
    assert "→" in result


def test_list_import_deps_returns_edge_items(oracle):
    from determined.agent.edge_tools import list_import_deps
    from determined.agent.edge_types import EdgeRef
    text, items = list_import_deps(oracle, {})
    if "No project-internal" in text:
        pytest.skip("Corpus has no internal import edges")
    assert len(items) > 0
    assert all(isinstance(e, EdgeRef) for e in items)
    assert all(e.edge_type == "import" for e in items)


# ---------------------------------------------------------------------------
# edges_of
# ---------------------------------------------------------------------------

def test_edges_of_file_returns_imports(oracle):
    from determined.agent.edge_tools import edges_of, list_import_deps
    deps_text = _text(list_import_deps(oracle, {}))
    if "No project-internal" in deps_text:
        pytest.skip("No internal import edges available")
    first_arrow = [line for line in deps_text.splitlines() if "→" in line]
    assert first_arrow, "Expected import edge lines"
    src = first_arrow[0].split("→")[0].strip()
    if not src:
        pytest.skip("Could not extract source file name")
    basename = src.split("/")[-1]
    result = _text(edges_of(oracle, {"name": basename, "type": "import"}))
    assert "ERROR" not in result
    assert "imports" in result.lower() or "no edges" in result.lower()


def test_edges_of_empty_name_returns_error(oracle):
    from determined.agent.edge_tools import edges_of
    result = _text(edges_of(oracle, {"name": ""}))
    assert "ERROR" in result


def test_edges_of_unknown_name_returns_no_edges(oracle):
    from determined.agent.edge_tools import edges_of
    result = _text(edges_of(oracle, {"name": "TOTALLY_UNKNOWN_SYMBOL_XYZ_123"}))
    assert "no edges found" in result.lower() or "ERROR" not in result


def test_edges_of_returns_edge_items(oracle):
    from determined.agent.edge_tools import edges_of
    from determined.agent.edge_types import EdgeRef
    # Find a real caller from graph_edges
    row = oracle.conn.execute(
        "SELECT DISTINCT caller FROM graph_edges WHERE caller NOT LIKE '%.__init__%' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("No call edges in corpus")
    text, items = edges_of(oracle, {"name": row[0], "type": "call", "direction": "out"})
    # May be empty if no callees, but items should be EdgeRef if present
    assert all(isinstance(e, EdgeRef) for e in items)


# ---------------------------------------------------------------------------
# edge_detail
# ---------------------------------------------------------------------------

def test_edge_detail_requires_src_and_dst(oracle):
    from determined.agent.edge_tools import edge_detail
    result = edge_detail(oracle, {"src": "foo"})
    assert "ERROR" in result


def test_edge_detail_no_connection_is_graceful(oracle):
    from determined.agent.edge_tools import edge_detail
    result = edge_detail(oracle, {"src": "UNKNOWN_A_XYZ", "dst": "UNKNOWN_B_XYZ"})
    assert "ERROR" not in result
    assert "no direct edge" in result.lower()


# ---------------------------------------------------------------------------
# EdgeRef dataclass
# ---------------------------------------------------------------------------

def test_edge_ref_key_is_stable():
    from determined.agent.edge_types import EdgeRef
    e = EdgeRef(src="foo", src_type="symbol", dst="bar", dst_type="symbol", edge_type="call")
    assert e.key() == "call::foo::bar"
    assert e.label() == "foo calls bar"
    d = e.to_dict()
    assert d["src"] == "foo"
    assert d["edge_type"] == "call"
    assert d["is_internal"] is True


def test_edge_ref_label_for_import():
    from determined.agent.edge_types import EdgeRef
    e = EdgeRef(src="a.py", src_type="file", dst="b.py", dst_type="file", edge_type="import")
    assert "imports" in e.label()


# ---------------------------------------------------------------------------
# TOOLS dict registration
# ---------------------------------------------------------------------------

def test_edge_tools_are_in_tools_dict():
    from determined.agent.agent_tools import TOOLS
    for name in ("edges_of", "edge_detail", "list_import_deps", "add_edge"):
        assert name in TOOLS, f"'{name}' missing from TOOLS dict"


def test_edge_tools_are_in_registry():
    from determined.agent.tool_registry import REGISTRY
    for name in ("edges_of", "edge_detail", "list_import_deps", "add_edge"):
        assert name in REGISTRY, f"'{name}' missing from REGISTRY"
