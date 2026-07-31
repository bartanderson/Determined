# tests/regression/test_domain_analyst.py
# Unit tests for local_agent analyst functions: _build_wiring_gaps, build_domain_analysis,
# _is_domain_analysis_question routing.

import types
import pytest
from unittest.mock import MagicMock


def _make_oracle(stubs_by_name, callers_by_callee):
    """
    Build a mock oracle whose conn.execute returns canned data.
    stubs_by_name: {name: (is_stub, file_path)}
    callers_by_callee: {name: [caller1, caller2, ...]}
    """
    def execute(sql, params=()):
        mock_result = MagicMock()
        # is_stub + file_path lookup
        if "SELECT is_stub, file_path FROM functions WHERE name" in sql:
            name = params[0]
            row = stubs_by_name.get(name)
            mock_result.fetchone.return_value = row
            return mock_result
        # caller count lookup
        if "SELECT COUNT(*)" in sql and "graph_edges" in sql:
            name = params[0]
            callers = callers_by_callee.get(name, [])
            mock_result.fetchone.return_value = (len(callers),)
            return mock_result
        # caller list lookup
        if "SELECT DISTINCT caller FROM graph_edges" in sql:
            name = params[0]
            callers = callers_by_callee.get(name, [])
            mock_result.fetchall.return_value = [(c,) for c in callers]
            return mock_result
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = None
        return mock_result

    oracle = MagicMock()
    oracle.conn.execute.side_effect = execute
    return oracle


# ── _build_wiring_gaps ────────────────────────────────────────────────────────

def test_wiring_gaps_connected_stubs():
    """Stubs with callers produce 'caller → stub (unimplemented)' entries."""
    from determined.agent.local_agent import _build_wiring_gaps

    enrichment = {
        "stubs": ["resolve_encounter (encounter.py, 2 caller(s) waiting)"],
        "complete": [], "orphaned": [], "design_notes": [],
    }
    oracle = _make_oracle(
        {"resolve_encounter": (True, "encounter.py")},
        {"resolve_encounter": ["handle_action", "run_combat"]},
    )
    result = _build_wiring_gaps(enrichment, oracle)
    assert "resolve_encounter" in result
    assert "unimplemented" in result


def test_wiring_gaps_isolated_stubs():
    """Stubs with no callers are reported as 'not yet connected', not silently skipped."""
    from determined.agent.local_agent import _build_wiring_gaps

    enrichment = {
        "stubs": ["start_encounter (encounter.py, not yet called)"],
        "complete": [], "orphaned": [], "design_notes": [],
    }
    oracle = _make_oracle(
        {"start_encounter": (True, "encounter.py")},
        {},
    )
    result = _build_wiring_gaps(enrichment, oracle)
    assert "start_encounter" in result
    assert "not yet connected" in result


def test_wiring_gaps_multiple_isolated_stubs():
    """Multiple isolated stubs: first named, rest counted."""
    from determined.agent.local_agent import _build_wiring_gaps

    enrichment = {
        "stubs": [
            "start_encounter (encounter.py, not yet called)",
            "end_encounter (encounter.py, not yet called)",
            "resolve_encounter (encounter.py, not yet called)",
        ],
        "complete": [], "orphaned": [], "design_notes": [],
    }
    oracle = _make_oracle({}, {})
    result = _build_wiring_gaps(enrichment, oracle)
    assert "start_encounter" in result
    assert "2 other stub(s)" in result


def test_wiring_gaps_no_stubs():
    """No stubs → 'No direct wiring gaps found'."""
    from determined.agent.local_agent import _build_wiring_gaps

    enrichment = {"stubs": [], "complete": [], "orphaned": [], "design_notes": []}
    oracle = _make_oracle({}, {})
    result = _build_wiring_gaps(enrichment, oracle)
    assert "No direct wiring gaps" in result


def test_wiring_gaps_mixed():
    """Both connected and isolated stubs in one call."""
    from determined.agent.local_agent import _build_wiring_gaps

    enrichment = {
        "stubs": [
            "stub_a (file.py, 1 caller(s) waiting)",
            "stub_b (file.py, not yet called)",
        ],
        "complete": [], "orphaned": [], "design_notes": [],
    }
    oracle = _make_oracle(
        {"stub_a": (True, "file.py"), "stub_b": (True, "file.py")},
        {"stub_a": ["some_caller"]},
    )
    result = _build_wiring_gaps(enrichment, oracle)
    assert "stub_a" in result
    assert "stub_b" in result


