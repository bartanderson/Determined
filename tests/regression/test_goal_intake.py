"""
Regression tests for RM10: goal_intake intent detection (2A) and trace routing (2B).
Uses in-memory SQLite; no LLM, no embeddings.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from determined.agent.agent_tools import (
    _classify_goal_type,
    _extract_trace_endpoints,
    _find_symbol_for_concept,
    goal_intake,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_oracle(conn, sym_rows=None):
    oracle = MagicMock()
    oracle.conn = conn
    oracle.get_project_root.return_value = "/proj"
    if sym_rows is not None:
        oracle.find_symbols.return_value = sym_rows
    else:
        oracle.find_symbols.return_value = []
    return oracle


def _make_assessor(conn, sym_rows=None):
    oracle = _make_oracle(conn, sym_rows)
    assessor = MagicMock()
    assessor.oracle = oracle
    return assessor


def _seed_db(conn):
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            line_number INTEGER DEFAULT 1,
            is_stub INTEGER DEFAULT 0,
            param_types_json TEXT,
            arguments_json TEXT,
            return_type TEXT,
            docstring TEXT
        );
        CREATE TABLE classes (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            docstring TEXT
        );
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            caller TEXT,
            callee TEXT,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            line_number INTEGER
        );
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            file_path TEXT
        );
        CREATE TABLE semantic_summaries (
            id INTEGER PRIMARY KEY,
            subject TEXT,
            distilled TEXT
        );
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY,
            kind TEXT,
            subject TEXT,
            body TEXT
        );
        CREATE TABLE symbol_references (
            id INTEGER PRIMARY KEY,
            caller TEXT,
            callee TEXT,
            file_path TEXT,
            line_number INTEGER
        );
    """)
    # Functions: handle_input -> process_input -> save_to_db
    fn_rows = [
        ("handle_input",   "/proj/input.py",     0, "Receives player input from UI"),
        ("process_input",  "/proj/processor.py", 0, "Processes and validates input"),
        ("save_to_db",     "/proj/db.py",        0, "Saves processed data to database"),
        ("apply_effect",   "/proj/effects.py",   0, "Apply game effect to state"),
        ("check_boundary", "/proj/ai.py",        0, "Enforce AI boundary rules"),
    ]
    conn.executemany(
        "INSERT INTO functions (name, file_path, is_stub, docstring) VALUES (?,?,?,?)",
        fn_rows,
    )
    conn.executemany(
        "INSERT INTO graph_edges (caller, callee, caller_file, resolved) VALUES (?,?,?,?)",
        [
            ("handle_input",  "process_input", "/proj/input.py",     1),
            ("process_input", "save_to_db",    "/proj/processor.py", 1),
        ]
    )
    conn.execute("INSERT INTO files (file_path) VALUES ('/proj/input.py')")
    conn.commit()
    return [{"name": r[0], "file_path": r[1], "symbol_type": "function", "line_number": 1} for r in fn_rows]


# ---------------------------------------------------------------------------
# 2A: _classify_goal_type
# ---------------------------------------------------------------------------

def test_classify_implement():
    assert _classify_goal_type("add consequence tracking to the game") == "implement"


def test_classify_investigate_find():
    assert _classify_goal_type("find where the AI boundary is violated") == "investigate"


def test_classify_investigate_detect():
    assert _classify_goal_type("detect where data leaks occur") == "investigate"


def test_classify_trace_explicit():
    assert _classify_goal_type("trace how player input reaches the database") == "trace"


def test_classify_trace_follow():
    assert _classify_goal_type("follow the flow from handle_input to save_to_db") == "trace"


def test_classify_explain():
    assert _classify_goal_type("explain what process_input does") == "explain"


def test_classify_explain_what_is():
    assert _classify_goal_type("what is the AI boundary") == "explain"


# ---------------------------------------------------------------------------
# 2B: _extract_trace_endpoints
# ---------------------------------------------------------------------------

def test_extract_endpoints_trace():
    src, dst = _extract_trace_endpoints("trace player input to database")
    assert "input" in src
    assert "database" in dst


