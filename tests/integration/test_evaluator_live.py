# tests/regression/test_evaluator_live.py
#
# Live LLM smoke tests for the evaluate kernel.
# Skipped automatically if the 3B llama-server is not running.
# Run manually: pytest tests/regression/test_evaluator_live.py -v -s

import pytest

from determined.agent import llm_client
from determined.agent.evaluator import evaluate, VALID_VERDICTS


@pytest.fixture(scope="module", autouse=True)
def require_llm():
    if not llm_client.is_available():
        pytest.skip("3B llama-server not running on port 8080")


class TestEvaluateLive:
    def test_known_violates(self):
        """Claim that clearly violates the evidence should return VIOLATES."""
        j = evaluate(
            claim="The AI integration module directly updates player position in the database.",
            evidence_items=[
                "AI is voice and judgment only. It must never mutate game state directly.",
                "Only the adjudicator may write to game state tables.",
            ],
            question="Does this observation violate a documented design constraint?",
        )
        assert j.verdict in VALID_VERDICTS
        # This is a strong case — expect VIOLATES or at least not UNRELATED
        assert j.verdict != "UNRELATED", f"Expected violation verdict, got: {j}"
        assert j.confidence > 0.3, f"Confidence too low: {j}"
        print(f"\nVIOLATES case: {j}")

    def test_known_confirms(self):
        """Claim that is consistent with evidence should return CONFIRMS or EXPLAINS."""
        j = evaluate(
            claim="The AI module only reads game state to produce a narrative response, and never writes to any table.",
            evidence_items=[
                "AI is voice and judgment only. It must never mutate game state directly.",
                "Read-only access to state is acceptable for AI reasoning.",
            ],
            question="Is this observation consistent with the design constraints, or does it violate them?",
        )
        assert j.verdict in VALID_VERDICTS
        assert j.verdict in ("CONFIRMS", "EXPLAINS"), f"Expected confirmation verdict, got: {j}"
        print(f"\nCONFIRMS case: {j}")

    def test_unrelated_evidence_yields_unrelated(self):
        """Evidence unrelated to the claim should yield UNRELATED."""
        j = evaluate(
            claim="The pathfinding module uses A* search over a hex grid.",
            evidence_items=[
                "Resource cleanup must happen in the same scope that acquired the resource.",
                "Logging must use structured JSON format, not plain strings.",
            ],
            question="Does this observation violate or confirm any of the listed constraints?",
        )
        assert j.verdict in VALID_VERDICTS
        # UNRELATED or UNCERTAIN are both acceptable here
        assert j.verdict in ("UNRELATED", "UNCERTAIN"), f"Expected unrelated verdict, got: {j}"
        print(f"\nUNRELATED case: {j}")
