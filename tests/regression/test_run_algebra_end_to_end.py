# tools/analysis/tests/regression/test_run_algebra_end_to_end.py
#
# Locks in the 2026-06-16 agent-readiness fix: QuerySession.run_algebra()
# previously had ZERO callers anywhere in the codebase and had never been
# run end-to-end against real data. Assessor.all_views() / Assessor.ask()
# (assessor/assessor.py) and tools/analysis/ask.py are the real wiring
# that closes that gap.
#
# This test is the permanent proof that:
#   1. All 6 Truth Layer views (STRUCTURE/STABILITY/INTEGRITY/SUMMARY/
#      SUBSYSTEM/ROLE - ROLE added 2026-06-16/17, see
#      test_role_view_routing.py for its dedicated coverage) are
#      buildable from real DB-backed data via Assessor, not stub objects
#      (truth/tests/test_query_algebra.py covers the algebra mechanics
#      in isolation with stubs; this covers the real data path those
#      mechanics are supposed to run against).
#   2. NL to oracle router to AI compiler to AST to executor to real
#      views runs end-to-end without raising, via Assessor.ask().
#   3. The whole pipeline is deterministic: same question, same DB state,
#      same result, every time.
#
# Uses a real temp sqlite DB built through the real schema (ensure_schema),
# same fixture pattern as test_oracle_router_persistence_lock.py - no
# mocking of the DB layer.

import os
import sqlite3
import tempfile

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.truth.query_executor import QueryExecutor
from determined.truth.query_ast import Select


def _seeded_oracle():
    """
    Real temp DB, real schema, hand-seeded rows giving us a small but
    non-trivial graph: a couple of project symbols calling each other
    across two "modules" (so SUBSYSTEM grouping has something to find),
    one builtin, and one accessor-chain noise symbol.
    """
    tmp_path = tempfile.mktemp(suffix=".db")
    oracle = DBOracle(tmp_path)
    oracle.conn.row_factory = sqlite3.Row
    ensure_schema(oracle.conn)

    cur = oracle.conn.cursor()

    # NOTE: caller/callee use 3 dotted segments (moduleA.core.do_thing).
    # truth/subsystem_view.py's _module() groups by the first TWO
    # segments, so "moduleA.core.do_thing" maps to subsystem
    # "moduleA.core". Using only 2 segments would make the "module"
    # identical to the full symbol name and the subsystem grouping
    # would have nothing real to demonstrate.
    symbol_reference_rows = [
        # (file_path, caller, callee, line_number, bucket)
        ("file.py", "moduleA.core.do_thing", "moduleB.utils.helper_function", 10, "project"),
        ("file.py", "moduleB.utils.helper_function", "enumerate", 11, "builtin"),
        ("file.py", "moduleA.core.do_thing", "cursor.self.oracle.conn", 12, "project"),
        ("file.py", "moduleB.utils.helper_function", "moduleA.core.do_thing", 14, "project"),
    ]
    for file_path, caller, callee, line, bucket in symbol_reference_rows:
        cur.execute(
            "INSERT INTO symbol_references (file_path, caller, callee, line_number, bucket) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, caller, callee, line, bucket),
        )

    graph_edge_rows = [
        # (source_id, target_id, caller, callee, line_number)
        ("moduleA.core.do_thing", "moduleB.utils.helper_function",
         "moduleA.core.do_thing", "moduleB.utils.helper_function", 10),
        ("moduleB.utils.helper_function", "enumerate",
         "moduleB.utils.helper_function", "enumerate", 11),
        ("moduleB.utils.helper_function", "moduleA.core.do_thing",
         "moduleB.utils.helper_function", "moduleA.core.do_thing", 14),
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
# 1. ALL 6 VIEWS BUILD FROM REAL DATA (NOT STUBS)
# =========================================================

def test_all_views_real_data():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        views = assessor.all_views()

        assert set(views.keys()) == {
            "STRUCTURE", "STABILITY", "INTEGRITY", "SUMMARY", "SUBSYSTEM", "ROLE", "INTENT"
        }

        structure = views["STRUCTURE"]
        assert len(structure.edges) == 3
        # "enumerate" is a builtin -> excluded from hotspot ranking
        assert all(sym != "enumerate" for sym, _ in structure.hotspots)

        summary = views["SUMMARY"]
        assert summary.file_count == oracle.file_count()
        assert summary.metrics["builtin"] >= 1  # bucket_summary, DB-authoritative
        assert summary.metrics["project"] >= 1

        # CLAUDE-EDIT 2026-06-17: bracket access -> attribute access.
        # SUBSYSTEM used to be the one view (of 6) that built/returned a
        # bare dict instead of a dataclass, so this was the one place
        # subsystem["subsystems"] was needed instead of subsystem.subsystems.
        # build_subsystem_view() now returns a SubsystemView dataclass
        # (views.py) for parity with STRUCTURE/STABILITY/INTEGRITY/SUMMARY/
        # ROLE - see subsystem_view.py's CLAUDE-EDIT same date and REFACTOR
        # OPS BOARD.md's "algebra shape contract" entry.
        subsystem = views["SUBSYSTEM"]
        # moduleA.core -> moduleB.utils and moduleB.utils -> moduleA.core
        # are both real cross-module edges
        assert "moduleA.core" in subsystem.subsystems
        assert "moduleB.utils" in subsystem.subsystems["moduleA.core"]["modules"]
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 2. ALGEBRA EXECUTES AGAINST REAL SUMMARY/SUBSYSTEM VIEWS
#    (these two were orphaned with zero direct test coverage
#    before 2026-06-16 - see Truth.md Phase 1 findings)
# =========================================================

def test_algebra_select_summary_and_subsystem_real_views():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        executor = QueryExecutor(views=assessor.all_views())

        summary_result = executor.execute(Select("SUMMARY", metric="file_count"))
        assert summary_result.data == oracle.file_count()

        # Select(..., metric="subsystems") projects the field's value
        # directly (a dict), same as before - the metric=None full-view
        # path is the one that changed shape (dict -> SubsystemView), and
        # that's covered above in test_all_views_real_data.
        subsystem_result = executor.execute(Select("SUBSYSTEM", metric="subsystems"))
        assert "moduleA.core" in subsystem_result.data
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 3. END-TO-END: NL -> ROUTER -> COMPILER -> AST -> EXECUTOR
#    -> REAL VIEWS, VIA Assessor.ask() (the real entrypoint)
# =========================================================

def test_ask_runs_end_to_end_without_stubs():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        result = assessor.ask("what does moduleA.core.do_thing call")

        assert result["text"] == "what does moduleA.core.do_thing call"
        assert result["intent"] is not None
        assert result["algebra_result"] is not None
        # compiled_ast must be a real AST repr, not an error string
        assert "Select" in result["compiled_ast"] or "Combine" in result["compiled_ast"]
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


def test_ask_is_deterministic():
    """
    Same question, same DB state, twice -> identical intent and identical
    algebra result. This is the actual proof the 2026-06-16 readiness
    assessment asked for: that the full stack can run end-to-end and do
    so reproducibly, not just once by luck.
    """
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        question = "what does moduleA.core.do_thing call"

        first = assessor.ask(question)
        second = assessor.ask(question)

        assert first["intent"] == second["intent"]
        assert first["compiled_ast"] == second["compiled_ast"]
        assert first["algebra_result"] == second["algebra_result"]
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_all_views_real_data,
        test_algebra_select_summary_and_subsystem_real_views,
        test_ask_runs_end_to_end_without_stubs,
        test_ask_is_deterministic,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
