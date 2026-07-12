"""Regression tests for completion_contract tool (RM45)."""
import json
import sqlite3
import pytest
from determined.agent.agent_tools import completion_contract


# ---------------------------------------------------------------------------
# Minimal oracle/assessor stubs
# ---------------------------------------------------------------------------

class _Oracle:
    def __init__(self, conn):
        self.conn = conn


class _Assessor:
    def __init__(self, conn):
        self.oracle = _Oracle(conn)


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            line_number INTEGER,
            is_stub INTEGER DEFAULT 0,
            param_types_json TEXT DEFAULT '{}',
            return_type TEXT DEFAULT '',
            docstring TEXT DEFAULT '',
            decorators_json TEXT DEFAULT '[]'
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
            line_number INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE behavioral_contracts (
            function_name TEXT,
            file_path TEXT,
            line_number INTEGER,
            description TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE symbols (
            name TEXT,
            file_path TEXT,
            line_number INTEGER,
            symbol_type TEXT
        )
    """)
    conn.commit()
    return conn


def _add_fn(conn, name, fp="mod.py", ln=1, is_stub=0,
            params=None, ret="", doc=""):
    conn.execute(
        "INSERT OR IGNORE INTO functions VALUES (?,?,?,?,?,?,?,'[]')",
        (name, fp, ln, is_stub, json.dumps(params or {}), ret, doc),
    )


def _add_edge(conn, caller, callee, caller_fp="mod.py", ln=1):
    conn.execute("INSERT INTO graph_edges VALUES (?,?,?,0)", (caller, callee, ln))
    conn.execute("INSERT INTO symbol_references VALUES (?,?,?,?)", (caller, callee, caller_fp, ln))


def _add_contract(conn, fn, desc, ln=1):
    conn.execute(
        "INSERT INTO behavioral_contracts VALUES (?,?,?,?)", (fn, "mod.py", ln, desc)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_missing_symbol_error():
    conn = _make_db()
    result = completion_contract(_Assessor(conn), {"symbol": "nonexistent"})
    assert "ERROR" in result
    assert "not found" in result


def test_empty_symbol_error():
    conn = _make_db()
    result = completion_contract(_Assessor(conn), {})
    assert "ERROR" in result


def test_basic_stub_shows_signature():
    conn = _make_db()
    _add_fn(conn, "process", fp="engine.py", ln=42, is_stub=1,
             params={"self": "Engine", "action": "Action"}, ret="Dict")
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "process"})
    assert "process" in result
    assert "engine.py:42" in result
    assert "SIGNATURE" in result
    assert "Action" in result
    assert "Dict" in result


def test_callers_listed():
    conn = _make_db()
    _add_fn(conn, "process", fp="engine.py", ln=10, is_stub=1)
    _add_fn(conn, "run_turn", fp="loop.py", ln=50)
    _add_edge(conn, "run_turn", "process", caller_fp="loop.py", ln=55)
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "process"})
    assert "CALLERS" in result
    assert "run_turn" in result


def test_no_callers_message():
    conn = _make_db()
    _add_fn(conn, "orphan_stub", fp="a.py", ln=1, is_stub=1)
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "orphan_stub"})
    assert "CALLERS" in result
    assert "none" in result.lower() or "uncalled" in result.lower()


def test_stub_callees_flagged():
    conn = _make_db()
    _add_fn(conn, "top_stub", fp="a.py", ln=1, is_stub=1)
    _add_fn(conn, "dep_stub", fp="a.py", ln=10, is_stub=1)
    _add_fn(conn, "impl_fn", fp="a.py", ln=20, is_stub=0)
    _add_edge(conn, "top_stub", "dep_stub")
    _add_edge(conn, "top_stub", "impl_fn")
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "top_stub"})
    assert "dep_stub" in result
    assert "impl_fn" in result
    assert "implement" in result.lower() or "STUBS THIS DEPENDS" in result


def test_behavioral_contracts_shown():
    conn = _make_db()
    _add_fn(conn, "validate", fp="v.py", ln=5, is_stub=1)
    _add_contract(conn, "validate", "Returns True if input is valid, False otherwise")
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "validate"})
    assert "CONTRACTS" in result
    assert "Returns True" in result


def test_docstring_fallback_when_no_contracts():
    conn = _make_db()
    _add_fn(conn, "compute", fp="c.py", ln=3, is_stub=1,
             doc="Compute the final score from raw inputs.")
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "compute"})
    assert "CONTRACTS" in result
    assert "Compute the final score" in result


def test_no_type_annotations_message():
    conn = _make_db()
    _add_fn(conn, "bare_stub", fp="b.py", ln=1, is_stub=1)
    conn.commit()
    result = completion_contract(_Assessor(conn), {"symbol": "bare_stub"})
    assert "SIGNATURE" in result
    # Should not crash; may show placeholder
    assert "bare_stub" in result


def test_completion_contract_in_tools():
    from determined.agent.agent_tools import TOOLS
    assert "completion_contract" in TOOLS


def test_completion_contract_in_registry():
    from determined.agent.tool_registry import REGISTRY
    assert "completion_contract" in REGISTRY
    entry = REGISTRY["completion_contract"]
    assert entry["category"] == "understanding"
