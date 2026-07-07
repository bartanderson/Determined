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


# ---------------------------------------------------------------------------
# classify_duplicates -- Pass 2 (RM19)
# ---------------------------------------------------------------------------

def _insert_duplicate_pair(conn, name_a, file_a, name_b, file_b, score=0.92):
    """Insert a duplicate:: reconciliation_finding artifact directly."""
    subj = f"duplicate::{name_a}@{file_a}::{name_b}@{file_b}"
    content = json.dumps({"symbol_a": name_a, "file_a": file_a,
                          "symbol_b": name_b, "file_b": file_b, "score": score})
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at) "
        "VALUES (?, 'reconciliation_finding', ?, 'ai-generated', '2026-01-01T00:00:00+00:00')",
        (subj, content),
    )
    conn.commit()
    return subj


def _make_db_with_graph(functions, edges=None):
    """DB with functions, knowledge_artifacts, graph_edges, and symbol_references."""
    conn = _make_db(functions)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller TEXT NOT NULL,
            callee TEXT NOT NULL,
            caller_file TEXT,
            line_number INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS symbol_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller TEXT NOT NULL,
            callee TEXT NOT NULL,
            file_path TEXT,
            line_number INTEGER DEFAULT 0
        )
    """)
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file, line_number, resolved) VALUES (?,?,?,?,?)",
            (e["caller"], e["callee"], e.get("file", "x.py"), e.get("line", 1), e.get("resolved", 0)),
        )
    conn.commit()
    return conn


def test_classify_duplicates_no_pairs():
    """Returns early with helpful message when no duplicate pairs exist."""
    conn = _make_db_with_graph([])
    from determined.agent.agent_tools import classify_duplicates
    result = classify_duplicates(_FakeAssessor(conn), {})
    assert "run find_duplicates" in result or "all pairs already classified" in result


def test_classify_duplicates_stores_classified_artifact(monkeypatch):
    """A successful LLM response produces a classified:: artifact."""
    conn = _make_db_with_graph([
        {"name": "parse_csv",   "file_path": "a.py", "docstring": "Parse a CSV file and return rows."},
        {"name": "read_csv",    "file_path": "b.py", "docstring": "Read a CSV file and return rows."},
    ])
    _insert_duplicate_pair(conn, "parse_csv", "a.py", "read_csv", "b.py", score=0.93)

    fake_response = json.dumps({
        "reason": "accidental copy",
        "confidence": "high",
        "explanation": "Both functions do the same thing; one is a copy of the other.",
    })
    import determined.agent.llm_client as lc
    monkeypatch.setattr(lc, "chat", lambda msgs, **kw: fake_response)

    from determined.agent.agent_tools import classify_duplicates
    result = classify_duplicates(_FakeAssessor(conn), {})

    assert "1 pairs classified" in result
    rows = conn.execute(
        "SELECT subject, content FROM knowledge_artifacts "
        "WHERE kind='reconciliation_finding' AND subject LIKE 'classified::%'"
    ).fetchall()
    assert len(rows) == 1
    subj, content = rows[0]
    assert subj.startswith("classified::")
    d = json.loads(content)
    assert d["reason"] == "accidental copy"
    assert d["confidence"] == "high"
    assert "symbol_a" in d and "symbol_b" in d


def test_classify_duplicates_idempotent(monkeypatch):
    """Running classify_duplicates twice does not double-store classifications."""
    conn = _make_db_with_graph([
        {"name": "send_email",  "file_path": "a.py", "docstring": "Send an email to the user."},
        {"name": "mail_user",   "file_path": "b.py", "docstring": "Mail a message to the user."},
    ])
    _insert_duplicate_pair(conn, "send_email", "a.py", "mail_user", "b.py", score=0.91)

    fake_response = json.dumps({
        "reason": "historical evolution",
        "confidence": "medium",
        "explanation": "Older API renamed over time.",
    })
    import determined.agent.llm_client as lc
    monkeypatch.setattr(lc, "chat", lambda msgs, **kw: fake_response)

    from determined.agent.agent_tools import classify_duplicates
    classify_duplicates(_FakeAssessor(conn), {})
    count_first = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'classified::%'"
    ).fetchone()[0]

    result2 = classify_duplicates(_FakeAssessor(conn), {})
    count_second = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'classified::%'"
    ).fetchone()[0]
    assert count_first == count_second
    assert "all pairs already classified" in result2


def test_classify_duplicates_llm_unavailable(monkeypatch):
    """When LLM returns None (server down) pairs are skipped, not crashed."""
    conn = _make_db_with_graph([
        {"name": "hash_password", "file_path": "a.py", "docstring": "Hash a password with bcrypt."},
        {"name": "encrypt_pw",    "file_path": "b.py", "docstring": "Encrypt a password using bcrypt."},
    ])
    _insert_duplicate_pair(conn, "hash_password", "a.py", "encrypt_pw", "b.py", score=0.88)

    import determined.agent.llm_client as lc
    monkeypatch.setattr(lc, "chat", lambda msgs, **kw: None)

    from determined.agent.agent_tools import classify_duplicates
    result = classify_duplicates(_FakeAssessor(conn), {})
    assert "skipped" in result
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'classified::%'"
    ).fetchone()[0]
    assert rows == 0


def test_classify_duplicates_subject_filter(monkeypatch):
    """subject= arg limits classification to that one pair."""
    conn = _make_db_with_graph([
        {"name": "fn_a", "file_path": "a.py", "docstring": "Do thing A."},
        {"name": "fn_b", "file_path": "b.py", "docstring": "Do thing B."},
        {"name": "fn_c", "file_path": "c.py", "docstring": "Do thing C."},
        {"name": "fn_d", "file_path": "d.py", "docstring": "Do thing D."},
    ])
    subj1 = _insert_duplicate_pair(conn, "fn_a", "a.py", "fn_b", "b.py", score=0.90)
    _insert_duplicate_pair(conn, "fn_c", "c.py", "fn_d", "d.py", score=0.90)

    import determined.agent.llm_client as lc
    monkeypatch.setattr(lc, "chat", lambda msgs, **kw: json.dumps({
        "reason": "performance optimization",
        "confidence": "low",
        "explanation": "One is faster.",
    }))

    from determined.agent.agent_tools import classify_duplicates
    classify_duplicates(_FakeAssessor(conn), {"subject": subj1})

    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'classified::%'"
    ).fetchone()[0]
    assert rows == 1   # only subj1 classified


def test_classify_duplicates_malformed_llm_json(monkeypatch):
    """Malformed LLM JSON is handled gracefully; artifact still stored with fallback."""
    conn = _make_db_with_graph([
        {"name": "load_config",  "file_path": "a.py", "docstring": "Load YAML config from disk."},
        {"name": "read_config",  "file_path": "b.py", "docstring": "Read YAML config from file."},
    ])
    _insert_duplicate_pair(conn, "load_config", "a.py", "read_config", "b.py", score=0.89)

    import determined.agent.llm_client as lc
    monkeypatch.setattr(lc, "chat", lambda msgs, **kw: "Sorry, I cannot classify this.")

    from determined.agent.agent_tools import classify_duplicates
    result = classify_duplicates(_FakeAssessor(conn), {})
    # Should still store something (raw text as explanation, reason=unknown)
    rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject LIKE 'classified::%'"
    ).fetchall()
    assert len(rows) == 1
    d = json.loads(rows[0][0])
    assert d["reason"] == "unknown"


def test_classify_duplicates_reason_in_result_output(monkeypatch):
    """Result string includes reason and confidence for each pair."""
    conn = _make_db_with_graph([
        {"name": "fmt_date",  "file_path": "a.py", "docstring": "Format a date as ISO string."},
        {"name": "date_str",  "file_path": "b.py", "docstring": "Convert date to ISO format string."},
    ])
    _insert_duplicate_pair(conn, "fmt_date", "a.py", "date_str", "b.py", score=0.94)

    import determined.agent.llm_client as lc
    monkeypatch.setattr(lc, "chat", lambda msgs, **kw: json.dumps({
        "reason": "genuinely different abstraction",
        "confidence": "medium",
        "explanation": "One handles timezone-aware dates, the other is naive.",
    }))

    from determined.agent.agent_tools import classify_duplicates
    result = classify_duplicates(_FakeAssessor(conn), {})
    assert "genuinely different abstraction" in result
    assert "medium" in result


def test_classify_duplicates_registered_in_tools():
    from determined.agent.agent_tools import TOOLS
    assert "classify_duplicates" in TOOLS


def test_classify_duplicates_registered_in_registry():
    from determined.agent.tool_registry import REGISTRY
    assert "classify_duplicates" in REGISTRY
