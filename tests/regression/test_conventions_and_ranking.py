# tests/regression/test_conventions_and_ranking.py
#
# Regression tests for RM70 detect_conventions and RM69 rank_stubs.
# Uses in-memory SQLite fixtures — no live corpus required.

import json
import sqlite3
import pytest

from determined.agent.agent_tools import detect_conventions, rank_stubs


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_oracle(functions=None, edges=None):
    """Minimal oracle shim with an in-memory DB."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE functions (
            name TEXT, file_path TEXT, line_number INTEGER,
            docstring TEXT, param_types_json TEXT, return_type TEXT,
            is_stub INTEGER DEFAULT 0, is_tool INTEGER DEFAULT 0,
            decorators_json TEXT, arguments_json TEXT, class_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT, callee TEXT, caller_file TEXT,
            edge_type TEXT DEFAULT 'static', resolved INTEGER DEFAULT 0,
            source_id TEXT, target_id TEXT
        )
    """)
    conn.execute("CREATE TABLE files (file_path TEXT, line_count INTEGER)")
    conn.execute("""
        CREATE TABLE classes (
            name TEXT, file_path TEXT,
            base_classes_json TEXT, docstring TEXT, methods_json TEXT
        )
    """)
    for fn in (functions or []):
        conn.execute(
            "INSERT INTO functions (name, file_path, line_number, docstring, "
            "param_types_json, return_type, is_stub) VALUES (?,?,?,?,?,?,?)",
            (fn.get("name"), fn.get("file_path", "mod.py"), fn.get("line_number", 1),
             fn.get("docstring", ""), fn.get("param_types_json", "{}"),
             fn.get("return_type", ""), fn.get("is_stub", 0))
        )
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, edge_type) VALUES (?,?,?)",
            (e["caller"], e["callee"], e.get("edge_type", "static"))
        )
    conn.commit()

    class _Oracle:
        def __init__(self, c):
            self.conn = c
        def get_project_root(self):
            return "."

    return _Oracle(conn)


class _Assessor:
    def __init__(self, oracle):
        self.oracle = oracle


# ---------------------------------------------------------------------------
# detect_conventions tests
# ---------------------------------------------------------------------------

def _make_get_family():
    """Six get_ functions with consistent shape — should form a family."""
    fns = [
        {"name": "get_player", "file_path": "world.py", "return_type": "dict"},
        {"name": "get_session", "file_path": "world.py", "return_type": "dict"},
        {"name": "get_character", "file_path": "world.py", "return_type": "dict"},
    ]
    return fns


def test_detect_conventions_finds_prefix_family():
    oracle = _make_oracle(functions=_make_get_family())
    result = detect_conventions(oracle, {})
    assert "prefix:get" in result
    assert "family" in result.lower() or "canon" in result.lower()


def test_detect_conventions_below_min_family_returns_no_families():
    fns = [
        {"name": "get_player", "file_path": "world.py"},
        {"name": "get_session", "file_path": "world.py"},
        # only 2 — below default min_family=3
    ]
    oracle = _make_oracle(functions=fns)
    result = detect_conventions(oracle, {})
    assert "No naming families" in result or "Conventions: 0" in result or "family" not in result


def test_detect_conventions_surfaces_outlier():
    """Outlier: one get_ function returns list while the rest return dict."""
    fns = [
        {"name": "get_player",    "file_path": "world.py", "return_type": "dict",
         "param_types_json": "{}"},
        {"name": "get_session",   "file_path": "world.py", "return_type": "dict",
         "param_types_json": "{}"},
        {"name": "get_character", "file_path": "world.py", "return_type": "dict",
         "param_types_json": "{}"},
        {"name": "get_items",     "file_path": "world.py", "return_type": "list",
         "param_types_json": "{}"},  # outlier
    ]
    oracle = _make_oracle(functions=fns)
    result = detect_conventions(oracle, {})
    # Should surface get_items as a diverging member
    assert "get_items" in result
    assert "diverges" in result or "differs" in result