# ── _is_domain_analysis_question routing ─────────────────────────────────────

def test_domain_routing_state_of():
    """'what is the state of X subsystem?' routes to domain_analyst."""
    from determined.agent.local_agent import _is_domain_analysis_question, _is_survey_needs
    from determined.agent.agent_resolver import detect_heuristic

    q = "what is the state of the encounter subsystem?"
    needs = detect_heuristic(q) or []
    assert _is_domain_analysis_question(q, needs), "domain_analyst should fire"
    # Confirm survey doesn't short-circuit (domain check is first)
    assert not (_is_survey_needs(needs) and not _is_domain_analysis_question(q, needs))


def test_domain_routing_assess():
    """'assess the X subsystem' routes to domain_analyst."""
    from determined.agent.local_agent import _is_domain_analysis_question

    assert _is_domain_analysis_question("assess the encounter subsystem", [])


def test_domain_routing_status_of():
    """'status of X' routes to domain_analyst."""
    from determined.agent.local_agent import _is_domain_analysis_question

    assert _is_domain_analysis_question("what is the status of the trade subsystem?", [])


# ── _is_plan_request routing ──────────────────────────────────────────────────

def test_plan_routing_plan_for():
    from determined.agent.local_agent import _is_plan_request
    assert _is_plan_request("plan for encounter")
    assert _is_plan_request("build plan for trade")
    assert _is_plan_request("generate plan for barter")
    assert _is_plan_request("implementation plan for encounter")


def test_plan_routing_negative():
    from determined.agent.local_agent import _is_plan_request
    assert not _is_plan_request("what is the state of the encounter subsystem?")
    assert not _is_plan_request("show me all stubs")


# ── generate_domain_plan ──────────────────────────────────────────────────────

def _make_assessor_with_db():
    """Build an in-memory assessor mock with a real SQLite connection."""
    import sqlite3
    from determined.intent.workflow_store import ensure_workflow_items_table, ensure_artifact_columns

    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, file_path TEXT)")
    ensure_workflow_items_table(cur)
    ensure_artifact_columns(cur)
    conn.commit()

    assessor = MagicMock()
    assessor._knowledge_conn = conn
    return assessor, conn


def test_generate_domain_plan_callers_waiting():
    """Stubs with callers waiting become next_up items ranked by caller count."""
    from determined.agent.local_agent import generate_domain_plan
    from determined.intent.workflow_store import list_items

    oracle = _make_oracle(
        {
            "_get_encounter_context": (True, "encounter.py"),
            "resolve_flee": (True, "encounter.py"),
        },
        {
            "_get_encounter_context": ["build", "run"],  # 2 callers
            "resolve_flee": ["adjudicate"],              # 1 caller
        },
    )
    # Real search_symbols format: header line (skipped), then "  name (type) in file line N"
    facts = [
        {"tool": "search_symbols", "args": {"query": "encounter"},
         "result": "Symbols matching 'encounter':\n"
                   "  _get_encounter_context (function) in encounter.py line 10\n"
                   "  resolve_flee (function) in encounter.py line 20\n"},
    ]

    assessor, conn = _make_assessor_with_db()
    result = generate_domain_plan("plan for encounter", facts, oracle, assessor)

    assert "added" in result.lower() or "no new items" in result.lower()
    items = list_items(conn, kind="next_up", status="active", limit=20)
    names = [i["subject"] for i in items]
    assert any("_get_encounter_context" in n or "resolve_flee" in n for n in names)


def test_generate_domain_plan_no_stubs():
    """Domain with no stubs produces a clear 'nothing to add' message."""
    from determined.agent.local_agent import generate_domain_plan

    oracle = _make_oracle({}, {})
    facts = [
        {"tool": "search_symbols", "args": {"query": "combat"},
         "result": "Symbols matching 'combat':\n"
                   "  fight (function) in combat.py line 5\n"},
    ]
    assessor, _ = _make_assessor_with_db()
    result = generate_domain_plan("plan for combat", facts, oracle, assessor)
    assert "no new items" in result.lower() or "added" in result.lower()


