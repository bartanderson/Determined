# tools/analysis/tests/regression/test_single_file_filter_scoping.py
#
# Locks in the 2026-06-17 single-named-file ROLE scoping fix (the bug Bart
# hit directly on his Windows machine: "what is the purpose of
# db_probe_toolsold.py" came back with the FULL unfiltered ROLE view - every
# file in the project - instead of just the one file named in the question).
#
# Root cause had three independent layers, all fixed together:
#   1. truth/query_ast.py's Filter and truth/query_executor.py's
#      _apply_filter were both fully implemented and already passing
#      planner-validation tests, but NOTHING upstream (neither the Ollama
#      prompt spec nor the rule-based fallback table in query_compiler.py)
#      ever constructed a Filter. Select.filter was None end-to-end. Same
#      "orphaned primitive" shape as the 2026-06-17 drift_signals fix.
#   2. QueryExecutor._select() applied Filter to the bare view object
#      BEFORE metric projection. Every real view is a dataclass, not a
#      dict/list, so _apply_filter's isinstance checks always fell through
#      to "return data unchanged" - even a correctly-constructed Filter
#      would have silently done nothing. Fixed by filtering AFTER
#      projection, against the actual projected list (ROLE's "files").
#   3. QuerySemanticsRegistry.VALID_FILTER_KEYS had no "ROLE" entry at all -
#      a Filter on ROLE would have been rejected by
#      QueryPlanner._validate_select() even if one had ever been built.
#
# The actual fix (query_compiler.py's _extract_single_file_filter() /
# _maybe_scope_to_named_file()) is deterministic regex + a planner-
# revalidated Filter, not an AI-compiler responsibility - the buggy run
# that surfaced this went through Ollama and still produced metric=None
# despite the prompt explicitly preferring metric="files" for one-named-
# file questions, proving prompt compliance isn't guaranteed even at
# temperature 0.0.
#
# Same fixture pattern as test_role_view_routing.py / test_run_algebra_
# end_to_end.py - real temp sqlite DB, real schema, no mocking of the DB
# layer.

import os
import sqlite3
import tempfile

import pytest

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.truth.query_ast import Select, Filter
from determined.truth.query_plan import QueryPlan
from determined.truth.query_executor import QueryExecutor, get_field
from determined.truth.query_compiler import (
    _extract_single_file_filter,
    _maybe_scope_to_named_file,
)


def _seeded_oracle():
    """
    Real temp DB, real schema, two files with distinct role-triggering
    callees so a single-file question has two real candidates to be
    wrongly mixed up with if scoping fails.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    symbol_reference_rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("db_probe_toolsold.py", "probe.run", "sqlite3.connect", 10, "project"),
        ("db_probe_toolsold.py", "probe.run", "persist_record", 11, "project"),
        ("ingest.py", "ingest.run", "scanner.scan_file", 20, "project"),
        ("ingest.py", "ingest.run", "ast.parse", 21, "project"),
    ]
    for file_path, caller, callee, line, bucket in symbol_reference_rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line, bucket),
        )

    oracle.conn.commit()
    return oracle, tmp_path


# =========================================================
# 1. _extract_single_file_filter(): unit behavior
# =========================================================

def test_extract_single_file_filter_one_file_named():
    f = _extract_single_file_filter("what is the purpose of db_probe_toolsold.py")
    assert f == Filter("file_path", "endswith", "db_probe_toolsold.py")


def test_extract_single_file_filter_zero_files_named():
    assert _extract_single_file_filter("what is the purpose of this system") is None


def test_extract_single_file_filter_multiple_files_named():
    text = "what depends on a.py and b.py"
    assert _extract_single_file_filter(text) is None


# =========================================================
# 2. _maybe_scope_to_named_file(): rescoping behavior
# =========================================================

def test_scope_rescopes_bare_role_select_with_named_file():
    plan = QueryPlan(root=Select("ROLE"))
    scoped = _maybe_scope_to_named_file(plan, "what is the purpose of db_probe_toolsold.py")

    assert scoped.root.view == "ROLE"
    assert scoped.root.metric == "files"
    assert scoped.root.filter == Filter("file_path", "endswith", "db_probe_toolsold.py")


def test_scope_leaves_plan_unchanged_when_metric_already_chosen():
    # A compiler (Ollama or rule-based) that already picked a specific
    # metric made a deliberate choice - this must not be silently
    # overridden, even if the question also names a file.
    plan = QueryPlan(root=Select("ROLE", metric="totals"))
    scoped = _maybe_scope_to_named_file(plan, "what is the purpose of db_probe_toolsold.py")

    assert scoped.root.metric == "totals"
    assert scoped.root.filter is None


def test_scope_leaves_plan_unchanged_when_filter_already_set():
    existing_filter = Filter("file_path", "endswith", "ingest.py")
    plan = QueryPlan(root=Select("ROLE", metric="files", filter=existing_filter))
    scoped = _maybe_scope_to_named_file(plan, "what is the purpose of db_probe_toolsold.py")

    assert scoped.root.filter == existing_filter


def test_scope_leaves_plan_unchanged_when_no_file_named():
    plan = QueryPlan(root=Select("ROLE"))
    scoped = _maybe_scope_to_named_file(plan, "what is the purpose of this system")

    assert scoped.root.metric is None
    assert scoped.root.filter is None


def test_scope_leaves_non_role_select_unchanged():
    plan = QueryPlan(root=Select("STRUCTURE"))
    scoped = _maybe_scope_to_named_file(plan, "what is the purpose of db_probe_toolsold.py")

    assert scoped.root.view == "STRUCTURE"
    assert scoped.root.metric is None
    assert scoped.root.filter is None


# =========================================================
# 3. EXECUTOR: filter actually narrows real DB-backed ROLE data
#    (the part that was previously a silent no-op - see fix #2 above)
# =========================================================

def test_executor_filters_role_files_to_named_file_only():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        executor = QueryExecutor(views=assessor.all_views())

        query = Select(
            "ROLE",
            metric="files",
            filter=Filter("file_path", "endswith", "db_probe_toolsold.py"),
        )
        result = executor.execute(query)

        assert len(result.data) == 1
        assert result.data[0]["file_path"] == "db_probe_toolsold.py"
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 4. END-TO-END: a real "what is the purpose of X.py" question against a
#    real seeded DB returns exactly that file's entry, not the whole
#    project - the literal bug Bart hit, reproduced and proven fixed.
# =========================================================

@pytest.mark.slow
def test_ask_single_named_file_returns_only_that_file():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        result = assessor.ask("what is the purpose of db_probe_toolsold.py")

        assert result["intent"] == "role_query"

        files = get_field(result["algebra_result"], "files")
        assert files is not None, "expected metric='files' once a single file is named"
        assert len(files) == 1, (
            f"expected exactly one file (the one named in the question), "
            f"got {len(files)}: {[f['file_path'] for f in files]}"
        )
        assert files[0]["file_path"] == "db_probe_toolsold.py"
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_extract_single_file_filter_one_file_named,
        test_extract_single_file_filter_zero_files_named,
        test_extract_single_file_filter_multiple_files_named,
        test_scope_rescopes_bare_role_select_with_named_file,
        test_scope_leaves_plan_unchanged_when_metric_already_chosen,
        test_scope_leaves_plan_unchanged_when_filter_already_set,
        test_scope_leaves_plan_unchanged_when_no_file_named,
        test_scope_leaves_non_role_select_unchanged,
        test_executor_filters_role_files_to_named_file_only,
        test_ask_single_named_file_returns_only_that_file,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
