# tests/regression/test_export_context.py
#
# Mechanism tests for export_context and its complexity signal helpers.
# Uses in-memory SQLite fixtures — no live corpus required.

import json
import sqlite3
import pytest

from determined.agent.export_context import (
    _complexity_score,
    _build_packet,
    _sessions,
    export_context,
    export_context_append,
    export_context_dump,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_db(stubs=None, non_stubs=None, classes=None, edges=None):
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE functions (
            name TEXT, file_path TEXT, line_number INTEGER,
            docstring TEXT, param_types_json TEXT, return_type TEXT,
            is_stub INTEGER DEFAULT 0, is_tool INTEGER DEFAULT 0,
            decorators_json TEXT, arguments_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE classes (
            name TEXT, file_path TEXT,
            base_classes_json TEXT, docstring TEXT, methods_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT, callee TEXT, caller_file TEXT,
            edge_type TEXT DEFAULT 'static', resolved INTEGER DEFAULT 0,
            source_id TEXT, target_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE files (file_path TEXT, line_count INTEGER)
    """)
    for s in (stubs or []):
        conn.execute(
            "INSERT INTO functions VALUES (?,?,?,?,?,?,1,0,NULL,NULL)",
            (s.get("name"), s.get("file_path", "world/test.py"),
             s.get("line_number", 10), s.get("docstring"),
             json.dumps(s.get("params", {})), s.get("return_type"))
        )
    for n in (non_stubs or []):
        conn.execute(
            "INSERT INTO functions VALUES (?,?,?,?,?,?,0,0,NULL,NULL)",
            (n.get("name"), n.get("file_path", "world/test.py"),
             n.get("line_number", 1), n.get("docstring"),
             json.dumps(n.get("params", {})), n.get("return_type"))
        )
    for c in (classes or []):
        conn.execute(
            "INSERT INTO classes VALUES (?,?,?,?,?)",
            (c.get("name"), c.get("file_path", "world/test.py"),
             json.dumps(c.get("base_classes", [])),
             c.get("docstring"), json.dumps(c.get("methods", [])))
        )
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges VALUES (?,?,NULL,'static',?,NULL,NULL)",
            (e.get("caller", ""), e.get("callee", ""), int(e.get("resolved", 0)))
        )
    conn.commit()
    return conn


class _FakeOracle:
    def __init__(self, conn):
        self.conn = conn

    def get_project_root(self):
        return "C:/fake"


class _FakeAssessor:
    def __init__(self, conn):
        self.oracle = _FakeOracle(conn)


# ---------------------------------------------------------------------------
# _complexity_score
# ---------------------------------------------------------------------------

def test_complexity_score_returns_float_and_signals():
    conn = _make_db(stubs=[{
        "name": "my_stub", "docstring": "does something",
        "file_path": "world/x.py",
    }])
    oracle = _FakeOracle(conn)
    brief = {
        "symbol": "my_stub", "score": 0.8, "signature": "def my_stub():",
        "callers": [], "siblings": [], "type_defs": [], "intent_text": None,
    }
    score, signals = _complexity_score(brief, oracle)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
    assert "caller_complexity" in signals
    assert "low_confidence" in signals
    assert "unresolved_ratio" in signals
    assert "type_missing" in signals
    assert "sibling_missing" in signals


def test_complexity_score_high_confidence_lowers_score():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    high_conf = {
        "symbol": "fn", "score": 0.95, "signature": "def fn():",
        "callers": [], "siblings": [{"name": "sib", "body_preview": "x"}],
        "type_defs": [], "intent_text": None,
    }
    low_conf = dict(high_conf, score=0.1)
    score_high, _ = _complexity_score(high_conf, oracle)
    score_low, _ = _complexity_score(low_conf, oracle)
    assert score_low > score_high


def test_complexity_score_sibling_missing_increases_score():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    base = {
        "symbol": "fn", "score": 0.5, "signature": "def fn():",
        "callers": [], "type_defs": [], "intent_text": None,
    }
    with_sibling = dict(base, siblings=[{"name": "sib", "body_preview": "x"}])
    without_sibling = dict(base, siblings=[])
    score_with, _ = _complexity_score(with_sibling, oracle)
    score_without, _ = _complexity_score(without_sibling, oracle)
    assert score_without > score_with


def test_complexity_score_unresolved_edges_increase_score():
    # All unresolved edges
    conn_unresolved = _make_db(
        stubs=[{"name": "fn"}],
        edges=[{"caller": "fn", "callee": "other", "resolved": 0}],
    )
    # All resolved
    conn_resolved = _make_db(
        stubs=[{"name": "fn"}],
        edges=[{"caller": "fn", "callee": "other", "resolved": 1}],
    )
    base_brief = {
        "symbol": "fn", "score": 0.5, "signature": "def fn():",
        "callers": [], "siblings": [], "type_defs": [], "intent_text": None,
    }
    score_unresolved, _ = _complexity_score(base_brief, _FakeOracle(conn_unresolved))
    score_resolved, _ = _complexity_score(base_brief, _FakeOracle(conn_resolved))
    assert score_unresolved > score_resolved


# ---------------------------------------------------------------------------
# _build_packet — structure checks
# ---------------------------------------------------------------------------

def test_build_packet_contains_all_four_sections():
    conn = _make_db(
        stubs=[{"name": "my_stub", "docstring": "does x", "file_path": "w/x.py"}],
        non_stubs=[{"name": "caller_fn", "file_path": "w/x.py"}],
    )
    oracle = _FakeOracle(conn)
    brief = {
        "symbol": "my_stub",
        "actionable": True,
        "classification": "design-intent-stated",
        "score": 0.75,
        "file": "x.py",
        "file_path": "w/x.py",
        "line_number": 10,
        "signature": "def my_stub() -> dict:",
        "intent_text": "Compute the state",
        "body_shape": None,
        "callers": [{"name": "caller_fn", "file": "x.py", "body": "    x = my_stub()\n    return x['key']"}],
        "siblings": [],
        "concepts": {},
        "return_type": "dict",
        "return_shape": {"confidence": "STRONG", "hints": ['["key"]']},
        "type_defs": [],
    }
    packet = _build_packet(brief, oracle)
    assert "FUNCTION UNDER ANALYSIS" in packet
    assert "NEIGHBOR CONTEXT" in packet
    assert "COMPLEXITY SCORE" in packet
    assert "TOOL API MANIFEST" in packet


def test_build_packet_includes_symbol_and_signature():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    brief = {
        "symbol": "get_encounter_context",
        "actionable": True,
        "classification": "design-intent-stated",
        "score": 0.8,
        "file": "encounter.py",
        "file_path": "world/encounter.py",
        "line_number": 42,
        "signature": "def get_encounter_context(self) -> dict:",
        "intent_text": None,
        "body_shape": None,
        "callers": [],
        "siblings": [],
        "concepts": {},
        "return_type": "dict",
        "return_shape": {"confidence": "NONE", "hints": []},
        "type_defs": [],
    }
    packet = _build_packet(brief, oracle)
    assert "get_encounter_context" in packet
    assert "def get_encounter_context(self) -> dict:" in packet


def test_build_packet_shows_tier_label():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    # Low confidence + no sibling → high complexity → TIER 2
    brief = {
        "symbol": "fn", "actionable": True,
        "classification": "design-intent-stated", "score": 0.1,
        "file": "x.py", "file_path": "w/x.py", "line_number": 1,
        "signature": "def fn():", "intent_text": None, "body_shape": None,
        "callers": [], "siblings": [], "concepts": {},
        "return_type": None, "return_shape": {"confidence": "NONE", "hints": []},
        "type_defs": [],
    }
    packet = _build_packet(brief, oracle)
    assert "TIER" in packet


def test_build_packet_includes_tool_manifest_tools():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    brief = {
        "symbol": "fn", "actionable": True,
        "classification": "design-intent-stated", "score": 0.5,
        "file": "x.py", "file_path": "w/x.py", "line_number": 1,
        "signature": "def fn():", "intent_text": None, "body_shape": None,
        "callers": [], "siblings": [], "concepts": {},
        "return_type": None, "return_shape": {"confidence": "NONE", "hints": []},
        "type_defs": [],
    }
    packet = _build_packet(brief, oracle)
    assert "classify_stub" in packet
    assert "blast_radius" in packet
    assert "sketch_stub" in packet


# ---------------------------------------------------------------------------
# export_context entry point
# ---------------------------------------------------------------------------

def test_export_context_requires_symbol():
    conn = _make_db()
    assessor = _FakeAssessor(conn)
    result = export_context(assessor, {})
    assert result.startswith("ERROR")


def test_export_context_not_found():
    conn = _make_db()
    assessor = _FakeAssessor(conn)
    result = export_context(assessor, {"symbol": "nonexistent"})
    assert "export_context" in result


def test_export_context_non_actionable_stub():
    conn = _make_db(stubs=[{"name": "concept_stub", "docstring": "not needed"}])
    assessor = _FakeAssessor(conn)
    # concept-not-applicable → not actionable → no packet
    result = export_context(assessor, {"symbol": "concept_stub"})
    assert "Not actionable" in result or "export_context" in result


# ---------------------------------------------------------------------------
# Session accumulator
# ---------------------------------------------------------------------------

def _make_actionable_stub_db():
    return _make_db(stubs=[{
        "name": "do_thing",
        "docstring": "Implement the thing. Will be built when subsystem is ready.",
        "file_path": "engine/core.py",
    }])


def test_export_context_starts_session():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    export_context(assessor, {"symbol": "do_thing"})
    key = ("", "do_thing")
    assert key in _sessions
    assert _sessions[key].symbol == "do_thing"
    assert _sessions[key].initial_packet != ""
    assert _sessions[key].entries == []


def test_export_context_resets_session():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    export_context(assessor, {"symbol": "do_thing"})
    # Manually add a fake entry so we can confirm it gets cleared on re-call.
    from determined.agent.export_context import _SessionEntry
    _sessions[("", "do_thing")].entries.append(
        _SessionEntry(source="user_supplied", tool="", args={},
                      chunk="old chunk", timestamp="2026-01-01T00:00:00")
    )
    assert len(_sessions[("", "do_thing")].entries) == 1
    export_context(assessor, {"symbol": "do_thing"})
    assert _sessions[("", "do_thing")].entries == []


def test_export_context_append_no_session():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    result = export_context_append(assessor, {"symbol": "do_thing", "tool": "list_stubs", "tool_args": {}})
    assert "ERROR" in result
    assert "export_context" in result


def test_export_context_append_requires_symbol():
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    result = export_context_append(assessor, {})
    assert result.startswith("ERROR")


def test_export_context_append_user_supplied():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    export_context(assessor, {"symbol": "do_thing"})
    chunk = export_context_append(assessor, {
        "symbol": "do_thing",
        "content": "The LLM said: implement using a queue.",
    })
    assert "USER-SUPPLIED" in chunk
    assert "queue" in chunk
    session = _sessions[("", "do_thing")]
    assert len(session.entries) == 1
    assert session.entries[0].source == "user_supplied"


def test_export_context_append_unknown_tool():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    export_context(assessor, {"symbol": "do_thing"})
    result = export_context_append(assessor, {
        "symbol": "do_thing",
        "tool": "nonexistent_tool",
        "tool_args": {},
    })
    assert "ERROR" in result


def test_export_context_dump_no_session():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    result = export_context_dump(assessor, {"symbol": "do_thing"})
    assert "ERROR" in result


def test_export_context_dump_empty_session():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    export_context(assessor, {"symbol": "do_thing"})
    result = export_context_dump(assessor, {"symbol": "do_thing"})
    assert "SESSION LOG" in result
    assert "FUNCTION UNDER ANALYSIS" in result
    assert "No follow-up steps" in result


def test_export_context_dump_with_entries():
    _sessions.clear()
    conn = _make_actionable_stub_db()
    assessor = _FakeAssessor(conn)
    export_context(assessor, {"symbol": "do_thing"})
    export_context_append(assessor, {
        "symbol": "do_thing",
        "content": "Response from external LLM.",
    })
    result = export_context_dump(assessor, {"symbol": "do_thing"})
    assert "SESSION LOG" in result
    assert "FUNCTION UNDER ANALYSIS" in result
    assert "USER-SUPPLIED" in result
    assert "Response from external LLM" in result
    assert "Steps: 1" in result