def test_generate_domain_plan_idempotent():
    """Running plan twice does not duplicate items."""
    from determined.agent.local_agent import generate_domain_plan
    from determined.intent.workflow_store import list_items

    oracle = _make_oracle(
        {"_get_encounter_context": (True, "encounter.py")},
        {"_get_encounter_context": ["build"]},
    )
    facts = [
        {"tool": "search_symbols", "args": {"query": "encounter"},
         "result": "Symbols matching 'encounter':\n"
                   "  _get_encounter_context (function) in encounter.py line 10\n"},
    ]
    assessor, conn = _make_assessor_with_db()

    generate_domain_plan("plan for encounter", facts, oracle, assessor)
    generate_domain_plan("plan for encounter", facts, oracle, assessor)

    items = list_items(conn, kind="next_up", status="active", limit=20)
    subjects = [i["subject"] for i in items]
    # No duplicate subjects
    assert len(subjects) == len(set(subjects))


# ── _is_direction_request routing ────────────────────────────────────────────

def test_direction_routing_positive():
    from determined.agent.local_agent import _is_direction_request
    assert _is_direction_request("I implemented _get_encounter_context")
    assert _is_direction_request("I've implemented resolve_flee")
    assert _is_direction_request("I finished _get_combat_context")
    assert _is_direction_request("implemented the resolve_barter stub")
    assert _is_direction_request("done with on_arc_completed")


def test_direction_routing_negative():
    from determined.agent.local_agent import _is_direction_request
    assert not _is_direction_request("plan for encounter")
    assert not _is_direction_request("what is the state of encounter?")
    assert not _is_direction_request("show me all stubs")


# ── generate_direction_update ─────────────────────────────────────────────────

def _make_assessor_with_stubs(functions, edges):
    """
    functions: list of (name, file_path, is_stub)
    edges: list of (caller, callee)
    """
    import sqlite3
    from determined.intent.workflow_store import (
        ensure_workflow_items_table, ensure_artifact_columns, add_item,
    )

    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE functions (name TEXT, file_path TEXT, is_stub INTEGER)"
    )
    cur.executemany("INSERT INTO functions VALUES (?,?,?)", functions)
    cur.execute(
        "CREATE TABLE graph_edges (caller TEXT, callee TEXT)"
    )
    cur.executemany("INSERT INTO graph_edges VALUES (?,?)", edges)
    cur.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, file_path TEXT)")
    ensure_workflow_items_table(cur)
    ensure_artifact_columns(cur)
    conn.commit()

    # Pre-populate a workflow item for the stub
    for name, fpath, is_stub in functions:
        if is_stub:
            add_item(conn, kind="next_up", subject=f"implement: {name}",
                     content="stub", rank=1, provenance="analyst")

    assessor = MagicMock()
    assessor._knowledge_conn = conn
    return assessor, conn


def test_direction_update_marks_done_and_reports_unblocked():
    """Implementing a stub marks it done and reports callers now unblocked."""
    from determined.agent.local_agent import generate_direction_update
    from determined.intent.workflow_store import list_items

    assessor, conn = _make_assessor_with_stubs(
        functions=[
            ("_get_encounter_context", "encounter.py", 1),
            ("trigger_encounter", "encounter.py", 0),
        ],
        edges=[
            ("trigger_encounter", "_get_encounter_context"),
        ],
    )
    oracle = MagicMock()
    oracle.conn = conn

    result = generate_direction_update(
        "I implemented _get_encounter_context", oracle, assessor
    )

    assert "_get_encounter_context" in result
    assert "trigger_encounter" in result or "unblocked" in result.lower()

    # The workflow item should be closed
    active = list_items(conn, status="active", limit=20)
    active_subjects = [i["subject"] for i in active]
    assert not any("_get_encounter_context" in s for s in active_subjects)


def test_direction_update_no_callers():
    """Implementing an isolated stub (no callers) produces a clear 'no chain unblocked' message."""
    from determined.agent.local_agent import generate_direction_update

    assessor, conn = _make_assessor_with_stubs(
        functions=[("resolve_barter", "barter.py", 1)],
        edges=[],
    )
    oracle = MagicMock()
    oracle.conn = conn

    result = generate_direction_update("I finished resolve_barter", oracle, assessor)

    assert "resolve_barter" in result
    assert "no chain unblocked" in result.lower() or "no caller" in result.lower()


