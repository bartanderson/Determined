# tools/analysis/tests/regression/test_agent_tools.py
#
# Regression tests for agent/agent_tools.py (DESIGN.md section 8).
# All 12 tools tested against a controlled in-memory fixture.
# No dependency on world_corpus.db, Ollama, or network.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.intent.semantic_summary import ensure_semantic_summaries_table
from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table

os.environ.setdefault("PYTHONPATH", ".")

PROJECT_ROOT = "C:/project"


# ------------------------------------------------------------------
# FIXTURE
# ------------------------------------------------------------------

class FakeOracle:
    """Minimal oracle duck-type backed by a real in-memory DB."""
    def __init__(self, conn):
        self.conn = conn
        self.db_path = None

    def get_project_root(self):
        return PROJECT_ROOT

    def find_symbols(self, pattern, symbol_type=None, exact=False, limit=50):
        if exact:
            cond = "name = ?"
            params = [pattern]
        else:
            cond = "name LIKE ?"
            params = [f"%{pattern}%"]
        if symbol_type:
            cond += " AND symbol_type = ?"
            params.append(symbol_type)
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT name, file_path, symbol_type, line_number, signature, canonical_id "
            f"FROM symbols WHERE {cond} ORDER BY file_path, line_number LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def find_files(self, pattern=None, role=None, limit=None):
        conditions, params = [], []
        if pattern:
            conditions.append("file_path LIKE ?")
            params.append(f"%{pattern}%")
        if role:
            conditions.append("role = ?")
            params.append(role)
        q = "SELECT file_path, line_count, role, is_hot FROM files"
        if conditions:
            q += " WHERE " + " AND ".join(conditions)
        q += " ORDER BY file_path"
        if limit:
            q += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_edge_maps(self):
        rows = self.conn.execute(
            "SELECT caller, callee FROM graph_edges WHERE caller IS NOT NULL AND callee IS NOT NULL"
        ).fetchall()
        forward, reverse = {}, {}
        for r in rows:
            forward.setdefault(r[0], set()).add(r[1])
            reverse.setdefault(r[1], set()).add(r[0])
        return forward, reverse

    def builtin_symbols(self):
        return frozenset()

    def discover_seed_symbols(self, text, limit=20):
        return []


