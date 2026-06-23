# tests/regression/test_intent_layer_ab.py
#
# Regression tests for Intent Layer sub-layers A and B (TRACKER.md item 12b):
#   Sub-layer A: semantic_summaries table + get_or_generate_summary()
#   Sub-layer B: knowledge_artifacts table + add/get/list/delete/highest_provenance
#
# All tests use in-memory SQLite; no Ollama needed (Ollama unavailability
# is tested explicitly via the heuristic-fallback test).

import sqlite3

from determined.intent.semantic_summary import (
    ensure_semantic_summaries_table,
    get_or_generate_summary,
    get_summary_if_fresh,
    list_summaries,
    _hash,
    _heuristic_stub,
)
from determined.intent.knowledge_artifact import (
    ensure_knowledge_artifacts_table,
    add_artifact,
    get_artifacts,
    list_artifacts,
    delete_artifact,
    highest_provenance,
    VALID_KINDS,
    VALID_PROVENANCES,
)
from determined.persistence.persistence_engine import ensure_schema


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _make_conn():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    ensure_semantic_summaries_table(cursor)
    ensure_knowledge_artifacts_table(cursor)
    conn.commit()
    return conn


# ==================================================================
# Sub-layer A - semantic_summaries
# ==================================================================

def test_ensure_schema_creates_semantic_summaries_table():
    # semantic_summaries lives in knowledge.db (KnowledgeOracle), not corpus DB.
    # Verify the table is created by ensure_semantic_summaries_table directly.
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    ensure_semantic_summaries_table(cursor)
    conn.commit()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='semantic_summaries'"
    )
    assert cursor.fetchone() is not None, "semantic_summaries table was not created"


def test_semantic_summary_stored_and_retrieved():
    conn = _make_conn()
    source = "def foo(): pass"
    result = get_or_generate_summary(conn, "myfile.py", "file", source)
    assert result["subject"] == "myfile.py"
    assert result["kind"] == "file"
    assert result["content"]
    assert result["source_hash"] == _hash(source)
    assert result["cache_hit"] is False


def test_semantic_summary_cache_hit_on_same_hash():
    conn = _make_conn()
    source = "def foo(): pass"
    first = get_or_generate_summary(conn, "myfile.py", "file", source)
    second = get_or_generate_summary(conn, "myfile.py", "file", source)
    assert second["cache_hit"] is True
    assert second["content"] == first["content"]


def test_semantic_summary_stale_on_changed_source():
    conn = _make_conn()
    source_v1 = "def foo(): pass"
    source_v2 = "def foo(): return 42"
    r1 = get_or_generate_summary(conn, "myfile.py", "file", source_v1)
    assert r1["cache_hit"] is False
    r2 = get_or_generate_summary(conn, "myfile.py", "file", source_v2)
    assert r2["cache_hit"] is False
    assert r2["source_hash"] != r1["source_hash"]


def test_semantic_summary_force_refresh_bypasses_cache():
    conn = _make_conn()
    source = "def foo(): pass"
    get_or_generate_summary(conn, "myfile.py", "file", source)
    result = get_or_generate_summary(conn, "myfile.py", "file", source, force_refresh=True)
    assert result["cache_hit"] is False


def test_get_summary_if_fresh_returns_none_when_missing():
    conn = _make_conn()
    result = get_summary_if_fresh(conn, "nowhere.py", "file", "x = 1")
    assert result is None


def test_get_summary_if_fresh_returns_none_when_stale():
    conn = _make_conn()
    get_or_generate_summary(conn, "myfile.py", "file", "version 1")
    result = get_summary_if_fresh(conn, "myfile.py", "file", "version 2")
    assert result is None


def test_get_summary_if_fresh_returns_cached_when_fresh():
    conn = _make_conn()
    source = "class A: pass"
    get_or_generate_summary(conn, "myfile.py", "file", source)
    result = get_summary_if_fresh(conn, "myfile.py", "file", source)
    assert result is not None
    assert result["cache_hit"] is True


def test_list_summaries_returns_all():
    conn = _make_conn()
    get_or_generate_summary(conn, "a.py", "file", "x = 1")
    get_or_generate_summary(conn, "b.py", "file", "y = 2")
    rows = list_summaries(conn)
    subjects = {r["subject"] for r in rows}
    assert {"a.py", "b.py"} <= subjects


def test_list_summaries_filtered_by_kind():
    conn = _make_conn()
    get_or_generate_summary(conn, "a.py", "file", "x")
    get_or_generate_summary(conn, "mymod", "module", "y")
    file_rows = list_summaries(conn, kind="file")
    module_rows = list_summaries(conn, kind="module")
    assert all(r["kind"] == "file" for r in file_rows)
    assert all(r["kind"] == "module" for r in module_rows)


def test_heuristic_stub_no_ollama():
    result = _heuristic_stub("myfile.py", "file", "def foo(): pass\ndef bar(): pass\n")
    assert "heuristic" in result
    assert "myfile.py" in result
    assert "2" in result  # 2 definitions


def test_semantic_summary_empty_source_no_crash():
    conn = _make_conn()
    result = get_or_generate_summary(conn, "empty.py", "file", "")
    assert result["content"]  # should produce the "[no source text]" stub


def test_semantic_summary_invalid_kind_raises():
    conn = _make_conn()
    try:
        get_or_generate_summary(conn, "x.py", "banana", "code")
        assert False, "should have raised"
    except ValueError:
        pass


# ==================================================================
# Sub-layer B - knowledge_artifacts
# ==================================================================

