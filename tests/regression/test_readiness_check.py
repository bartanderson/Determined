"""Regression tests for readiness_check tool (RM47)."""
import json
import sqlite3
import pytest
from determined.agent.agent_tools import readiness_check


class _Oracle:
    def __init__(self, conn):
        self.conn = conn
        self.db_path = ":memory:"

    def get_project_root(self):
        return "/project"


class _Assessor:
    def __init__(self, conn):
        self.oracle = _Oracle(conn)


def _make_db(rows=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            line_number INTEGER DEFAULT 1,
            is_stub INTEGER DEFAULT 0,
            param_types_json TEXT DEFAULT '{}',
            return_type TEXT DEFAULT '',
            docstring TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE classes (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            line_number INTEGER DEFAULT 1,
            docstring TEXT DEFAULT '',
            base_classes_json TEXT DEFAULT '[]',
            methods_json TEXT DEFAULT '[]'
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            line_number INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE symbol_references (
            caller TEXT,
            callee TEXT,
            file_path TEXT,
            line_number INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE abstract_methods (
            class_name TEXT,
            method_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE class_hierarchy (
            parent_name TEXT,
            child_name TEXT
        )
    """)
    if rows:
        for r in rows:
            conn.execute(
                "INSERT INTO functions (name, file_path, line_number, is_stub, param_types_json, return_type) VALUES (?,?,?,?,?,?)",
                r,
            )
    conn.commit()
    return conn


FP = "/project/module.py"


# ---------------------------------------------------------------------------
# Tier 1: symbol existence / already-complete
# ---------------------------------------------------------------------------

def test_missing_symbol():
    conn = _make_db()
    result = readiness_check(_Assessor(conn), {"symbol": "nonexistent"})
    assert "NOT FOUND" in result


def test_missing_symbol_arg():
    conn = _make_db()
    result = readiness_check(_Assessor(conn), {})
    assert result.startswith("ERROR")


def test_already_complete():
    conn = _make_db([("complete_fn", FP, 1, 0, "{}", "")])
    result = readiness_check(_Assessor(conn), {"symbol": "complete_fn"})
    assert "ALREADY COMPLETE" in result


# ---------------------------------------------------------------------------
# Tier 2: stub callees
# ---------------------------------------------------------------------------

def test_ready_no_stub_callees():
    conn = _make_db([
        ("my_stub", FP, 1, 1, "{}", ""),
        ("helper", FP, 10, 0, "{}", ""),  # complete callee
    ])
    conn.execute("INSERT INTO graph_edges VALUES ('my_stub', 'helper', 5, 1)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "my_stub"})
    assert "READY" in result
    assert "STUB CALLEE" not in result


def test_blocked_stub_callee():
    conn = _make_db([
        ("my_stub", FP, 1, 1, "{}", ""),
        ("upstream_stub", FP, 20, 1, "{}", ""),
    ])
    conn.execute("INSERT INTO graph_edges VALUES ('my_stub', 'upstream_stub', 5, 0)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "my_stub"})
    assert "BLOCKED" in result
    assert "STUB CALLEE" in result
    assert "upstream_stub" in result


def test_stub_callee_lists_implement_first():
    conn = _make_db([
        ("target", FP, 1, 1, "{}", ""),
        ("dep_stub", FP, 5, 1, "{}", ""),
    ])
    conn.execute("INSERT INTO graph_edges VALUES ('target', 'dep_stub', 2, 0)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "target"})
    assert "implement first" in result.lower()


# ---------------------------------------------------------------------------
# Tier 3: unknown type annotations
# ---------------------------------------------------------------------------

def test_ready_known_type():
    conn = _make_db([
        ("my_stub", FP, 1, 1, json.dumps({"x": "MyClass"}), ""),
    ])
    conn.execute("INSERT INTO classes (name, file_path, line_number) VALUES ('MyClass', '/project/types.py', 1)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "my_stub"})
    # MyClass is found in classes — should not be flagged
    assert "UNKNOWN TYPE: MyClass" not in result


def test_unknown_type_annotation():
    conn = _make_db([
        ("my_stub", FP, 1, 1, json.dumps({"x": "GhostType"}), ""),
    ])
    # GhostType not in functions or classes
    result = readiness_check(_Assessor(conn), {"symbol": "my_stub"})
    assert "UNKNOWN TYPE" in result
    assert "GhostType" in result


def test_builtin_types_not_flagged():
    conn = _make_db([
        ("my_stub", FP, 1, 1, json.dumps({"a": "str", "b": "int", "c": "bool"}), ""),
    ])
    result = readiness_check(_Assessor(conn), {"symbol": "my_stub"})
    assert "UNKNOWN TYPE" not in result


# ---------------------------------------------------------------------------
# Tier 5: cycle detection
# ---------------------------------------------------------------------------

def test_cycle_in_stub_graph():
    conn = _make_db([
        ("alpha", FP, 1, 1, "{}", ""),
        ("beta", FP, 5, 1, "{}", ""),
    ])
    # alpha -> beta -> alpha
    conn.execute("INSERT INTO graph_edges VALUES ('alpha', 'beta', 2, 0)")
    conn.execute("INSERT INTO graph_edges VALUES ('beta', 'alpha', 3, 0)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "alpha"})
    assert "CYCLE" in result


def test_no_false_cycle():
    conn = _make_db([
        ("root_stub", FP, 1, 1, "{}", ""),
        ("leaf", FP, 5, 0, "{}", ""),  # complete, not a stub
    ])
    conn.execute("INSERT INTO graph_edges VALUES ('root_stub', 'leaf', 2, 1)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "root_stub"})
    assert "CYCLE" not in result


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_ready_suggests_completion_contract():
    conn = _make_db([("solo_stub", FP, 1, 1, "{}", "")])
    result = readiness_check(_Assessor(conn), {"symbol": "solo_stub"})
    assert "completion_contract" in result


def test_blocked_suggests_implementation_order():
    conn = _make_db([
        ("tgt", FP, 1, 1, "{}", ""),
        ("dep", FP, 5, 1, "{}", ""),
    ])
    conn.execute("INSERT INTO graph_edges VALUES ('tgt', 'dep', 2, 0)")
    conn.commit()
    result = readiness_check(_Assessor(conn), {"symbol": "tgt"})
    assert "implementation_order" in result


def test_header_contains_symbol_and_file():
    conn = _make_db([("my_fn", FP, 42, 1, "{}", "")])
    result = readiness_check(_Assessor(conn), {"symbol": "my_fn"})
    assert "my_fn" in result
    assert "module.py" in result
    assert "42" in result