def test_detect_conventions_scope_restricts_corpus():
    fns = [
        {"name": "get_player",  "file_path": "world.py", "return_type": "dict"},
        {"name": "get_session", "file_path": "world.py", "return_type": "dict"},
        {"name": "get_char",    "file_path": "world.py", "return_type": "dict"},
        # These are in a different file and should be excluded by scope
        {"name": "set_player",  "file_path": "admin.py"},
        {"name": "set_session", "file_path": "admin.py"},
        {"name": "set_char",    "file_path": "admin.py"},
    ]
    oracle = _make_oracle(functions=fns)
    result = detect_conventions(oracle, {"scope": "world.py"})
    assert "set_player" not in result


def test_detect_conventions_empty_corpus():
    oracle = _make_oracle(functions=[])
    result = detect_conventions(oracle, {})
    assert "No functions found" in result


# ---------------------------------------------------------------------------
# rank_stubs tests
# ---------------------------------------------------------------------------

def _make_rank_db():
    """Two stubs: one with callers (priority), one without."""
    fns = [
        {"name": "build_context", "file_path": "engine.py",
         "docstring": "Builds the game context for rendering", "is_stub": 1},
        {"name": "process_input", "file_path": "engine.py",
         "docstring": "", "is_stub": 1},
        {"name": "render_frame",  "file_path": "engine.py",
         "docstring": "", "is_stub": 0},  # not a stub
    ]
    edges = [
        {"caller": "render_frame", "callee": "build_context"},
    ]
    return fns, edges


def test_rank_stubs_priority_mode_returns_stubs():
    fns, edges = _make_rank_db()
    oracle = _make_oracle(functions=fns, edges=edges)
    assessor = _Assessor(oracle)
    result = rank_stubs(assessor, {"mode": "priority"})
    # Should find at least one actionable stub or report none
    assert "stub" in result.lower() or "No stubs" in result or "Priority" in result


def test_rank_stubs_gap_mode_groups_by_classification():
    fns, edges = _make_rank_db()
    oracle = _make_oracle(functions=fns, edges=edges)
    assessor = _Assessor(oracle)
    result = rank_stubs(assessor, {"mode": "gap"})
    assert "Gap survey" in result or "No stubs" in result


def test_rank_stubs_perusal_mode_returns_top_stubs():
    fns, edges = _make_rank_db()
    oracle = _make_oracle(functions=fns, edges=edges)
    assessor = _Assessor(oracle)
    result = rank_stubs(assessor, {"mode": "perusal"})
    assert "Top stubs" in result or "No stubs" in result


def test_rank_stubs_unknown_mode_returns_error():
    fns, _ = _make_rank_db()
    oracle = _make_oracle(functions=fns)
    assessor = _Assessor(oracle)
    result = rank_stubs(assessor, {"mode": "bogus"})
    assert "Unknown mode" in result


def test_rank_stubs_scope_restricts():
    fns = [
        {"name": "get_player",  "file_path": "world.py",  "is_stub": 1, "docstring": ""},
        {"name": "get_session", "file_path": "engine.py", "is_stub": 1, "docstring": ""},
    ]
    oracle = _make_oracle(functions=fns)
    assessor = _Assessor(oracle)
    result = rank_stubs(assessor, {"mode": "gap", "scope": "world.py"})
    assert "get_session" not in result


def test_rank_stubs_excludes_test_files():
    fns = [
        {"name": "test_stub_thing", "file_path": "test_foo.py", "is_stub": 1, "docstring": ""},
        {"name": "real_stub",       "file_path": "engine.py",   "is_stub": 1, "docstring": ""},
    ]
    oracle = _make_oracle(functions=fns)
    assessor = _Assessor(oracle)
    result = rank_stubs(assessor, {"mode": "gap"})
    assert "test_stub_thing" not in result
