# tools/analysis/tests/regression/test_query_result_shape_contract.py
#
# CLAUDE-EDIT 2026-06-17: new regression suite closing out the "full
# mapping" audit Bart asked for after the Windows-only
# test_ask_purpose_question_routes_to_role_view AttributeError (see
# REFACTOR OPS BOARD.md 2026-06-17 "algebra shape contract" entry).
#
# That bug happened because a single consumer assumed QueryResult.data
# always had one fixed shape. The real contract is:
#   metric is None  -> data is the full view object (attribute access)
#   metric == "X"   -> data IS the value of field X already (no wrapper)
# get_field() (query_executor.py) is the shared accessor meant to make
# that contract impossible to get wrong from now on. This suite is the
# permanent proof that:
#   1. get_field() agrees with direct metric-selection, for every single
#      (view, metric) pair in the real registry - not just ROLE, all 6
#      views and all ~15 metrics, against real DB-backed data, not stubs.
#   2. get_field() returns the documented default (not a wrong value, not
#      a crash) when asked for a field that a *different* metric selection
#      legitimately doesn't carry.
#   3. SUBSYSTEM's full-view (metric=None) shape is attribute-accessible
#      like every other view, locking in the SubsystemView dataclass fix
#      (views.py / subsystem_view.py CLAUDE-EDIT 2026-06-17) so this
#      specific inconsistency can't quietly come back as a bare dict.
#   4. The AI-compiler prompt spec (_ALGEBRA_SPEC) can never silently
#      drift out of sync with the registry it's generated from, because
#      it's generated from QueryPlan.VALID_METRICS /
#      QuerySemanticsRegistry.VALID_COMBINES directly rather than
#      hand-duplicated text (query_compiler.py CLAUDE-EDIT 2026-06-17).
#
# Same fixture pattern as test_run_algebra_end_to_end.py / test_role_view
# _routing.py - real temp sqlite DB, real schema, no mocking of the DB
# layer.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.truth.query_executor import QueryExecutor, get_field
from determined.truth.query_ast import Select
from determined.truth.query_plan import QueryPlan, QuerySemanticsRegistry
from determined.truth.query_compiler import _ALGEBRA_SPEC


def _seeded_oracle():
    """
    Real temp DB, real schema, enough rows to give every one of the 6
    views non-empty content to compare shapes against (an all-empty view
    would let a broken get_field() pass by accident on None == None).
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    symbol_reference_rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("ingest.py", "ingest.run", "scanner.scan_file", 10, "project"),
        ("ingest.py", "ingest.run", "ast.parse", 11, "project"),
        ("store.py", "store.save", "sqlite3.connect", 20, "project"),
        ("store.py", "store.save", "persist_record", 21, "project"),
        ("store.py", "store.save", "enumerate", 22, "builtin"),
    ]
    for file_path, caller, callee, line, bucket in symbol_reference_rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line, bucket),
        )

    graph_edge_rows = [
        # (source_id, target_id, caller, callee, line_number)
        ("ingest.run", "scanner.scan_file", "ingest.run", "scanner.scan_file", 10),
        ("ingest.run", "ast.parse", "ingest.run", "ast.parse", 11),
        ("store.save", "sqlite3.connect", "store.save", "sqlite3.connect", 20),
        ("store.save", "enumerate", "store.save", "enumerate", 22),
    ]
    for source_id, target_id, caller, callee, line in graph_edge_rows:
        cur.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, line_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_id, target_id, caller, callee, line),
        )

    oracle.conn.commit()

    return oracle, tmp_path


# =========================================================
# 1. get_field() AGREES WITH DIRECT METRIC SELECTION,
#    FOR EVERY (view, metric) PAIR IN THE REAL REGISTRY
# =========================================================

def test_get_field_matches_direct_selection_for_every_view_and_metric():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        views = assessor.all_views()
        executor = QueryExecutor(views=views)

        assert set(views.keys()) == set(QueryPlan.VALID_METRICS.keys()), (
            "Assessor.all_views() must expose exactly the views the "
            "registry knows about - if these drift apart, either a real "
            "view is unreachable through the algebra, or the registry is "
            "advertising a view that doesn't exist."
        )

        checked = []
        for view_name, metrics in QueryPlan.VALID_METRICS.items():
            full_result = executor.execute(Select(view_name))

            for metric in metrics:
                projected_result = executor.execute(Select(view_name, metric=metric))
                via_get_field = get_field(full_result, metric)

                assert via_get_field == projected_result.data, (
                    f"get_field(full {view_name} view, '{metric}') disagreed "
                    f"with Select({view_name!r}, metric={metric!r}).data - "
                    f"the shape contract is broken for this pair"
                )
                checked.append((view_name, metric))

        # Sanity check on the audit itself: make sure we actually exercised
        # every metric in the registry, not a stale/partial subset.
        expected_pairs = {
            (view, metric)
            for view, metrics in QueryPlan.VALID_METRICS.items()
            for metric in metrics
        }
        assert set(checked) == expected_pairs
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 2. get_field() RETURNS THE DOCUMENTED DEFAULT WHEN A
#    DIFFERENT METRIC WAS SELECTED - NEVER A CRASH, NEVER
#    A WRONG VALUE
# =========================================================

def test_get_field_returns_default_for_mismatched_metric():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        executor = QueryExecutor(views=assessor.all_views())

        files_only = executor.execute(Select("ROLE", metric="files"))

        # "totals" genuinely isn't part of this result (a different,
        # equally valid metric was selected) - must come back as the
        # default, not raise, not silently return the files list.
        assert get_field(files_only, "totals") is None
        assert get_field(files_only, "totals", default="MISSING") == "MISSING"

        # The metric that *was* selected still works directly.
        assert get_field(files_only, "files") == files_only.data
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 3. SUBSYSTEM'S FULL VIEW IS ATTRIBUTE-ACCESSIBLE LIKE
#    EVERY OTHER VIEW (locks in the SubsystemView dataclass fix)
# =========================================================

def test_all_full_views_are_attribute_accessible():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        views = assessor.all_views()

        for view_name, view_obj in views.items():
            assert not isinstance(view_obj, dict), (
                f"{view_name}'s full view (metric=None) is a bare dict - "
                f"every other Truth Layer view is a dataclass with "
                f"attribute access. This is the exact SUBSYSTEM-was-a-dict "
                f"inconsistency fixed 2026-06-17; it must not come back."
            )
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 4. THE AI-COMPILER PROMPT SPEC CANNOT SILENTLY DRIFT FROM
#    THE REGISTRY IT'S GENERATED FROM
# =========================================================

def test_algebra_spec_reflects_every_view_metric_and_combine():
    for view, metrics in QueryPlan.VALID_METRICS.items():
        assert view in _ALGEBRA_SPEC, (
            f"{view} missing from the AI compiler's prompt spec - "
            f"the model would never be told this view exists"
        )
        for metric in metrics:
            assert metric in _ALGEBRA_SPEC, (
                f"metric '{metric}' (view {view}) missing from the AI "
                f"compiler's prompt spec"
            )

    for left, right in QuerySemanticsRegistry.VALID_COMBINES:
        assert f"({left}, {right})" in _ALGEBRA_SPEC, (
            f"combine pair ({left}, {right}) missing from the AI "
            f"compiler's prompt spec"
        )


if __name__ == "__main__":
    tests = [
        test_get_field_matches_direct_selection_for_every_view_and_metric,
        test_get_field_returns_default_for_mismatched_metric,
        test_all_full_views_are_attribute_accessible,
        test_algebra_spec_reflects_every_view_metric_and_combine,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