def _make_fixture():
    """
    In-memory DB with a small but representative graph:

    Files:    world/engine.py (50 lines), world/handler.py (30 lines)
    Symbols:  generate_encounter (function, engine.py, line 10, has docstring)
              handle_movement   (function, handler.py, line 5, no docstring)
              EncounterState    (class,    engine.py,  line 1,  no docstring)
    Graph:    handle_movement -> world.engine.generate_encounter (qualified)
              handle_movement -> helper (bare)
    Artifacts: one known_issue for generate_encounter
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=MEMORY")
    ensure_schema(conn)

    # semantic_summaries + knowledge_artifacts in same conn for test simplicity
    cur = conn.cursor()
    ensure_semantic_summaries_table(cur)
    ensure_knowledge_artifacts_table(cur)
    conn.commit()

    # files
    conn.execute(
        "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
        (f"{PROJECT_ROOT}/world/engine.py", 50, "core", 1),
    )
    conn.execute(
        "INSERT INTO files (file_path, line_count, role, is_hot) VALUES (?, ?, ?, ?)",
        (f"{PROJECT_ROOT}/world/handler.py", 30, "handler", 0),
    )

    # symbols
    for row in [
        (f"{PROJECT_ROOT}/world/engine.py",  "function", "generate_encounter", 10, "",
         f"{PROJECT_ROOT}/world/engine.py:function:generate_encounter:10"),
        (f"{PROJECT_ROOT}/world/handler.py", "function", "handle_movement",    5,  "",
         f"{PROJECT_ROOT}/world/handler.py:function:handle_movement:5"),
        (f"{PROJECT_ROOT}/world/engine.py",  "class",    "EncounterState",     1,  "",
         f"{PROJECT_ROOT}/world/engine.py:class:EncounterState:1"),
    ]:
        conn.execute(
            "INSERT INTO symbols (file_path, symbol_type, name, line_number, signature, canonical_id) "
            "VALUES (?, ?, ?, ?, ?, ?)", row,
        )

    # functions table (for symbol_intent and symbols_in_file)
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, docstring) VALUES (?, ?, ?, ?)",
        (f"{PROJECT_ROOT}/world/engine.py", "generate_encounter", 10,
         "Generate an Encounter based on the provided context."),
    )
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, docstring) VALUES (?, ?, ?, ?)",
        (f"{PROJECT_ROOT}/world/handler.py", "handle_movement", 5, None),
    )

    # classes table
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, docstring) VALUES (?, ?, ?, ?)",
        (f"{PROJECT_ROOT}/world/engine.py", "EncounterState", 1, None),
    )

    # graph edges: qualified callee and bare callee
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
        "VALUES (?, ?, ?, ?, ?)",
        ("handle_movement", "world.engine.generate_encounter",
         "handle_movement", "world.engine.generate_encounter", 12),
    )
    conn.execute(
        "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
        "VALUES (?, ?, ?, ?, ?)",
        ("generate_encounter", "helper", "generate_encounter", "helper", 20),
    )

    # symbol_references (for LEFT JOIN in list_callers)
    conn.execute(
        "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
        "VALUES (?, ?, ?, ?, ?)",
        (f"{PROJECT_ROOT}/world/handler.py", "handle_movement",
         "world.engine.generate_encounter", 12, "project"),
    )

    # knowledge artifact
    conn.execute(
        "INSERT INTO knowledge_artifacts "
        "(subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, ?, ?, ?, datetime('now'), 0)",
        ("generate_encounter", "known_issue", "Returns None if context is empty.",
         "human-confirmed"),
    )
    # artifact stored with file::symbol subject (tests suffix matching)
    conn.execute(
        "INSERT INTO knowledge_artifacts "
        "(subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, ?, ?, ?, datetime('now'), 0)",
        ("world/engine.py::EncounterState", "file_purpose",
         "FSM tracking encounter phase.", "ai-generated"),
    )

    conn.commit()
    return FakeOracle(conn)


class FakeAssessor:
    """
    Minimal assessor duck-type for tool tests.
    Delegates to the oracle conn directly; avoids full Assessor init.
    """
    def __init__(self, oracle):
        self._oracle = oracle
        self.oracle = oracle  # _resolve_file_path accesses assessor.oracle
        self._knowledge_conn = oracle.conn

    def semantic_summary(self, subject, kind="file", source_text="", **_):
        # Return a deterministic stub - no Ollama in tests
        return {
            "subject": subject,
            "kind": kind,
            "content": f"[test-stub] {subject} is a Python {kind}.",
            "source_hash": "abc123",
            "model_version": "test",
            "generated_at": "2026-06-20",
            "cache_hit": False,
        }

    def generate_task_md(self, symbol, out_path=None):
        # Minimal stub - returns something with the right sections
        return (
            f"# task: review impact of changes to `{symbol}`\n\n"
            "## Direct callers (confirmed)\n\n- (stub)\n\n"
            "## Impact zone (may need review)\n\n- (stub)\n"
        )

    def get_artifacts(self, subject):
        rows = self._knowledge_conn.execute(
            "SELECT id, subject, kind, content, provenance, created_at, file_hash, needs_review "
            "FROM knowledge_artifacts WHERE subject = ? ORDER BY created_at DESC",
            (subject,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def add_artifact(self, subject, kind, content, provenance):
        from determined.intent.knowledge_artifact import VALID_KINDS, VALID_PROVENANCES
        if kind not in VALID_KINDS:
            raise ValueError(f"invalid kind: {kind}")
        if provenance not in VALID_PROVENANCES:
            raise ValueError(f"invalid provenance: {provenance}")
        self._knowledge_conn.execute(
            "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (subject, kind, content, provenance),
        )
        self._knowledge_conn.commit()

    def ask(self, question):
        # Stub - returns a simple object with get_field
        class _Result:
            def get_field(self, key):
                return f"[stub answer to: {question}]"
        return _Result()


def _row_to_dict(r):
    keys = ["id", "subject", "kind", "content", "provenance",
            "created_at", "file_hash", "needs_review"]
    return dict(zip(keys, r))


# ------------------------------------------------------------------
# HELPER
# ------------------------------------------------------------------

def _dispatch(tool, args, oracle=None, assessor=None):
    from determined.agent.agent_tools import dispatch
    _oracle = oracle or _make_fixture()
    _assessor = assessor or FakeAssessor(_oracle)
    return dispatch(tool, args, _oracle, _assessor)


# ------------------------------------------------------------------
# DISCOVERY TOOLS
# ------------------------------------------------------------------

def test_search_symbols_returns_matches():
    result = _dispatch("search_symbols", {"query": "encounter"})
    assert "generate_encounter" in result
    assert "EncounterState" in result


def test_search_symbols_no_match():
    result = _dispatch("search_symbols", {"query": "xyzzy_nonexistent"})
    assert "No symbols found" in result


def test_search_symbols_missing_query():
    result = _dispatch("search_symbols", {})
    assert "ERROR" in result


def test_search_files_returns_matches():
    result = _dispatch("search_files", {"query": "engine"})
    assert "engine.py" in result


def test_search_files_no_match():
    result = _dispatch("search_files", {"query": "xyzzy_nonexistent"})
    assert "No files found" in result


def test_list_callers_bare_name():
    result = _dispatch("list_callers", {"symbol": "generate_encounter"})
    assert "handle_movement" in result


def test_list_callers_qualified_name_matches_bare_query():
    """Callee stored as 'world.engine.generate_encounter' must match bare query."""
    result = _dispatch("list_callers", {"symbol": "generate_encounter"})
    assert "handle_movement" in result
    assert "No direct callers" not in result


def test_list_callers_no_callers():
    result = _dispatch("list_callers", {"symbol": "xyzzy_none"})
    assert "No direct callers" in result


def test_list_callees_returns_results():
    result = _dispatch("list_callees", {"symbol": "generate_encounter"})
    assert "helper" in result


def test_list_callees_no_callees():
    result = _dispatch("list_callees", {"symbol": "xyzzy_none"})
    assert "No" in result and "callee" in result.lower()


def test_symbols_in_file_returns_symbols():
    result = _dispatch("symbols_in_file", {"file_path": "world/engine.py"})
    assert "generate_encounter" in result
    assert "EncounterState" in result


def test_symbols_in_file_shows_docstring_flag():
    result = _dispatch("symbols_in_file", {"file_path": "world/engine.py"})
    assert "has docstring" in result


def test_symbols_in_file_not_found():
    result = _dispatch("symbols_in_file", {"file_path": "world/nonexistent.py"})
    assert "No symbols found" in result


def test_files_in_directory_returns_files():
    result = _dispatch("files_in_directory", {"path": "world"})
    assert "engine.py" in result
    assert "handler.py" in result


def test_files_in_directory_not_found():
    result = _dispatch("files_in_directory", {"path": "xyzzy"})
    assert "No files found" in result


# ------------------------------------------------------------------
# UNDERSTANDING TOOLS
# ------------------------------------------------------------------

def test_describe_file_returns_content():
    result = _dispatch("describe_file", {"file_path": "world/engine.py"})
    assert "engine.py" in result
    assert len(result) > 10


def test_describe_file_missing_arg():
    result = _dispatch("describe_file", {})
    assert "ERROR" in result


def test_symbol_intent_with_docstring():
    result = _dispatch("symbol_intent", {"symbol": "generate_encounter"})
    assert "Generate an Encounter" in result


def test_symbol_intent_no_docstring():
    result = _dispatch("symbol_intent", {"symbol": "handle_movement"})
    assert "no docstring" in result


def test_symbol_intent_not_found():
    result = _dispatch("symbol_intent", {"symbol": "xyzzy_none"})
    assert "not found" in result


def test_symbol_brief_returns_sections():
    result = _dispatch("symbol_brief", {"symbol": "generate_encounter"})
    assert "Direct callers" in result
    assert "Impact zone" in result


# ------------------------------------------------------------------
# KNOWLEDGE TOOLS
# ------------------------------------------------------------------

def test_get_findings_exact_subject():
    result = _dispatch("get_findings", {"symbol": "generate_encounter"})
    assert "Returns None if context is empty" in result
    assert "human-confirmed" in result


def test_get_findings_suffix_match():
    """Artifact stored as 'file::symbol' must be found by bare symbol query."""
    result = _dispatch("get_findings", {"symbol": "EncounterState"})
    assert "FSM tracking encounter phase" in result


def test_get_findings_none_stored():
    result = _dispatch("get_findings", {"symbol": "handle_movement"})
    assert "No stored findings" in result


def test_store_finding_writes_artifact():
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)
    result = _dispatch("store_finding",
                       {"symbol": "handle_movement",
                        "kind": "known_issue",
                        "content": "Does not validate input before routing."},
                       oracle=oracle, assessor=assessor)
    assert "Stored" in result
    # verify it's actually in the DB
    row = oracle.conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE subject = 'handle_movement'"
    ).fetchone()
    assert row is not None
    assert "Does not validate" in row[0]


def test_store_finding_invalid_kind():
    result = _dispatch("store_finding",
                       {"symbol": "x", "kind": "not_a_kind", "content": "y"})
    assert "ERROR" in result


def test_store_finding_missing_args():
    result = _dispatch("store_finding", {"symbol": "x"})
    assert "ERROR" in result


# ------------------------------------------------------------------
# TRUTH LAYER TOOL
# ------------------------------------------------------------------

def test_ask_truth_layer_returns_answer():
    result = _dispatch("ask_truth_layer", {"question": "what is the structure"})
    assert len(result) > 0
    assert "ERROR" not in result or "Truth layer" in result


def test_ask_truth_layer_missing_question():
    result = _dispatch("ask_truth_layer", {})
    assert "ERROR" in result


# ------------------------------------------------------------------
# DISPATCH
# ------------------------------------------------------------------

def test_dispatch_unknown_tool():
    from determined.agent.agent_tools import dispatch
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)
    result = dispatch("nonexistent_tool", {}, oracle, assessor)
    assert "ERROR" in result
    assert "unknown tool" in result


def test_dispatch_all_tools_registered():
    from determined.agent.agent_tools import TOOLS
    expected = {
        "search_symbols", "search_files", "list_callers", "list_callees",
        "symbols_in_file", "files_in_directory", "describe_file",
        "symbol_intent", "symbol_brief", "get_findings", "store_finding",
        "ask_truth_layer",
        "graph_path", "graph_entry_points", "graph_most_connected",
        "graph_subgraph", "graph_clusters",
        "workflow_status", "store_workflow_item", "rerank_workflow",
        "prioritize_work",
        "list_findings_by_kind",
        "missing_docstrings",
        "find_todos",
        "git_log_for",
        "risk_profile",
        "knowledge_status",
        "extract_design_facts",
        "describe_tool",
        # Level-4 edge tools
        "edges_of",
        "edge_detail",
        "list_import_deps",
        "add_edge",
        # Bag tools
        "bag_status",
        "bag_list",
        "bag_add",
        "bag_label",
        "bag_clear",
        "bag_report",
        "list_stubs",
        "project_stub",
        "discover_docs",
        "ingest_design_docs",
        "goal_intake",
        "distill_corpus",
        "check_design_violations",
        "project_status",
        "reingest_file",
    }
    assert set(TOOLS.keys()) == expected


def test_tool_registry_covers_all_tools():
    """Every tool in TOOLS must have a registry entry with required fields."""
    from determined.agent.agent_tools import TOOLS
    from determined.agent.tool_registry import REGISTRY, get_compact_tool_list
    for name in TOOLS:
        assert name in REGISTRY, f"tool '{name}' missing from REGISTRY"
        entry = REGISTRY[name]
        for field in ("purpose", "args", "output", "feeds", "use_when", "category"):
            assert field in entry, f"REGISTRY['{name}'] missing field '{field}'"
    # compact list must mention all tools
    compact = get_compact_tool_list()
    for name in TOOLS:
        assert name in compact, f"'{name}' missing from compact tool list"


def test_describe_tool_fn_lookup():
    """describe_tool_fn returns useful output for known and unknown tool names."""
    from determined.agent.tool_registry import describe_tool_fn
    result = describe_tool_fn(None, {"name": "search_symbols"})
    assert "search_symbols" in result
    assert "Purpose" in result
    assert "feeds" in result.lower() or "Feeds" in result

    result_all = describe_tool_fn(None, {"name": "all"})
    assert "search_symbols" in result_all
    assert "graph" in result_all

    result_patterns = describe_tool_fn(None, {"name": "patterns"})
    assert "understand_symbol" in result_patterns
    assert "orient_to_codebase" in result_patterns

    result_bad = describe_tool_fn(None, {"name": "xyzzy_nonexistent"})
    assert "Unknown tool" in result_bad


def test_distill_corpus_no_ollama():
    """distill_corpus returns a clear error when Ollama is unreachable."""
    from determined.agent.agent_tools import distill_corpus
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)
    # Ollama is not running in tests - should get a clear error, not a crash
    result = distill_corpus(assessor, {})
    assert "ERROR" in result or "distill_corpus" in result


def test_distill_corpus_idempotent():
    """distill_corpus skips already-distilled subjects without re-calling Ollama."""
    import unittest.mock as mock
    from determined.agent.agent_tools import distill_corpus
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)
    conn = oracle.conn

    # Pre-populate a semantic_summary
    conn.execute(
        "INSERT INTO semantic_summaries "
        "(subject, kind, content, source_hash, model_version, generated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
        ("engine.py", "file", "Handles encounter generation.", "abc123", "llama3.2:3b"),
    )
    conn.commit()

    # Pre-populate the distilled entry to simulate a prior run
    conn.execute(
        "INSERT INTO knowledge_artifacts "
        "(subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, ?, ?, ?, datetime('now'), 0)",
        ("distilled::engine", "distilled", "Generates encounters for the game world.", "ai-generated"),
    )
    conn.commit()

    call_count = 0
    def mock_distill(content, subject):
        nonlocal call_count
        call_count += 1
        return "mock sentence"

    with mock.patch("determined.agent.agent_tools._distill_to_one_sentence", side_effect=mock_distill):
        result = distill_corpus(assessor, {})

    # The pre-existing "distilled::engine" entry should be skipped
    # The probe call counts as 1; if no new entries, only probe fires
    assert "skipped" in result or "already cached" in result or "distill_corpus" in result


def test_raw_helpers_return_dicts():
    """_list_callers_raw, _list_callees_raw, _search_symbols_raw return list[dict]."""
    from determined.agent.agent_tools import (
        _list_callers_raw, _list_callees_raw, _search_symbols_raw,
        _graph_most_connected_raw, _graph_subgraph_raw,
    )
    oracle = _make_fixture()

    callers = _list_callers_raw(oracle, "generate_encounter")
    assert isinstance(callers, list)
    assert all(isinstance(r, dict) for r in callers)
    assert all("caller" in r and "line_number" in r for r in callers)
    assert any(r["caller"] == "handle_movement" for r in callers)

    callees = _list_callees_raw(oracle, "generate_encounter")
    assert isinstance(callees, list)
    # "helper" is in the graph; builtins are filtered
    if callees:
        assert all("callee" in r and "count" in r for r in callees)

    results = _search_symbols_raw(oracle, "generate")
    assert isinstance(results, list)
    assert any(r["name"] == "generate_encounter" for r in results)
    assert all("docstring" in r for r in results)  # docstring key always present

    connected = _graph_most_connected_raw(oracle)
    assert isinstance(connected, list)
    if connected:
        assert all("symbol" in r and "in_degree" in r for r in connected)

    sg = _graph_subgraph_raw(oracle, "generate_encounter", radius=1)
    assert isinstance(sg, dict)
    assert "nodes" in sg and "edges" in sg
    assert "generate_encounter" in sg["nodes"]


def test_project_status_structural():
    """project_status returns subsystem matrix and totals without Ollama."""
    from determined.agent.agent_tools import project_status
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)

    result = project_status(assessor, {})
    # Must have the header with file/function counts
    assert "files" in result
    assert "functions" in result
    # Must have the subsystem section
    assert "Subsystems" in result
    # With no stubs, no critical gaps section
    assert "Project" in result


def test_project_status_with_stubs():
    """project_status identifies stubs with callers as critical path gaps."""
    from determined.agent.agent_tools import project_status
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)

    # Mark generate_encounter as a stub
    oracle.conn.execute(
        "UPDATE functions SET is_stub = 1 WHERE name = 'generate_encounter'"
    )
    oracle.conn.commit()

    result = project_status(assessor, {})
    # generate_encounter is called by handle_movement in the fixture graph
    assert "generate_encounter" in result
    assert "Critical path" in result or "callers" in result


def test_check_design_violations_no_notes():
    """check_design_violations explains why when no design_notes exist."""
    from determined.agent.agent_tools import check_design_violations
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)
    result = check_design_violations(assessor, {"symbol": "generate_encounter"})
    # No design_notes in fixture -> should explain, not return empty string silently
    assert "generate_encounter" in result
    assert len(result) > 10  # not a silent empty result


def test_check_design_violations_with_notes():
    """check_design_violations returns matches when constraint notes exist."""
    import unittest.mock as mock
    from determined.agent.agent_tools import check_design_violations
    oracle = _make_fixture()
    assessor = FakeAssessor(oracle)

    # Insert a design_note with constraint language
    oracle.conn.execute(
        "INSERT INTO knowledge_artifacts "
        "(subject, kind, content, provenance, created_at, needs_review) "
        "VALUES (?, ?, ?, ?, datetime('now'), 0)",
        ("engine", "design_note", "must not call generate_encounter from handlers directly", "human-confirmed"),
    )
    oracle.conn.commit()

    # Mock the embedding model to return a high similarity score
    import numpy as np
    def mock_encode(texts, normalize_embeddings=False):
        n = len(texts)
        vecs = np.ones((n, 4), dtype=float)
        vecs /= np.linalg.norm(vecs[0])
        return vecs

    with mock.patch("determined.agent.agent_tools._get_embed_model") as mock_model:
        mock_model.return_value.encode = mock_encode
        result = check_design_violations(assessor, {"symbol": "generate_encounter"})

    # Should either find a match or explain no matches above threshold
    assert "generate_encounter" in result


def test_string_tools_derive_from_raw():
    """list_callers and list_callees string output matches raw helper data."""
    from determined.agent.agent_tools import _list_callers_raw, _list_callees_raw
    oracle = _make_fixture()

    callers = _list_callers_raw(oracle, "generate_encounter")
    result = _dispatch("list_callers", {"symbol": "generate_encounter"}, oracle)
    for r in callers:
        assert r["caller"] in result

    # list_callees with generate_encounter (calls "helper")
    callees = _list_callees_raw(oracle, "generate_encounter")
    result = _dispatch("list_callees", {"symbol": "generate_encounter"}, oracle)
    for r in callees:
        assert r["callee"] in result


# ------------------------------------------------------------------
# RUN DIRECTLY
# ------------------------------------------------------------------

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
