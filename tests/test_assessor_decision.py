# tests/test_assessor_decision.py
#
# Boundary fuzz test: severity -> LLM gating decision in Assessor.ask().
# Uses a fake EpistemicPolicy so the math is isolated from the decision logic.
# Patches llm_client so no real server is required.

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from determined.assessor.assessor import Assessor


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


def _make_assessor_with_severity(severity, structure_risk=0.0, integrity_risk=0.0):
    """Patches EpistemicPolicy to return a fixed directive."""
    from determined.assessor.epistemic_policy import EpistemicDirective

    fake_directive = EpistemicDirective(
        severity=severity,
        risk_vector={
            "structure": structure_risk,
            "integrity": integrity_risk,
            "stability": 0.0,
            "scale": 0.0,
            "complexity": 0.0,
            "completeness": 0.0,
        },
        required_surfaces=["INTEGRITY"],
    )

    class FakePolicy:
        def analyze(self, **kwargs):
            return fake_directive

    assessor = Assessor(_make_oracle())

    # Patch run_algebra to return a minimal result dict
    assessor.session = lambda: SimpleNamespace(
        run_algebra=lambda text, views: {
            "text": text,
            "intent": "general_query",
            "oracle": SimpleNamespace(expanded=[]),
            "compiled_ast": None,
            "compiler_explanation": "",
            "algebra_result": {},
        }
    )

    # Patch all_views to return minimal stubs the real policy would need
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

    return assessor, FakePolicy()


@pytest.mark.parametrize("severity,expect_llm", [
    (0.00, False),
    (0.10, False),
    (0.15, False),   # boundary: threshold is >, not >=
    (0.16, True),
    (0.50, True),
    (0.90, True),
])
def test_llm_gating_boundary(severity, expect_llm):
    assessor, fake_policy = _make_assessor_with_severity(severity)

    with patch("determined.assessor.assessor.EpistemicPolicy", return_value=fake_policy), \
         patch("determined.assessor.assessor.llm_client") as mock_llm:

        mock_llm.is_available.return_value = True
        mock_llm.chat.return_value = "narrative response"

        result = assessor.ask("test query")

        if expect_llm:
            assert result.get("narrative") == "narrative response"
        else:
            assert result.get("narrative") is None
