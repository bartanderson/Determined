"""Regression tests for RM19 Pass 3: find_primitive_gaps primitive discovery."""
import json
import sqlite3
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(edges: list[dict]) -> sqlite3.Connection:
    """In-memory corpus DB with graph_edges and knowledge_artifacts tables."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller TEXT NOT NULL,
            callee TEXT NOT NULL,
            caller_file TEXT,
            line_number INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0
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
    for e in edges:
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
            (e["caller"], e["callee"], e.get("file", "x.py")),
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
# VALID_KINDS includes primitive_gap
# ---------------------------------------------------------------------------

def test_primitive_gap_in_valid_kinds():
    from determined.intent.knowledge_artifact import VALID_KINDS
    assert "primitive_gap" in VALID_KINDS


# ---------------------------------------------------------------------------
# find_primitive_gaps -- basic behaviour
# ---------------------------------------------------------------------------

def test_find_primitive_gaps_empty_graph():
    conn = _make_db([])
    from determined.agent.agent_tools import find_primitive_gaps
    result = find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 2})
    assert "no callee pairs" in result or "0 patterns" in result or "min_callers" in result


def test_find_primitive_gaps_below_threshold():
    """Pair appearing in only 2 callers should not surface at min_callers=3."""
    edges = [
        {"caller": "fn_x", "callee": "validate"},
        {"caller": "fn_x", "callee": "log_event"},
        {"caller": "fn_y", "callee": "validate"},
        {"caller": "fn_y", "callee": "log_event"},
    ]
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    result = find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    assert "no callee pairs" in result or "min_callers" in result
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    assert rows == 0


def test_find_primitive_gaps_detects_pattern():
    """Pair called by 3 independent callers should be surfaced and stored."""
    edges = [
        {"caller": "handler_a", "callee": "validate_input"},
        {"caller": "handler_a", "callee": "log_event"},
        {"caller": "handler_b", "callee": "validate_input"},
        {"caller": "handler_b", "callee": "log_event"},
        {"caller": "handler_c", "callee": "validate_input"},
        {"caller": "handler_c", "callee": "log_event"},
    ]
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    result = find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    assert "validate_input" in result
    assert "log_event" in result
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    assert rows >= 1


def test_find_primitive_gaps_artifact_content_valid_json():
    """Stored primitive_gap content must be valid JSON with required keys."""
    edges = [
        {"caller": f"caller_{i}", "callee": "save_record"} for i in range(4)
    ] + [
        {"caller": f"caller_{i}", "callee": "emit_event"} for i in range(4)
    ]
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchall()
    assert len(rows) >= 1
    for (content,) in rows:
        d = json.loads(content)
        assert "callee_a" in d
        assert "callee_b" in d
        assert "caller_count" in d
        assert "callers_sample" in d
        assert d["caller_count"] >= 3


def test_find_primitive_gaps_idempotent():
    """Running twice does not double-store patterns."""
    edges = [
        {"caller": f"svc_{i}", "callee": "authenticate"} for i in range(3)
    ] + [
        {"caller": f"svc_{i}", "callee": "audit_log"} for i in range(3)
    ]
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    count_first = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    result2 = find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    count_second = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    assert count_first == count_second
    assert "already recorded" in result2


def test_find_primitive_gaps_clear_resets():
    """clear=True deletes existing artifacts and rescans."""
    edges = [
        {"caller": f"mod_{i}", "callee": "parse_config"} for i in range(3)
    ] + [
        {"caller": f"mod_{i}", "callee": "load_schema"} for i in range(3)
    ]
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    count_before = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3, "clear": True})
    count_after = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    assert count_after == count_before


def test_find_primitive_gaps_excludes_dotted_callees():
    """Dotted names (external/method refs like obj.method) are excluded."""
    edges = [
        {"caller": f"fn_{i}", "callee": "requests.get"} for i in range(5)
    ] + [
        {"caller": f"fn_{i}", "callee": "json.loads"} for i in range(5)
    ]
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    result = find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    assert rows == 0


def test_find_primitive_gaps_ranked_by_caller_count():
    """Pairs with more shared callers appear first in output."""
    edges = (
        [{"caller": f"x_{i}", "callee": "common_a"} for i in range(5)]
        + [{"caller": f"x_{i}", "callee": "common_b"} for i in range(5)]
        + [{"caller": f"y_{i}", "callee": "rare_a"} for i in range(3)]
        + [{"caller": f"y_{i}", "callee": "rare_b"} for i in range(3)]
    )
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    result = find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3})
    # common pair should appear before rare pair
    assert result.index("common_a") < result.index("rare_a")


def test_find_primitive_gaps_limit_respected():
    """limit= caps the number of patterns surfaced."""
    # Create 10 distinct callee pairs each with 3 callers
    edges = []
    for pair_idx in range(10):
        for caller_idx in range(3):
            edges.append({"caller": f"caller_{pair_idx}_{caller_idx}", "callee": f"fn_p{pair_idx}_a"})
            edges.append({"caller": f"caller_{pair_idx}_{caller_idx}", "callee": f"fn_p{pair_idx}_b"})
    conn = _make_db(edges)
    from determined.agent.agent_tools import find_primitive_gaps
    find_primitive_gaps(_FakeAssessor(conn), {"min_callers": 3, "limit": 3})
    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='primitive_gap'"
    ).fetchone()[0]
    assert rows <= 3


def test_find_primitive_gaps_registered_in_tools():
    from determined.agent.agent_tools import TOOLS
    assert "find_primitive_gaps" in TOOLS


def test_find_primitive_gaps_registered_in_registry():
    from determined.agent.tool_registry import REGISTRY
    assert "find_primitive_gaps" in REGISTRY