def test_direction_update_adjacent_stubs():
    """Reports remaining stubs in the same file as the new frontier."""
    from determined.agent.local_agent import generate_direction_update

    assessor, conn = _make_assessor_with_stubs(
        functions=[
            ("_get_encounter_context", "encounter.py", 1),
            ("_get_flee_context", "encounter.py", 1),
        ],
        edges=[],
    )
    oracle = MagicMock()
    oracle.conn = conn

    result = generate_direction_update(
        "I implemented _get_encounter_context", oracle, assessor
    )

    assert "_get_flee_context" in result


# ── Tier 4: knowledge accumulation ───────────────────────────────────────────

def _make_full_assessor(functions=None, edges=None):
    """In-memory DB with functions + graph_edges + workflow tables + knowledge_artifacts."""
    import sqlite3
    from determined.intent.workflow_store import ensure_workflow_items_table, ensure_artifact_columns

    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, file_path TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS functions (name TEXT, file_path TEXT, is_stub INTEGER)")
    if functions:
        cur.executemany("INSERT INTO functions VALUES (?,?,?)", functions)
    cur.execute("CREATE TABLE IF NOT EXISTS graph_edges (caller TEXT, callee TEXT)")
    if edges:
        cur.executemany("INSERT INTO graph_edges VALUES (?,?)", edges)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS knowledge_artifacts "
        "(id INTEGER PRIMARY KEY, kind TEXT, subject TEXT, content TEXT, provenance TEXT)"
    )
    ensure_workflow_items_table(cur)
    ensure_artifact_columns(cur)
    conn.commit()

    assessor = MagicMock()
    assessor._knowledge_conn = conn
    return assessor, conn


def test_domain_analysis_stores_artifact():
    """build_domain_analysis stores an analyst_run artifact after the first run."""
    from determined.agent.local_agent import build_domain_analysis
    from determined.intent.workflow_store import get_artifact_by_name

    assessor, conn = _make_full_assessor()
    oracle = MagicMock()
    oracle.conn.execute.return_value.fetchall.return_value = []
    oracle.conn.execute.return_value.fetchone.return_value = None

    facts = [
        {"tool": "search_symbols", "args": {"query": "encounter"},
         "result": "Symbols matching 'encounter':\n  do_encounter (function) in encounter.py line 1\n"},
    ]
    build_domain_analysis("what is the state of encounter", facts, oracle, [], assessor=assessor)

    artifact = get_artifact_by_name(conn, "analyst_run:encounter")
    assert artifact is not None
    assert "COMPLETE" in artifact["content"] or "STUBS" in artifact["content"]


def test_domain_analysis_diff_shows_closed_stub():
    """Second run with a stub removed reports it as closed in the delta."""
    from determined.agent.local_agent import build_domain_analysis
    from determined.intent.workflow_store import store_artifact

    assessor, conn = _make_full_assessor()
    oracle = MagicMock()
    oracle.conn.execute.return_value.fetchall.return_value = []
    oracle.conn.execute.return_value.fetchone.return_value = None

    # Seed a prior artifact that had a stub
    prior_text = (
        "1. COMPLETE: (none)\n"
        "2. STUBS: _get_encounter_context (encounter.py, 1 caller(s) waiting)\n"
        "3. ORPHANED: (none)\n4. WIRING GAPS: ...\n5. DESIGN: ...\n6. FIRST STEP: ...\n"
    )
    store_artifact(conn, "analyst_run:encounter", "domain_analyst", prior_text)

    # Current run shows no stubs (stub was implemented)
    facts = [
        {"tool": "search_symbols", "args": {"query": "encounter"},
         "result": "Symbols matching 'encounter':\n  _get_encounter_context (function) in encounter.py line 1\n"},
    ]
    result = build_domain_analysis(
        "what is the state of encounter", facts, oracle, [], assessor=assessor
    )

    assert "Closed" in result or "closed" in result


def test_domain_analysis_no_diff_on_first_run():
    """First run produces no delta prefix."""
    from determined.agent.local_agent import build_domain_analysis

    assessor, conn = _make_full_assessor()
    oracle = MagicMock()
    oracle.conn.execute.return_value.fetchall.return_value = []
    oracle.conn.execute.return_value.fetchone.return_value = None

    facts = []
    result = build_domain_analysis(
        "what is the state of encounter", facts, oracle, [], assessor=assessor
    )

    assert "Since last analyst run" not in result
