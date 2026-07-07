"""Regression tests for RM19 Pass 1: find_duplicates duplicate detection."""
import json
import sqlite3
import tempfile
import os
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(functions: list[dict]) -> sqlite3.Connection:
    """Create an in-memory corpus DB with a minimal schema and the given functions."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line_number INTEGER DEFAULT 0,
            docstring TEXT,
            is_stub INTEGER DEFAULT 0,
            return_type TEXT,
            param_types_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            provenance TEXT NOT NULL DEFAULT 'ai-generated',
            created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00+00:00',
            file_hash TEXT,
            needs_review INTEGER NOT NULL DEFAULT 0,
            corpus TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ka_kind ON knowledge_artifacts(kind)")
    for fn in functions:
        conn.execute(
            "INSERT INTO functions (name, file_path, line_number, docstring) VALUES (?,?,?,?)",
            (fn["name"], fn.get("file_path", "a.py"), fn.get("line", 1), fn.get("docstring")),
        )
    conn.commit()
    return conn


class _FakeOracle:
    def __init__(self, conn):
        self.conn = conn


class _FakeAssessor:
    def __init__(self, conn):
        self.oracle = _FakeOracle(conn)


# ---------------------------------------------------------------------------
# VALID_KINDS includes reconciliation_finding
# ---------------------------------------------------------------------------

def test_reconciliation_finding_in_valid_kinds():
    from determined.intent.knowledge_artifact import VALID_KINDS
    assert "reconciliation_finding" in VALID_KINDS


# ---------------------------------------------------------------------------
# find_duplicates -- basic behaviour
# ---------------------------------------------------------------------------

def test_find_duplicates_no_docstrings():
    conn = _make_db([
        {"name": "foo", "docstring": None},
        {"name": "bar", "docstring": None},
    ])
    from determined.agent.agent_tools import find_duplicates
    result = find_duplicates(_FakeAssessor(conn), {})
    assert "fewer than 2" in result


def test_find_duplicates_one_docstring():
    conn = _make_db([
        {"name": "foo", "docstring": "does something"},
        {"name": "bar", "docstring": None},
    ])
    from determined.agent.agent_tools import find_duplicates
    result = find_duplicates(_FakeAssessor(conn), {})
    assert "fewer than 2" in result


def test_find_duplicates_identical_docstrings_detected():
    """Two functions with identical docstrings should score ~1.0 and be detected."""
    docstring = "Parse the user input and return a cleaned string."
    conn = _make_db([
        {"name": "parse_input",  "file_path": "a.py", "docstring": docstring},
        {"name": "clean_input",  "file_path": "b.py", "docstring": docstring},
    ])
    from determined.agent.agent_tools import find_duplicates
    result = find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    assert "parse_input" in result or "clean_input" in result
    # At least 1 pair stored
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    assert rows >= 1


def test_find_duplicates_unrelated_docstrings_below_threshold():
    """Semantically unrelated functions should not appear as duplicates."""
    conn = _make_db([
        {"name": "render_html",   "file_path": "a.py", "docstring": "Render an HTML template to string."},
        {"name": "connect_db",    "file_path": "b.py", "docstring": "Open a database connection and return cursor."},
        {"name": "sort_numbers",  "file_path": "c.py", "docstring": "Sort a list of integers in ascending order."},
    ])
    from determined.agent.agent_tools import find_duplicates
    result = find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    assert rows == 0


def test_find_duplicates_artifact_content_is_valid_json():
    """Stored reconciliation_finding content must be valid JSON with required keys."""
    docstring = "Calculate the sum of all elements in a list."
    conn = _make_db([
        {"name": "sum_list",   "file_path": "a.py", "docstring": docstring},
        {"name": "total_list", "file_path": "b.py", "docstring": docstring},
    ])
    from determined.agent.agent_tools import find_duplicates
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchall()
    assert len(rows) >= 1
    for (content,) in rows:
        d = json.loads(content)
        assert "symbol_a" in d
        assert "symbol_b" in d
        assert "file_a" in d
        assert "file_b" in d
        assert "score" in d
        assert 0.0 <= d["score"] <= 1.0


def test_find_duplicates_idempotent():
    """Running find_duplicates twice should not double-store pairs."""
    docstring = "Validate email address format and return bool."
    conn = _make_db([
        {"name": "validate_email",  "file_path": "a.py", "docstring": docstring},
        {"name": "check_email",     "file_path": "b.py", "docstring": docstring},
    ])
    from determined.agent.agent_tools import find_duplicates
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    count_first = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    result2 = find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    count_second = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    assert count_first == count_second
    assert "already recorded" in result2


def test_find_duplicates_clear_resets():
    """clear=True should delete existing findings and rescan."""
    docstring = "Serialize an object to a JSON string."
    conn = _make_db([
        {"name": "to_json",      "file_path": "a.py", "docstring": docstring},
        {"name": "serialize",    "file_path": "b.py", "docstring": docstring},
    ])
    from determined.agent.agent_tools import find_duplicates
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    count_before = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.85", "clear": True})
    count_after = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    assert count_after == count_before   # same pairs re-stored, not doubled


def test_find_duplicates_same_symbol_same_file_skipped():
    """A function should not be paired with itself even if the DB has it twice."""
    docstring = "Build a query from filter params."
    conn = _make_db([
        {"name": "build_query", "file_path": "a.py", "docstring": docstring},
        {"name": "build_query", "file_path": "a.py", "docstring": docstring},
    ])
    from determined.agent.agent_tools import find_duplicates
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.80"})
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    assert rows == 0


def test_find_duplicates_threshold_respected():
    """At threshold=0.99 no pair should be stored for near-but-not-identical text."""
    conn = _make_db([
        {"name": "process_payment", "file_path": "a.py",
         "docstring": "Process a credit card payment and return transaction id."},
        {"name": "handle_payment",  "file_path": "b.py",
         "docstring": "Handle a payment request and store the result in the database."},
    ])
    from determined.agent.agent_tools import find_duplicates
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.99"})
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='reconciliation_finding'"
    ).fetchone()[0]
    assert rows == 0


# ---------------------------------------------------------------------------
# list_reconciliation_findings
# ---------------------------------------------------------------------------

def test_list_reconciliation_findings_empty():
    conn = _make_db([])
    from determined.agent.agent_tools import list_reconciliation_findings
    result = list_reconciliation_findings(_FakeAssessor(conn), {})
    assert "run find_duplicates" in result


def test_list_reconciliation_findings_shows_stored_pairs():
    docstring = "Convert temperature from Celsius to Fahrenheit."
    conn = _make_db([
        {"name": "celsius_to_f",  "file_path": "a.py", "docstring": docstring},
        {"name": "c_to_fahrenheit", "file_path": "b.py", "docstring": docstring},
    ])
    from determined.agent.agent_tools import find_duplicates, list_reconciliation_findings
    find_duplicates(_FakeAssessor(conn), {"threshold": "0.85"})
    result = list_reconciliation_findings(_FakeAssessor(conn), {})
    assert "celsius_to_f" in result or "c_to_fahrenheit" in result


def test_list_reconciliation_findings_min_score_filter():
    """min_score should filter out low-scoring pairs."""
    conn = _make_db([])
    # Insert a fake pair with score 0.50
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at) "
        "VALUES (?, 'reconciliation_finding', ?, 'ai-generated', '2026-01-01T00:00:00+00:00')",
        (
            "duplicate::foo@a.py::bar@b.py",
            json.dumps({"symbol_a": "foo", "file_a": "a.py",
                        "symbol_b": "bar", "file_b": "b.py", "score": 0.50}),
        ),
    )
    conn.commit()
    from determined.agent.agent_tools import list_reconciliation_findings
    result_all  = list_reconciliation_findings(_FakeAssessor(conn), {"min_score": "0.0"})
    result_high = list_reconciliation_findings(_FakeAssessor(conn), {"min_score": "0.90"})
    assert "foo" in result_all
    assert "run find_duplicates" in result_high or "foo" not in result_high
