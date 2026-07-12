# tests/regression/test_annotation_pass.py
# RM51: run_annotation_pass driver -- priority queue and convergence loop

import json
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from determined.persistence.persistence_engine import ensure_schema
from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table


PROJECT_ROOT = "C:/project"

_FAKE_JSON = json.dumps({
    "param_types": {"x": "int"},
    "return_type": "str",
    "pre_conditions": [],
    "post_conditions": [],
    "raises": [],
    "docstring": "Does something.",
    "confidence": 0.8,
    "inference_basis": ["2 callers found"],
})


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


def _seed_fn(conn, name, file_path="a.py", line=10, param_types_json=None, is_stub=0):
    conn.execute(
        "INSERT INTO functions (name, file_path, line_number, arguments_json, "
        "param_types_json, is_stub) VALUES (?, ?, ?, ?, ?, ?)",
        (name, file_path, line, '["x"]', param_types_json, is_stub),
    )
    conn.commit()


def _seed_edge(conn, caller, callee):
    conn.execute(
        "INSERT OR IGNORE INTO graph_edges (caller, callee, source_id, target_id) "
        "VALUES (?, ?, ?, ?)",
        (caller, callee, caller, callee),
    )
    conn.commit()


def _patch_llm(fake_response=_FAKE_JSON):
    import determined.agent.llm_client as llm_mod
    original = llm_mod.generate_quality
    llm_mod.generate_quality = lambda prompt, **kw: fake_response
    return original


def _restore_llm(original):
    import determined.agent.llm_client as llm_mod
    llm_mod.generate_quality = original


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_queue_empty_when_all_annotated():
    """If all functions already have inferred_annotations, queue is empty."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    _seed_fn(conn, "foo")
    # pre-store an annotation for foo
    from datetime import datetime, timezone
    conn.execute(
        "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, 'inferred_annotation', '{}', 'llm-inferred', ?, 1)",
        ("foo", datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    from determined.agent.agent_tools import _build_annotation_queue
    queue = _build_annotation_queue(oracle)
    assert all(item["name"] != "foo" for item in queue)


def test_queue_ordered_by_caller_count():
    """Functions with more callers appear earlier in the queue."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    _seed_fn(conn, "low_caller", "a.py")
    _seed_fn(conn, "high_caller", "a.py")
    # Give high_caller 3 callers, low_caller 1
    for i in range(3):
        _seed_edge(conn, f"caller_{i}", "high_caller")
    _seed_edge(conn, "only_caller", "low_caller")

    from determined.agent.agent_tools import _build_annotation_queue
    queue = _build_annotation_queue(oracle)
    names = [item["name"] for item in queue]
    assert names.index("high_caller") < names.index("low_caller")


def test_queue_scope_filter():
    """scope argument restricts queue to matching file paths."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    _seed_fn(conn, "in_scope", "world/world_app.py")
    _seed_fn(conn, "out_scope", "engine/core.py")

    from determined.agent.agent_tools import _build_annotation_queue
    queue = _build_annotation_queue(oracle, scope="world/")
    names = [item["name"] for item in queue]
    assert "in_scope" in names
    assert "out_scope" not in names


def test_queue_excludes_stubs():
    """Stubs (is_stub=1) are excluded from the annotation queue."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    _seed_fn(conn, "a_stub", is_stub=1)
    _seed_fn(conn, "a_complete", is_stub=0)

    from determined.agent.agent_tools import _build_annotation_queue
    queue = _build_annotation_queue(oracle)
    names = [item["name"] for item in queue]
    assert "a_stub" not in names
    assert "a_complete" in names


def test_run_pass_annotates_functions():
    """run_annotation_pass with LLM mocked stores inferred_annotations."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    assessor = _FakeAssessor(oracle)
    _seed_fn(conn, "alpha", "x.py", line=1)
    _seed_fn(conn, "beta", "x.py", line=10)

    orig = _patch_llm()
    try:
        from determined.agent.agent_tools import run_annotation_pass
        result = run_annotation_pass(assessor, {"max_functions": 5})
    finally:
        _restore_llm(orig)

    assert "Annotated:" in result
    # At least one function was annotated
    rows = conn.execute(
        "SELECT subject FROM knowledge_artifacts WHERE kind='inferred_annotation'"
    ).fetchall()
    assert len(rows) >= 1


def test_run_pass_max_functions_cap():
    """max_functions limits how many functions are processed."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    assessor = _FakeAssessor(oracle)
    for i in range(5):
        _seed_fn(conn, f"fn_{i}", "x.py", line=i * 10)

    orig = _patch_llm()
    try:
        from determined.agent.agent_tools import run_annotation_pass
        result = run_annotation_pass(assessor, {"max_functions": 2})
    finally:
        _restore_llm(orig)

    rows = conn.execute(
        "SELECT subject FROM knowledge_artifacts WHERE kind='inferred_annotation'"
    ).fetchall()
    assert len(rows) <= 2


def test_run_pass_empty_queue():
    """run_annotation_pass with empty queue returns informative message."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    assessor = _FakeAssessor(oracle)
    # No functions seeded

    from determined.agent.agent_tools import run_annotation_pass
    result = run_annotation_pass(assessor, {})
    assert "queue is empty" in result.lower()


def test_run_pass_convergence_on_llm_failure():
    """Consecutive LLM failures trigger early stop."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    assessor = _FakeAssessor(oracle)
    for i in range(5):
        _seed_fn(conn, f"fn_{i}", "x.py", line=i * 10)

    import determined.agent.llm_client as llm_mod
    orig = llm_mod.generate_quality
    llm_mod.generate_quality = lambda prompt, **kw: (_ for _ in ()).throw(
        RuntimeError("LLM offline")
    )
    try:
        from determined.agent.agent_tools import run_annotation_pass
        result = run_annotation_pass(assessor, {
            "max_functions": 10,
            "convergence_threshold": 2,
        })
    finally:
        llm_mod.generate_quality = orig

    assert "STOPPED" in result


def test_run_pass_scope_respected():
    """scope argument passed through to queue builder."""
    conn = _make_db()
    oracle = _FakeOracle(conn)
    assessor = _FakeAssessor(oracle)
    _seed_fn(conn, "in_scope", "dungeon/engine.py", line=1)
    _seed_fn(conn, "out_scope", "world/app.py", line=1)

    orig = _patch_llm()
    try:
        from determined.agent.agent_tools import run_annotation_pass
        result = run_annotation_pass(assessor, {"scope": "dungeon/", "max_functions": 10})
    finally:
        _restore_llm(orig)

    rows = conn.execute(
        "SELECT subject FROM knowledge_artifacts WHERE kind='inferred_annotation'"
    ).fetchall()
    subjects = {r[0] for r in rows}
    assert "in_scope" in subjects
    assert "out_scope" not in subjects
