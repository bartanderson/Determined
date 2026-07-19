# tests/regression/test_design_oracle.py
#
# Regression tests for design_oracle (agent_tools.py).
# Uses in-memory SQLite — no live corpus required.

import sqlite3
from unittest.mock import MagicMock

from determined.agent.agent_tools import design_oracle


def _make_db(stubs=None, non_stubs=None, edges=None):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            name TEXT, file_path TEXT, is_stub INTEGER DEFAULT 0,
            docstring TEXT, param_types_json TEXT, return_type TEXT,
            line_number INTEGER DEFAULT 1
        );
        CREATE TABLE graph_edges (
            caller TEXT, callee TEXT, edge_type TEXT DEFAULT 'static',
            line_number INTEGER DEFAULT 1, resolved INTEGER DEFAULT 0
        );
        CREATE TABLE symbol_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT, caller TEXT, callee TEXT,
            line_number INTEGER, bucket TEXT, edge_role TEXT
        );
    """)
    for s in (stubs or []):
        conn.execute(
            "INSERT INTO functions (name, file_path, is_stub, docstring) VALUES (?,?,1,?)",
            (s["name"], s.get("file_path", "world/ai.py"), s.get("docstring", "")),
        )
    for n in (non_stubs or []):
        conn.execute(
            "INSERT INTO functions (name, file_path, is_stub, docstring) VALUES (?,?,0,?)",
            (n["name"], n.get("file_path", "world/ai.py"), n.get("docstring", "")),
        )
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee) VALUES (?,?)",
            (e["caller"], e["callee"]),
        )
    conn.commit()
    return conn


def _make_assessor(conn):
    assessor = MagicMock()
    oracle = MagicMock()
    oracle.conn = conn
    assessor.oracle = oracle
    assessor.list_artifacts = MagicMock(return_value=[])
    return assessor


def test_design_oracle_no_stubs():
    conn = _make_db()
    result = design_oracle(_make_assessor(conn), {})
    assert "no stubs" in result.lower()


def test_design_oracle_critical_blocked():
    """Blocked stub with most callers is CRITICAL."""
    conn = _make_db(
        stubs=[
            {"name": "init_ai", "file_path": "world/ai.py",
             "docstring": "requires GameEngine to be built first"},
            {"name": "build_map", "file_path": "world/map.py", "docstring": ""},
        ],
        edges=[
            {"caller": "run_game", "callee": "init_ai"},
            {"caller": "start_encounter", "callee": "init_ai"},
        ],
    )
    result = design_oracle(_make_assessor(conn), {})
    assert "CRITICAL" in result
    assert "init_ai" in result


def test_design_oracle_fallback_critical_no_blocked():
    """When no blocked stub, highest-fanout stub becomes CRITICAL."""
    conn = _make_db(
        stubs=[
            {"name": "stub_a", "file_path": "world/a.py", "docstring": ""},
            {"name": "stub_b", "file_path": "world/b.py", "docstring": ""},
        ],
        edges=[
            {"caller": "x", "callee": "stub_a"},
            {"caller": "y", "callee": "stub_a"},
        ],
    )
    result = design_oracle(_make_assessor(conn), {})
    assert "CRITICAL" in result
    assert "stub_a" in result


def test_design_oracle_opportunity_context():
    """Unblocked stubs in same dir as context appear as OPPORTUNITY."""
    conn = _make_db(
        stubs=[
            {"name": "blocked_stub", "file_path": "world/ai.py",
             "docstring": "requires X"},
            {"name": "ready_stub", "file_path": "world/ai.py",
             "docstring": "I want to implement the AI decision loop"},
        ],
        non_stubs=[
            {"name": "run_ai", "file_path": "world/ai.py"},
        ],
    )
    result = design_oracle(_make_assessor(conn), {"context": "run_ai"})
    assert "OPPORTUNITY" in result
    assert "ready_stub" in result


def test_design_oracle_tip_without_context():
    """Without context, output includes tip to pass context."""
    conn = _make_db(stubs=[{"name": "stub_x", "docstring": ""}])
    result = design_oracle(_make_assessor(conn), {})
    assert "context" in result.lower()
