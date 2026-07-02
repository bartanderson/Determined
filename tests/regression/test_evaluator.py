# tests/regression/test_evaluator.py
#
# Tests for the evaluate kernel (determined/agent/evaluator.py).
#
# Phase 1 (no LLM, no DB): structure, parsing, edge cases.
# Phase 2 (real LLM): tiny known-answer case, only runs when LLM is available.

import json
import sqlite3

import pytest

from determined.agent.evaluator import (
    Judgment,
    VALID_VERDICTS,
    _parse_judgment,
    evaluate,
    retrieve_evidence,
)


# ---------------------------------------------------------------------------
# Judgment dataclass
# ---------------------------------------------------------------------------

class TestJudgment:
    def test_valid_verdict_accepted(self):
        for v in VALID_VERDICTS:
            j = Judgment(verdict=v, reasoning="ok", confidence=0.8)
            assert j.verdict == v

    def test_invalid_verdict_becomes_uncertain(self):
        j = Judgment(verdict="BOGUS", reasoning="x", confidence=0.5)
        assert j.verdict == "UNCERTAIN"

    def test_confidence_clamped(self):
        j = Judgment(verdict="CONFIRMS", reasoning="x", confidence=2.5)
        assert j.confidence == 1.0
        j2 = Judgment(verdict="CONFIRMS", reasoning="x", confidence=-1.0)
        assert j2.confidence == 0.0

    def test_str_includes_verdict_and_reasoning(self):
        j = Judgment(verdict="VIOLATES", reasoning="breaks the rule", confidence=0.9)
        s = str(j)
        assert "VIOLATES" in s
        assert "breaks the rule" in s


# ---------------------------------------------------------------------------
# _parse_judgment
# ---------------------------------------------------------------------------

class TestParseJudgment:
    def _evidence(self):
        return ["norm A: never mutate state", "norm B: AI is voice only", "norm C: boundary pattern"]

    def test_clean_json(self):
        evidence = self._evidence()
        raw = json.dumps({
            "verdict": "VIOLATES",
            "reasoning": "the code mutates state directly",
            "confidence": 0.85,
            "evidence_indices": [0, 1],
        })
        j = _parse_judgment(raw, evidence)
        assert j.verdict == "VIOLATES"
        assert j.confidence == pytest.approx(0.85)
        assert evidence[0] in j.evidence_used
        assert evidence[1] in j.evidence_used

    def test_json_with_markdown_fences(self):
        evidence = self._evidence()
        raw = "```json\n" + json.dumps({
            "verdict": "CONFIRMS",
            "reasoning": "consistent with boundary rule",
            "confidence": 0.7,
            "evidence_indices": [],
        }) + "\n```"
        j = _parse_judgment(raw, evidence)
        assert j.verdict == "CONFIRMS"

    def test_partial_json_regex_fallback(self):
        evidence = self._evidence()
        raw = '  {"verdict": "EXPLAINS", "reasoning": "design intent", "confidence": 0.6 ... garbage'
        j = _parse_judgment(raw, evidence)
        assert j.verdict == "EXPLAINS"
        assert j.confidence == pytest.approx(0.6)

    def test_garbage_returns_uncertain(self):
        j = _parse_judgment("I cannot determine the relationship.", [])
        assert j.verdict == "UNCERTAIN"
        assert j.confidence == 0.0

    def test_out_of_range_evidence_indices_ignored(self):
        evidence = self._evidence()
        raw = json.dumps({
            "verdict": "UNRELATED",
            "reasoning": "no match",
            "confidence": 0.3,
            "evidence_indices": [99, -1, 0],
        })
        j = _parse_judgment(raw, evidence)
        assert j.verdict == "UNRELATED"
        # Only index 0 is valid
        assert len(j.evidence_used) == 1

    def test_uppercase_normalization(self):
        evidence = self._evidence()
        raw = json.dumps({
            "verdict": "matches_pattern",
            "reasoning": "fits pipeline shape",
            "confidence": 0.75,
            "evidence_indices": [],
        })
        j = _parse_judgment(raw, evidence)
        assert j.verdict == "MATCHES_PATTERN"


# ---------------------------------------------------------------------------
# evaluate() with stub LLM
# ---------------------------------------------------------------------------