def test_ensure_schema_creates_knowledge_artifacts_table():
    # knowledge_artifacts lives in knowledge.db (KnowledgeOracle), not corpus DB.
    # Verify the table is created by ensure_knowledge_artifacts_table directly.
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    ensure_knowledge_artifacts_table(cursor)
    conn.commit()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_artifacts'"
    )
    assert cursor.fetchone() is not None, "knowledge_artifacts table was not created"


def test_add_and_get_artifact():
    conn = _make_conn()
    row_id = add_artifact(conn, "contracts/", "design_note", "Three contract systems overlap.", "human-confirmed")
    assert isinstance(row_id, int) and row_id > 0
    results = get_artifacts(conn, "contracts/")
    assert len(results) == 1
    assert results[0]["content"] == "Three contract systems overlap."
    assert results[0]["provenance"] == "human-confirmed"


def test_get_artifacts_empty_when_no_match():
    conn = _make_conn()
    results = get_artifacts(conn, "nonexistent_subject")
    assert results == []


def test_get_artifacts_sorted_by_provenance_rank():
    conn = _make_conn()
    add_artifact(conn, "foo.py", "file_purpose", "AI guess", "ai-generated")
    add_artifact(conn, "foo.py", "file_purpose", "Human fact", "human-confirmed")
    add_artifact(conn, "foo.py", "file_purpose", "AI+human", "ai-confirmed-by-human")
    results = get_artifacts(conn, "foo.py")
    provenances = [r["provenance"] for r in results]
    assert provenances[0] == "human-confirmed"
    assert provenances[1] == "ai-confirmed-by-human"
    assert provenances[2] == "ai-generated"


def test_get_artifacts_filtered_by_kind():
    conn = _make_conn()
    add_artifact(conn, "foo.py", "file_purpose", "purpose text", "ai-generated")
    add_artifact(conn, "foo.py", "known_issue", "a bug", "ai-generated")
    results = get_artifacts(conn, "foo.py", kind="known_issue")
    assert len(results) == 1
    assert results[0]["kind"] == "known_issue"


def test_list_artifacts_all():
    conn = _make_conn()
    add_artifact(conn, "a.py", "file_purpose", "A", "ai-generated")
    add_artifact(conn, "b.py", "strategy_decision", "B", "human-confirmed")
    all_rows = list_artifacts(conn)
    assert len(all_rows) == 2


def test_list_artifacts_filter_by_kind():
    conn = _make_conn()
    add_artifact(conn, "a.py", "file_purpose", "A", "ai-generated")
    add_artifact(conn, "b.py", "strategy_decision", "B", "human-confirmed")
    decisions = list_artifacts(conn, kind="strategy_decision")
    assert len(decisions) == 1 and decisions[0]["kind"] == "strategy_decision"


def test_list_artifacts_filter_by_provenance():
    conn = _make_conn()
    add_artifact(conn, "a.py", "file_purpose", "A", "ai-generated")
    add_artifact(conn, "b.py", "design_note", "B", "human-confirmed")
    human = list_artifacts(conn, provenance="human-confirmed")
    assert all(r["provenance"] == "human-confirmed" for r in human)


def test_delete_artifact():
    conn = _make_conn()
    row_id = add_artifact(conn, "x.py", "file_purpose", "will be deleted", "ai-generated")
    removed = delete_artifact(conn, row_id)
    assert removed is True
    assert get_artifacts(conn, "x.py") == []


def test_delete_artifact_nonexistent_returns_false():
    conn = _make_conn()
    removed = delete_artifact(conn, 99999)
    assert removed is False


def test_highest_provenance_selects_human_confirmed():
    conn = _make_conn()
    add_artifact(conn, "foo.py", "file_purpose", "AI guess", "ai-generated")
    add_artifact(conn, "foo.py", "file_purpose", "Human fact", "human-confirmed")
    artifacts = get_artifacts(conn, "foo.py")
    best = highest_provenance(artifacts)
    assert best["provenance"] == "human-confirmed"


def test_highest_provenance_empty_list_returns_none():
    result = highest_provenance([])
    assert result is None


def test_add_artifact_invalid_kind_raises():
    conn = _make_conn()
    try:
        add_artifact(conn, "x.py", "not_a_kind", "content")
        assert False, "should have raised"
    except ValueError:
        pass


def test_add_artifact_invalid_provenance_raises():
    conn = _make_conn()
    try:
        add_artifact(conn, "x.py", "design_note", "content", provenance="unverified")
        assert False, "should have raised"
    except ValueError:
        pass


def test_assessor_semantic_summary_reads_file_automatically():
    """Assessor.semantic_summary with kind='file' must read source without caller passing text."""
    import tempfile, os
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor

    # Write a real source file the assessor can read
    src = "def greet():\n    '''Say hello.'''\n    return 'hello'\n"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        src_path = f.name
        f.write(src)

    tmp_db = tempfile.mktemp(suffix=".db")
    try:
        oracle = DBOracle(tmp_db)
        ensure_schema(oracle.conn)
        # semantic_summaries lives in the knowledge conn - wire it up
        from determined.intent.semantic_summary import ensure_semantic_summaries_table
        cur = oracle.conn.cursor()
        ensure_semantic_summaries_table(cur)
        oracle.conn.commit()
        a = Assessor(oracle)
        # Pass the absolute path directly - no source_text supplied
        result = a.semantic_summary(src_path, kind="file")
        # Must not be the "no source text provided" stub
        assert "[no source text provided" not in result["content"], (
            f"Assessor did not read the file: {result['content']}"
        )
        assert result["content"].strip() != ""
    finally:
        oracle.conn.close()
        os.remove(src_path)
        if os.path.exists(tmp_db):
            os.remove(tmp_db)


# ------------------------------------------------------------------
# run directly
# ------------------------------------------------------------------
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