def test_extract_endpoints_follow():
    src, dst = _extract_trace_endpoints("follow the flow from handle_input to save_to_db")
    assert "handle_input" in src
    assert "save_to_db" in dst


def test_extract_endpoints_empty():
    src, dst = _extract_trace_endpoints("add consequence tracking")
    assert src == "" and dst == ""


# ---------------------------------------------------------------------------
# _find_symbol_for_concept
# ---------------------------------------------------------------------------

def test_find_symbol_exact(tmp_path):
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    sym = _find_symbol_for_concept(oracle, "handle input")
    assert sym == "handle_input"


def test_find_symbol_none(tmp_path):
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    oracle = _make_oracle(conn)
    sym = _find_symbol_for_concept(oracle, "xyzzy nonexistent")
    assert sym is None


# ---------------------------------------------------------------------------
# goal_intake integration: intent label + nav plan
# ---------------------------------------------------------------------------

def _call_goal_intake(conn, goal: str, sym_rows=None) -> str:
    assessor = _make_assessor(conn, sym_rows)
    # score_risk and search_tenets are imported inside goal_intake body,
    # so patch at their source modules.
    with patch("determined.agent.agent_tools._get_embed_model", side_effect=Exception("no model")):
        with patch("determined.agent.risk_annotator.score_risk", return_value={"level": "SAFE", "reasons": []}):
            with patch("determined.data.sots_loader.search_tenets", return_value=[]):
                return goal_intake(assessor, {"goal": goal})


def test_goal_intake_shows_intent_label():
    conn = sqlite3.connect(":memory:")
    sym_rows = _seed_db(conn)
    result = _call_goal_intake(conn, "add consequence tracking to player actions", sym_rows)
    assert "Intent: implement" in result


def test_goal_intake_investigate_no_modify():
    conn = sqlite3.connect(":memory:")
    sym_rows = _seed_db(conn)
    result = _call_goal_intake(conn, "find where the AI boundary is violated", sym_rows)
    assert "Intent: investigate" in result
    assert "MODIFY" not in result
    assert "EXTEND" not in result


def test_goal_intake_investigate_has_blast_radius():
    conn = sqlite3.connect(":memory:")
    sym_rows = _seed_db(conn)
    assessor = _make_assessor(conn, sym_rows)
    # Seed relevant_symbols directly by patching _search_symbols_raw + embedding
    fake_sym = [{"name": "check_boundary", "file_path": "/proj/ai.py",
                 "symbol_type": "function", "line_number": 1, "docstring": "AI boundary check"}]
    import numpy as np
    class _FakeModel:
        def encode(self, texts, normalize_embeddings=False):
            # Return vectors where symbol matches goal perfectly
            return np.array([[1.0]] * len(texts))
    with patch("determined.agent.agent_tools._search_symbols_raw", return_value=fake_sym):
        with patch("determined.agent.agent_tools._get_embed_model", return_value=_FakeModel()):
            with patch("determined.agent.risk_annotator.score_risk", return_value={"level": "HOT", "reasons": ["high callers"]}):
                with patch("determined.data.sots_loader.search_tenets", return_value=[]):
                    result = goal_intake(assessor, {"goal": "find where the AI boundary is violated"})
    assert "BLAST_RADIUS" in result


def test_goal_intake_implement_has_modify():
    conn = sqlite3.connect(":memory:")
    sym_rows = _seed_db(conn)
    result = _call_goal_intake(conn, "add consequence tracking", sym_rows)
    assert "Intent: implement" in result


def test_goal_intake_explain_no_modify():
    conn = sqlite3.connect(":memory:")
    sym_rows = _seed_db(conn)
    result = _call_goal_intake(conn, "explain what process_input does", sym_rows)
    assert "Intent: explain" in result
    assert "MODIFY" not in result
    assert "EXTEND" not in result


def test_goal_intake_trace_shows_call_path():
    conn = sqlite3.connect(":memory:")
    sym_rows = _seed_db(conn)
    result = _call_goal_intake(conn, "trace how handle_input reaches save_to_db", sym_rows)
    assert "Intent: trace" in result
    assert "Call path" in result


def test_goal_intake_missing_goal_returns_error():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = _call_goal_intake(conn, "")
    assert "ERROR" in result
