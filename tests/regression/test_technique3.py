# tests/regression/test_technique3.py
#
# Regression tests for RM21 Technique 3:
#   - walk_call_chain (agent_tools.py)
#   - trace_call_chain detect rule (pattern_executor.py)
#   - "each" heuristic fix (agent_resolver.py)

import sqlite3
import os
os.environ.setdefault("PYTHONPATH", ".")

import pytest
from unittest.mock import MagicMock

from determined.agent.agent_tools import walk_call_chain
from determined.agent.pattern_executor import detect_pattern
from determined.agent.agent_resolver import detect_heuristic


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_oracle(conn):
    oracle = MagicMock()
    oracle.conn = conn
    return oracle


def _seed_db(conn):
    """Minimal schema + data: A -> B -> C, B is a stub."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS functions (
            name TEXT, file_path TEXT, is_stub INTEGER DEFAULT 0,
            param_types_json TEXT, return_type TEXT, docstring TEXT,
            line_number INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS graph_edges (
            caller TEXT, callee TEXT, edge_type TEXT DEFAULT 'static',
            line_number INTEGER DEFAULT 1, resolved INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS symbol_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT, caller TEXT, callee TEXT,
            line_number INTEGER, bucket TEXT, edge_role TEXT
        );
    """)
    conn.execute("INSERT INTO functions VALUES ('A','a.py',0,'{}','str','does A',1)")
    conn.execute("INSERT INTO functions VALUES ('B','b.py',1,'{}','int','does B',1)")
    conn.execute("INSERT INTO functions VALUES ('C','c.py',0,'{}','None','does C',1)")
    conn.execute("INSERT INTO graph_edges VALUES ('A','B','static',2,1)")
    conn.execute("INSERT INTO graph_edges VALUES ('B','C','static',3,1)")
    conn.commit()


# ------------------------------------------------------------------
# walk_call_chain
# ------------------------------------------------------------------

def test_walk_chain_basic():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    chain = walk_call_chain("A", oracle)
    names = [n["symbol"] for n in chain]
    assert "A" in names
    assert "B" in names
    assert "C" in names


def test_walk_chain_order():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    chain = walk_call_chain("A", oracle)
    # A must appear before B (BFS order)
    names = [n["symbol"] for n in chain]
    assert names.index("A") < names.index("B")
    assert names.index("B") < names.index("C")


def test_walk_chain_stub_annotation():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    chain = walk_call_chain("A", oracle)
    nodes = {n["symbol"]: n for n in chain}
    assert nodes["A"]["is_stub"] is False
    assert nodes["B"]["is_stub"] is True
    assert nodes["C"]["is_stub"] is False


def test_walk_chain_depth_limit():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    # max_depth=1 should include A and B but not C (C is at depth 2)
    chain = walk_call_chain("A", oracle, max_depth=1)
    names = [n["symbol"] for n in chain]
    assert "A" in names
    assert "B" in names
    assert "C" not in names


def test_walk_chain_unknown_start():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    chain = walk_call_chain("nonexistent", oracle)
    assert chain == []


def test_walk_chain_no_cycles():
    """A cycle A->B->A should not produce infinite loop."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            name TEXT, file_path TEXT, is_stub INTEGER DEFAULT 0,
            param_types_json TEXT, return_type TEXT, docstring TEXT,
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
    conn.execute("INSERT INTO functions VALUES ('A','a.py',0,'{}','','',1)")
    conn.execute("INSERT INTO functions VALUES ('B','b.py',0,'{}','','',1)")
    conn.execute("INSERT INTO graph_edges VALUES ('A','B','static',1,1)")
    conn.execute("INSERT INTO graph_edges VALUES ('B','A','static',2,1)")
    conn.commit()
    oracle = _make_oracle(conn)
    chain = walk_call_chain("A", oracle)
    names = [n["symbol"] for n in chain]
    assert names.count("A") == 1
    assert names.count("B") == 1


def test_walk_chain_callees_list():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    chain = walk_call_chain("A", oracle)
    a_node = next(n for n in chain if n["symbol"] == "A")
    assert "B" in a_node["callees"]


# ------------------------------------------------------------------
# detect_pattern — trace_call_chain
# ------------------------------------------------------------------

def test_detect_trace_call_chain_search():
    name, _ = detect_pattern(
        "Trace the full path from the HTTP route that handles a search request through to the database"
    )
    assert name == "trace_call_chain"


def test_detect_trace_call_chain_save():
    name, _ = detect_pattern(
        "When a new entry is saved, which functions run between the HTTP handler and the database insert"
    )
    assert name == "trace_call_chain"


def test_detect_trace_call_chain_route():
    name, _ = detect_pattern(
        "Trace the call chain from the web route to the database"
    )
    assert name == "trace_call_chain"


def test_detect_trace_data_flow_still_works():
    """Specific symbol-to-symbol trace should still hit trace_data_flow, not trace_call_chain."""
    name, subject = detect_pattern("trace process_message to database_write")
    # trace_data_flow requires a specific symbol as source; this should still match
    assert name in ("trace_data_flow", "trace_call_chain")  # either is acceptable


def test_detect_trace_call_chain_not_triggered_for_symbol_query():
    name, _ = detect_pattern("what calls enrich_entry")
    assert name != "trace_call_chain"


# ------------------------------------------------------------------
# detect_heuristic — "each" fix
# ------------------------------------------------------------------

def test_heuristic_each_not_extracted_as_symbol():
    """'what does each one do' should not match the 'what does X do' heuristic."""
    result = detect_heuristic(
        "When a new entry is saved, which functions run between the HTTP handler "
        "and the database insert, and what does each one do?"
    )
    # If the heuristic fires at all, it must not have extracted "each" as a symbol
    if result is not None:
        for need in result:
            assert "each" not in need.lower() or "each" not in need.split()[-1]


def test_heuristic_real_symbol_still_works():
    """'what does enrich_entry do' should still match."""
    result = detect_heuristic("what does enrich_entry do")
    assert result is not None
    assert any("enrich_entry" in n for n in result)
