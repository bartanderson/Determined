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
