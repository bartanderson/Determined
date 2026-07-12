# tests/regression/test_annotate_function.py
# RM49: annotate_function tool -- infer types/contracts for unannotated functions

import json
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from determined.persistence.persistence_engine import ensure_schema
from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table


PROJECT_ROOT = "C:/project"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _FakeOracle:
    def __init__(self, conn):
        self.conn = conn
        self.db_path = None

    def get_project_root(self):
        return PROJECT_ROOT

    def find_symbols(self, pattern, symbol_type=None, exact=False, limit=50):
        return []

    def find_files(self, pattern=None, role=None, limit=None):
        return []


class _FakeAssessor:
    def __init__(self, oracle):
        self.oracle = oracle
        self._oracle = oracle
        self._knowledge_conn = oracle.conn


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    ensure_knowledge_artifacts_table(conn)
    conn.commit()
    return conn


def _seed_function(conn, name="process", file_path="engine.py", line=10,
                   arguments_json='["action", "state"]',
                   return_type=None, param_types_json=None, docstring=None):
    conn.execute(
        "INSERT INTO functions (name, file_path, line_number, arguments_json, return_type, "
        "param_types_json, docstring, is_stub) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        (name, file_path, line, arguments_json, return_type, param_types_json, docstring),
    )
    conn.commit()


def _seed_edge(conn, caller, callee):
    conn.execute(
        "INSERT OR IGNORE INTO graph_edges (caller, callee, source_id, target_id) VALUES (?, ?, ?, ?)",
        (caller, callee, caller, callee),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helper: call annotate_function with a mocked LLM response
# ---------------------------------------------------------------------------

_FAKE_JSON = json.dumps({
    "param_types": {"action": "PlayerAction", "state": "GameState"},
    "return_type": "Dict[str, Any]",
    "pre_conditions": ["action must be a valid ActionType"],
    "post_conditions": ["returns dict with key 'success'"],
    "raises": ["ValueError if action.type is unknown"],
    "docstring": "Process a player action and return the result.",
    "confidence": 0.75,
    "inference_basis": ["5 callers pass PlayerAction typed arg"],
})


def _annotate(assessor, symbol, fake_response=_FAKE_JSON):
    """Call annotate_function with LLM patched to return fake_response."""
    import determined.agent.llm_client as llm_mod

    original = llm_mod.generate_quality
    llm_mod.generate_quality = lambda prompt, **kw: fake_response
    try:
        from determined.agent.agent_tools import annotate_function
        result = annotate_function(assessor, {"symbol": symbol})
    finally:
        llm_mod.generate_quality = original
    return result


# ---------------------------------------------------------------------------
# Tests: storage
# ---------------------------------------------------------------------------

def test_stores_inferred_annotation_row():
    conn = _make_db()
    _seed_function(conn, name="process")
    oracle = _FakeOracle(conn)
    assessor = _FakeAssessor(oracle)

    _annotate(assessor, "process")

    row = conn.execute(
        "SELECT kind, content, provenance FROM knowledge_artifacts WHERE subject='process'",
    ).fetchone()
    assert row is not None
    assert row["kind"] == "inferred_annotation"
    assert row["provenance"] == "llm-inferred"


def test_stored_content_is_valid_json_with_required_keys():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    _annotate(assessor, "process")

    content = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject='process' AND kind='inferred_annotation'",
    ).fetchone()[0]
    data = json.loads(content)

    required = {"param_types", "return_type", "pre_conditions", "post_conditions",
                "raises", "docstring", "confidence", "inference_basis"}
    assert required.issubset(set(data.keys()))


def test_confidence_is_float():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    _annotate(assessor, "process")

    content = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject='process' AND kind='inferred_annotation'",
    ).fetchone()[0]
    data = json.loads(content)
    assert isinstance(data["confidence"], float)
    assert 0.0 <= data["confidence"] <= 1.0


def test_inference_basis_non_empty():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    _annotate(assessor, "process")

    content = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject='process' AND kind='inferred_annotation'",
    ).fetchone()[0]
    data = json.loads(content)
    assert len(data["inference_basis"]) >= 1


def test_stale_annotation_replaced_on_rerun():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    _annotate(assessor, "process")
    _annotate(assessor, "process")  # second run

    rows = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE subject='process' AND kind='inferred_annotation'",
    ).fetchone()[0]
    assert rows == 1  # no duplicates


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

def test_missing_symbol_arg_returns_error():
    conn = _make_db()
    assessor = _FakeAssessor(_FakeOracle(conn))
    from determined.agent.agent_tools import annotate_function
    result = annotate_function(assessor, {})
    assert result.startswith("ERROR")


