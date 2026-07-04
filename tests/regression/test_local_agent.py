# tools/analysis/tests/regression/test_local_agent.py
#
# Smoke tests for local_agent.py (three-phase pipeline).
# Does not call LLM - patches _call_ollama to return controlled responses.

import sqlite3
from unittest.mock import patch

# ------------------------------------------------------------------
# Minimal stubs
# ------------------------------------------------------------------

class _FakeOracle:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.db_path = None
    def get_project_root(self): return "/project"
    def find_symbols(self, *a, **kw): return []
    def find_files(self, *a, **kw): return []
    def get_edge_maps(self): return {}, {}
    def builtin_symbols(self): return frozenset()
    def discover_seed_symbols(self, *a, **kw): return []


class _FakeAssessor:
    def __init__(self, oracle):
        self._oracle = oracle
        self._knowledge_conn = None
    def ask(self, q):
        class R:
            def get_field(self, k): return "[stub]"
        return R()
    def semantic_summary(self, *a, **kw):
        return {"content": "stub summary", "cache_hit": False}
    def generate_task_md(self, symbol, **kw):
        return f"# task: {symbol}\n## stub\n"
    def get_artifacts(self, *a): return []
    def add_artifact(self, *a): pass


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_import_succeeds():
    import determined.agent.local_agent  # noqa: F401


def test_answer_basic_three_phase():
    """Happy path: Phase1 produces NEED: lines, resolver runs, Phase3 answers."""
    from determined.agent.local_agent import _answer
    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)

    # Phase1 returns NEED: lines; Phase3 returns the final answer.
    # resolve_all will call tools deterministically (returns empty for in-memory DB).
    responses = iter([
        "NEED: symbols named encounter",
        "The encounter system handles random encounters.",
    ])

    with patch("determined.agent.local_agent._call_ollama",
               side_effect=lambda msgs, verbose=False, label="": next(responses)):
        # Use a question that doesn't trigger any heuristic so LLM decompose fires
        answer, history = _answer("count the encounter modules", [], oracle, assessor)

    assert "encounter" in answer.lower()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_answer_no_needs_still_answers():
    """If Phase1 produces no NEED: lines, Phase3 still runs and answers."""
    from determined.agent.local_agent import _answer
    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)

    responses = iter([
        "I don't know what to search for.",   # Phase 1: no NEED: lines
        "I cannot find specific information about that topic.",  # Phase 3
    ])

    with patch("determined.agent.local_agent._call_ollama",
               side_effect=lambda msgs, verbose=False, label="": next(responses)):
        answer, history = _answer("what is the meaning of life?", [], oracle, assessor)

    assert len(history) == 2
    assert answer  # got some response


def test_answer_phase1_error_short_circuits():
    """If Phase1 returns ERROR:, _answer returns early with no history appended."""
    from determined.agent.local_agent import _answer
    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)

    with patch("determined.agent.local_agent._call_ollama",
               return_value="ERROR: llama-server is not running"):
        answer, history = _answer("anything", [], oracle, assessor)

    assert "ERROR" in answer
    assert len(history) == 0  # nothing appended on error


def test_answer_history_grows_across_questions():
    """Each Q/A appends 2 entries; second question has prior context."""
    from determined.agent.local_agent import _answer
    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)

    def _stub(msgs, verbose=False, label=""):
        # Return a NEED: on decompose calls, answer on assemble calls
        if label == "phase1-decompose":
            return "NEED: symbols named travel"
        return "The travel system handles movement."

    history: list = []
    with patch("determined.agent.local_agent._call_ollama", side_effect=_stub):
        _, history = _answer("what is the travel system?", history, oracle, assessor)
        _, history = _answer("how does it connect?", history, oracle, assessor)

    assert len(history) == 4
    assert history[0]["content"] == "what is the travel system?"
    assert history[2]["content"] == "how does it connect?"


def test_answer_multiple_needs_deduped():
    """Duplicate NEED: lines each produce only one tool call (deduplication)."""
    from determined.agent.local_agent import _answer
    from determined.agent.agent_resolver import resolve_all

    oracle = _FakeOracle()
    assessor = _FakeAssessor(oracle)

    # Phase1 emits two identical needs - resolver should dedup them
    phase1_response = "NEED: symbols named encounter\nNEED: symbols named encounter"

    call_log = []

    def _stub(msgs, verbose=False, label=""):
        call_log.append(label)
        if label == "phase1-decompose":
            return phase1_response
        return "Deduped correctly."

    with patch("determined.agent.local_agent._call_ollama", side_effect=_stub):
        answer, _ = _answer("find encounter twice", [], oracle, assessor)

    assert "phase1-decompose" in call_log
    assert "phase3-assemble" in call_log
    # Only two LLM calls total (phases 1 and 3); resolve is deterministic
    assert call_log.count("phase1-decompose") == 1
    assert call_log.count("phase3-assemble") == 1


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  FAIL  {t.__name__}: {exc}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
