"""
Regression tests for RM64: verify_implementation and detect_doc_drift.
Uses in-memory SQLite; no LLM, no embeddings.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock

from determined.agent.agent_tools import verify_implementation, detect_doc_drift


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _make_assessor(conn):
    oracle = MagicMock()
    oracle.conn = conn
    assessor = MagicMock()
    assessor.oracle = oracle
    return assessor


def _seed_db(conn):
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0,
            docstring TEXT
        );
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            caller TEXT,
            callee TEXT,
            caller_file TEXT
        );
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY,
            kind TEXT,
            subject TEXT,
            content TEXT,
            source TEXT
        );
    """)
    conn.executemany(
        "INSERT INTO functions (name, file_path, is_stub, docstring) VALUES (?,?,?,?)",
        [
            ("handle_input",   "world/input.py",   0, "Receives player input"),
            ("save_to_db",     "world/db.py",       0, "Saves data to database"),
            ("stub_fn",        "world/stubs.py",    1, "TODO: implement this"),
            ("implemented_fn", "world/actions.py",  0, "Applies the action"),
            ("orphan_ep",      "world/entry.py",    0, "Entry point with no design note"),
            ("stale_doc_fn",   "world/misc.py",     0, "placeholder -- not implemented yet"),
        ]
    )
    conn.executemany(
        "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
        [
            ("handle_input",   "save_to_db",     "world/input.py"),
            ("handle_input",   "implemented_fn", "world/input.py"),
            ("handle_input",   "missing_helper", "world/input.py"),  # unresolved
            ("external_entry", "handle_input",   "app.py"),
            ("external_entry", "orphan_ep",      "app.py"),
        ]
    )
    conn.execute(
        "INSERT INTO knowledge_artifacts (kind, subject, content, source) VALUES (?,?,?,?)",
        ("design_note", "handle_input", "MUST handle all input types", "design.md"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# verify_implementation tests
# ---------------------------------------------------------------------------

def test_verify_missing_symbol():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = verify_implementation(_make_assessor(conn), {"symbol": "no_such_fn"})
    assert "FAIL" in result
    assert "not found" in result


def test_verify_still_stub():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = verify_implementation(_make_assessor(conn), {"symbol": "stub_fn"})
    assert "FAIL" in result
    assert "is_stub=1" in result


def test_verify_pass_clean():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    # implemented_fn: is_stub=0, has a caller, callee (none) all resolve
    result = verify_implementation(_make_assessor(conn), {"symbol": "implemented_fn"})
    assert "PASS" in result
    assert "is_stub=0" in result


def test_verify_unresolved_callees():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    # handle_input calls missing_helper which is not in functions
    result = verify_implementation(_make_assessor(conn), {"symbol": "handle_input"})
    assert "unresolved" in result
    assert "missing_helper" in result


def test_verify_callers_shown():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = verify_implementation(_make_assessor(conn), {"symbol": "handle_input"})
    assert "external_entry" in result


def test_verify_doc_stale_warn():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    # stub_fn is still a stub, but also check stale_doc_fn separately
    # Add a caller for stale_doc_fn so it doesn't hit the no-caller warning
    conn.execute(
        "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
        ("handle_input", "stale_doc_fn", "world/input.py"),
    )
    conn.commit()
    result = verify_implementation(_make_assessor(conn), {"symbol": "stale_doc_fn"})
    assert "stub language" in result or "WARN" in result


def test_verify_no_symbol_arg():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = verify_implementation(_make_assessor(conn), {})
    assert "ERROR" in result


# ---------------------------------------------------------------------------
# detect_doc_drift tests
# ---------------------------------------------------------------------------

def test_drift_no_feature_path():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = detect_doc_drift(_make_assessor(conn), {})
    assert "ERROR" in result


def test_drift_pass_when_none():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    # Scan a path with no functions
    result = detect_doc_drift(_make_assessor(conn), {"feature_path": "engine/"})
    assert "PASS" in result


def test_drift_detects_ep_without_note():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    # stale_doc_fn has no callers and no design_note -- should appear in EP list
    result = detect_doc_drift(_make_assessor(conn), {"feature_path": "world/"})
    assert "stale_doc_fn" in result
    assert "design_note" in result


def test_drift_ep_with_note_not_flagged():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    # handle_input has a design_note AND callers, so it's not an EP anyway
    # orphan_ep has caller from external_entry, so it IS reachable -- not an EP
    # Let's add orphan_ep as having no callers to make it a true EP
    conn.execute("DELETE FROM graph_edges WHERE callee='orphan_ep'")
    conn.execute(
        "INSERT INTO knowledge_artifacts (kind, subject, content, source) VALUES (?,?,?,?)",
        ("design_note", "orphan_ep", "MUST handle entry", "design.md"),
    )
    conn.commit()
    result = detect_doc_drift(_make_assessor(conn), {"feature_path": "world/"})
    # orphan_ep now has a design note, should not appear in drift list
    assert "orphan_ep" not in result or "PASS" in result


def test_drift_detects_doc_stale():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = detect_doc_drift(_make_assessor(conn), {"feature_path": "world/"})
    assert "stale_doc_fn" in result
    assert "placeholder" in result


def test_drift_summary_shows_count():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    result = detect_doc_drift(_make_assessor(conn), {"feature_path": "world/"})
    assert "DRIFT" in result