def test_unknown_symbol_returns_error():
    conn = _make_db()
    assessor = _FakeAssessor(_FakeOracle(conn))
    from determined.agent.agent_tools import annotate_function
    result = annotate_function(assessor, {"symbol": "does_not_exist"})
    assert "not found" in result.lower()


def test_invalid_llm_json_returns_error():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    import determined.agent.llm_client as llm_mod
    original = llm_mod.generate_quality
    llm_mod.generate_quality = lambda prompt, **kw: "not json at all"
    try:
        from determined.agent.agent_tools import annotate_function
        result = annotate_function(assessor, {"symbol": "process"})
    finally:
        llm_mod.generate_quality = original

    assert "ERROR" in result


# ---------------------------------------------------------------------------
# Tests: output format
# ---------------------------------------------------------------------------

def test_output_contains_confidence():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    result = _annotate(assessor, "process")
    assert "Confidence:" in result


def test_output_contains_param_types():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    result = _annotate(assessor, "process")
    assert "INFERRED PARAM TYPES" in result
    assert "PlayerAction" in result


def test_output_contains_return_type():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    result = _annotate(assessor, "process")
    assert "INFERRED RETURN TYPE" in result
    assert "Dict" in result


def test_output_contains_stored_confirmation():
    conn = _make_db()
    _seed_function(conn, name="process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    result = _annotate(assessor, "process")
    assert "[STORED]" in result


def test_write_back_false_does_not_modify_source(tmp_path):
    """write_back defaults to False; no source file should be touched."""
    src_file = tmp_path / "engine.py"
    src_file.write_text("def process(action, state):\n    pass\n")

    conn = _make_db()
    _seed_function(conn, name="process", file_path=str(src_file))
    assessor = _FakeAssessor(_FakeOracle(conn))

    original_mtime = src_file.stat().st_mtime
    _annotate(assessor, "process")
    assert src_file.stat().st_mtime == original_mtime


def test_file_path_hint_disambiguates():
    conn = _make_db()
    _seed_function(conn, name="process", file_path="engine_a.py", line=10)
    _seed_function(conn, name="process", file_path="engine_b.py", line=20)
    assessor = _FakeAssessor(_FakeOracle(conn))

    import determined.agent.llm_client as llm_mod
    original = llm_mod.generate_quality
    llm_mod.generate_quality = lambda prompt, **kw: _FAKE_JSON
    try:
        from determined.agent.agent_tools import annotate_function
        result = annotate_function(assessor, {"symbol": "process", "file_path": "engine_b.py"})
    finally:
        llm_mod.generate_quality = original

    assert "engine_b.py" in result


# ---------------------------------------------------------------------------
# Tests: caller/callee context assembly (structural, no LLM)
# ---------------------------------------------------------------------------

def test_callers_included_in_inference_basis_when_present():
    conn = _make_db()
    _seed_function(conn, name="process")
    _seed_function(conn, name="main_loop", file_path="main.py")
    _seed_edge(conn, "main_loop", "process")
    assessor = _FakeAssessor(_FakeOracle(conn))

    # Use a fake that returns basis reflecting callers
    fake = json.dumps({
        "param_types": {}, "return_type": "None",
        "pre_conditions": [], "post_conditions": [], "raises": [],
        "docstring": "does stuff", "confidence": 0.5,
        "inference_basis": ["1 caller(s) found in call graph"],
    })
    result = _annotate(assessor, "process", fake_response=fake)
    content = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject='process' AND kind='inferred_annotation'",
    ).fetchone()[0]
    data = json.loads(content)
    assert any("caller" in b.lower() for b in data["inference_basis"])


# ---------------------------------------------------------------------------
# Slow tests (LLM required)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_annotate_live_llm_stores_valid_annotation(tmp_path):
    """Integration test: real LLM call. Mark --slow to skip in CI."""
    src = tmp_path / "sample.py"
    src.write_text(
        "def process(action, state):\n"
        "    if action.type == 'move':\n"
        "        return {'success': True, 'effects': []}\n"
        "    raise ValueError(f'unknown action: {action.type}')\n"
    )
    conn = _make_db()
    _seed_function(conn, name="process", file_path=str(src), line=1,
                   arguments_json='["action", "state"]')
    assessor = _FakeAssessor(_FakeOracle(conn))

    from determined.agent.agent_tools import annotate_function
    result = annotate_function(assessor, {"symbol": "process"})

    assert "ERROR" not in result
    row = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject='process' AND kind='inferred_annotation'",
    ).fetchone()
    assert row is not None
    data = json.loads(row[0])
    assert isinstance(data["confidence"], float)
    assert len(data["inference_basis"]) >= 1
