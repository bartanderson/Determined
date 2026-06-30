# tests/test_hard_block_regression.py
#
# Safety invariant: when integrity AND structure risk both breach their
# hard-block thresholds simultaneously, Assessor.ask() must never call
# the LLM regardless of severity or router intent.
#
# This test must never be removed or weakened. It is the regression guard
# for the single most important invariant in the decision layer.

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from determined.assessor.assessor import Assessor
from determined.assessor.epistemic_policy import (
    EpistemicDirective,
    HARD_BLOCK_INTEGRITY,
    HARD_BLOCK_STRUCTURE,
)


def _make_oracle():
    oracle = MagicMock()
    oracle.conn = MagicMock()
    oracle.conn.execute.return_value.fetchall.return_value = []
    oracle.get_snapshot_graph.return_value = SimpleNamespace(edges=[])
    oracle.builtin_symbols.return_value = set()
    oracle.discover_seed_symbols.return_value = []
    oracle.get_edge_maps.return_value = ({}, {})
    oracle.file_count.return_value = 0
    oracle.symbol_reference_count.return_value = 0
    oracle.bucket_summary.return_value = {}
    oracle.file_reference_map.return_value = {}
    oracle.symbol_module_map.return_value = {}
    oracle.get_project_root.return_value = None
    return oracle


def _hard_block_directive():
    """Directive that triggers hard block: both thresholds breached."""
    return EpistemicDirective(
        severity=0.99,
        risk_vector={
            "structure":    HARD_BLOCK_STRUCTURE + 0.05,  # over threshold
            "integrity":    HARD_BLOCK_INTEGRITY + 0.01,  # over threshold
            "stability":    0.0,
            "scale":        0.0,
            "complexity":   0.0,
            "completeness": 0.0,
        },
        required_surfaces=["INTEGRITY", "STRUCTURE"],
    )


def test_hard_block_prevents_llm_call():
    """LLM must not be called when both hard-block thresholds are breached."""
    fake_policy = MagicMock()
    fake_policy.analyze.return_value = _hard_block_directive()

    assessor = Assessor(_make_oracle())

    assessor.session = lambda: SimpleNamespace(
        run_algebra=lambda text, views: {
            "text": text,
            "intent": "general_query",
            "oracle": SimpleNamespace(seeds=[], expanded=[]),
            "compiled_ast": None,
            "compiler_explanation": "",
            "algebra_result": {},
        }
    )

    from determined.truth.views import StructureView, StabilityView, IntegrityView, SystemSummaryView, RoleView
    assessor.all_views = lambda: {
        "STRUCTURE": StructureView(edges=[], adjacency={}, hotspots=[]),
        "INTEGRITY": IntegrityView(errors=[], warnings=[], db_mismatches=[]),
        "STABILITY": StabilityView(stable_contracts=[], unstable_contracts=[], drift_signals=[]),
        "SUMMARY": SystemSummaryView(edge_count=0, file_count=0, metrics={}),
        "ROLE": RoleView(files=[], totals={}),
        "SUBSYSTEM": None,
        "INTENT": None,
    }

    llm_was_called = []

    with patch("determined.assessor.assessor.EpistemicPolicy", return_value=fake_policy), \
         patch("determined.assessor.assessor.llm_client") as mock_llm:

        mock_llm.is_available.return_value = True
        mock_llm.chat.side_effect = lambda *a, **kw: llm_was_called.append(True) or "SHOULD_NOT_RUN"

        result = assessor.ask("anything")

    assert not llm_was_called, "LLM was called despite hard block"
    assert result["narrative"] is None
    assert result["narrative_skipped_reason"] == "hard_block"


def test_hard_block_requires_both_thresholds():
    """Only integrity over threshold (structure fine) should NOT trigger hard block."""
    fake_policy = MagicMock()
    fake_policy.analyze.return_value = EpistemicDirective(
        severity=0.99,
        risk_vector={
            "structure":    HARD_BLOCK_STRUCTURE - 0.05,  # under threshold
            "integrity":    HARD_BLOCK_INTEGRITY + 0.01,  # over threshold
            "stability":    0.0,
            "scale":        0.0,
            "complexity":   0.0,
            "completeness": 0.0,
        },
        required_surfaces=["INTEGRITY"],
    )

    assessor = Assessor(_make_oracle())
    assessor.session = lambda: SimpleNamespace(
        run_algebra=lambda text, views: {
            "text": text,
            "intent": "general_query",
            "oracle": SimpleNamespace(seeds=[], expanded=[]),
            "compiled_ast": None,
            "compiler_explanation": "",
            "algebra_result": {},
        }
    )

    from determined.truth.views import StructureView, StabilityView, IntegrityView, SystemSummaryView, RoleView
    assessor.all_views = lambda: {
        "STRUCTURE": StructureView(edges=[], adjacency={}, hotspots=[]),
        "INTEGRITY": IntegrityView(errors=[], warnings=[], db_mismatches=[]),
        "STABILITY": StabilityView(stable_contracts=[], unstable_contracts=[], drift_signals=[]),
        "SUMMARY": SystemSummaryView(edge_count=0, file_count=0, metrics={}),
        "ROLE": RoleView(files=[], totals={}),
        "SUBSYSTEM": None,
        "INTENT": None,
    }

    with patch("determined.assessor.assessor.EpistemicPolicy", return_value=fake_policy), \
         patch("determined.assessor.assessor.llm_client") as mock_llm:

        mock_llm.is_available.return_value = True
        mock_llm.chat.return_value = "narrative"

        result = assessor.ask("anything")

    # Not hard blocked, severity high enough -> LLM should have been called
    assert result.get("narrative") == "narrative"