class TestEvaluate:
    def _stub_llm(self, response: str):
        """Returns a stub llm_fn that always returns the given response."""
        def fn(prompt: str) -> str:
            return response
        return fn

    def test_returns_judgment(self):
        resp = json.dumps({
            "verdict": "CONFIRMS",
            "reasoning": "the absence is by design",
            "confidence": 0.9,
            "evidence_indices": [0],
        })
        j = evaluate(
            claim="AI has no direct link to movement service",
            evidence_items=["AI is voice/judgment only; it must not mutate state"],
            question="Is this missing connection intentional or a gap?",
            llm_fn=self._stub_llm(resp),
        )
        assert j.verdict == "CONFIRMS"
        assert j.confidence == pytest.approx(0.9)

    def test_empty_claim_returns_uncertain(self):
        j = evaluate(
            claim="   ",
            evidence_items=["some norm"],
            question="anything",
            llm_fn=self._stub_llm("{}"),
        )
        assert j.verdict == "UNCERTAIN"

    def test_no_evidence_returns_unrelated(self):
        j = evaluate(
            claim="AI has no link to navigation",
            evidence_items=[],
            question="is this a gap?",
            llm_fn=self._stub_llm("{}"),
        )
        assert j.verdict == "UNRELATED"

    def test_llm_failure_raises(self):
        with pytest.raises(RuntimeError, match="llama-server"):
            evaluate(
                claim="some claim",
                evidence_items=["some norm"],
                question="anything",
                llm_fn=lambda prompt: None,
            )

    def test_prompt_contains_claim_and_evidence(self):
        """Verify the prompt sent to the LLM includes our inputs."""
        captured = []
        def capturing_llm(prompt: str) -> str:
            captured.append(prompt)
            return json.dumps({"verdict": "UNRELATED", "reasoning": "x",
                               "confidence": 0.5, "evidence_indices": []})

        evaluate(
            claim="unique_claim_marker_xyz",
            evidence_items=["unique_evidence_marker_abc"],
            question="unique_question_marker_def",
            llm_fn=capturing_llm,
        )
        assert captured, "LLM was not called"
        prompt = captured[0]
        assert "unique_claim_marker_xyz" in prompt
        assert "unique_evidence_marker_abc" in prompt
        assert "unique_question_marker_def" in prompt


# ---------------------------------------------------------------------------
# retrieve_evidence() with in-memory DB
# ---------------------------------------------------------------------------

class TestRetrieveEvidence:
    def _make_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE knowledge_artifacts (
                id INTEGER PRIMARY KEY,
                kind TEXT,
                subject TEXT,
                content TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO knowledge_artifacts (kind, subject, content) VALUES (?,?,?)",
            [
                ("design_note", "authority", "AI is voice and judgment only. It must never mutate game state directly."),
                ("design_note", "boundary",  "Movement is owned by the adjudicator, not the AI layer."),
                ("design_note", "lifecycle", "Resource cleanup must happen in the same scope that acquired the resource."),
                ("pattern",     "pipeline",  "A pipeline pattern: A -> B -> C where each step transforms without branching."),
                ("pattern",     "adjudicator", "Adjudicator pattern: receives intent, applies rules, emits action."),
            ]
        )
        conn.commit()
        return conn

    def test_returns_list_of_strings(self):
        conn = self._make_db()
        results = retrieve_evidence(
            "AI authority boundary movement",
            conn,
            surfaces=["design_note"],
        )
        assert isinstance(results, list)
        assert all(isinstance(r, str) for r in results)

    def test_surface_filter_works(self):
        conn = self._make_db()
        # Pattern surface should not return design_note content
        results = retrieve_evidence(
            "pipeline transform steps",
            conn,
            surfaces=["pattern"],
        )
        assert len(results) > 0
        # Should not include design_note content
        design_note_contents = {
            "AI is voice and judgment only. It must never mutate game state directly.",
            "Movement is owned by the adjudicator, not the AI layer.",
            "Resource cleanup must happen in the same scope that acquired the resource.",
        }
        for r in results:
            assert r not in design_note_contents

    def test_empty_db_returns_empty(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE knowledge_artifacts (id INTEGER PRIMARY KEY, kind TEXT, subject TEXT, content TEXT)")
        results = retrieve_evidence("anything", conn, surfaces=["design_note"])
        assert results == []

    def test_top_n_respected(self):
        conn = self._make_db()
        results = retrieve_evidence(
            "AI boundary movement adjudicator",
            conn,
            surfaces=["design_note", "pattern"],
            top_n=2,
        )
        assert len(results) <= 2

    def test_missing_table_returns_empty(self):
        conn = sqlite3.connect(":memory:")
        results = retrieve_evidence("anything", conn, surfaces=["design_note"])
        assert results == []
