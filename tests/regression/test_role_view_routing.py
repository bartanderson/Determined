# tools/analysis/tests/regression/test_role_view_routing.py
#
# Locks in the 2026-06-16/17 ROLE view fix (Truth.md Phase 3 Row 1 / Row 2:
# "purpose of a file" / "why does X exist" / "role of X" questions had no
# path to an answer - they fell through to general_query and got a
# content-blind STABILITY+INTEGRITY diagnostic regardless of which file
# was asked about, even though Assessor.responsibility_map() already had
# real, DB-backed, per-file role classification with no caller wiring it
# into the query algebra).
#
# This test is the permanent proof that:
#   1. ROLE is a 6th real Truth Layer view, buildable from real DB-backed
#      data via Assessor.all_views() (not a stub).
#   2. Select("ROLE") executes against that real data via QueryExecutor.
#   3. _detect_intent() actually classifies purpose/why/role phrasing as
#      role_query (this is the part that silently regressed once already
#      this session via a stale .pyc cache surviving a source edit - see
#      REFACTOR OPS BOARD.md 2026-06-17 note - so this test pins behavior
#      at the _detect_intent level too, not just at the ask() level).
#   4. Assessor.ask() routes those questions end-to-end to the ROLE view
#      and returns the real per-file role data, not a Combine of unrelated
#      views.
#
# Same fixture pattern as test_run_algebra_end_to_end.py - real temp
# sqlite DB, real schema, no mocking of the DB layer.

import os
import sqlite3
import tempfile

import pytest

from determined.persistence.persistence_engine import ensure_schema
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.truth.query_executor import QueryExecutor, get_field
from determined.truth.query_ast import Select
from determined.api.oracle_router import _detect_intent


def _seeded_oracle():
    """
    Real temp DB, real schema, hand-seeded rows giving us one file whose
    callee names plainly trigger the "ingestion" role pattern (scan/parse)
    and one whose callee names trigger "persistence" (sqlite/persist), so
    role classification has something real and unambiguous to find.
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
# 1. ROLE IS A REAL 6TH VIEW, BUILT FROM REAL DATA
# =========================================================

def test_role_in_all_views_real_data():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        views = assessor.all_views()

        assert set(views.keys()) == {
            "STRUCTURE", "STABILITY", "INTEGRITY", "SUMMARY", "SUBSYSTEM", "ROLE", "INTENT"
        }

        role = views["ROLE"]
        assert role.totals.get("ingestion", 0) >= 1
        assert role.totals.get("persistence", 0) >= 1

        by_path = {f["file_path"]: f for f in role.files}
        assert by_path["ingest.py"]["roles"]["ingestion"] is True
        assert by_path["store.py"]["roles"]["persistence"] is True
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 2. ALGEBRA EXECUTES Select("ROLE") AGAINST REAL DATA
# =========================================================

def test_algebra_select_role_real_view():
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        executor = QueryExecutor(views=assessor.all_views())

        totals_result = executor.execute(Select("ROLE", metric="totals"))
        assert totals_result.data.get("ingestion", 0) >= 1

        files_result = executor.execute(Select("ROLE", metric="files"))
        paths = {f["file_path"] for f in files_result.data}
        assert {"ingest.py", "store.py"} <= paths
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


# =========================================================
# 3. INTENT CLASSIFICATION: purpose/why/role phrasing -> role_query
#
# Pins _detect_intent() directly, not just through ask(), because this
# exact function silently regressed once already this session (a stale
# .pyc cache in __pycache__ had matching mtime+size to an intermediate
# saved version of the source and was loaded instead of the current
# file's compiled code, with no error surfaced - see REFACTOR OPS
# BOARD.md 2026-06-17 note). Catching it at this level means a future
# recurrence of that exact failure mode fails this test directly instead
# of silently falling back to general_query again.
# =========================================================

def test_detect_intent_routes_purpose_questions_to_role_query():
    for text in [
        "what is the purpose of assessor.py",
        "why does symbol_noise.py exist",
        "why is ingest.py here",
        "what is the role of oracle_router",
        "what role does store.py play",
        "what kind of file is ingest.py",
    ]:
        assert _detect_intent(text) == "role_query", (
            f"expected role_query for {text!r}, got {_detect_intent(text)!r}"
        )


# =========================================================
# 4. END-TO-END: NL -> ROUTER -> COMPILER -> AST -> EXECUTOR
#    -> REAL ROLE VIEW, VIA Assessor.ask()
# =========================================================

@pytest.mark.slow
def test_ask_purpose_question_routes_to_role_view():
    # CLAUDE-EDIT 2026-06-17: was data.totals / data.files directly, which
    # assumed Select("ROLE") (metric=None) was the only legitimate AST the
    # compiler could produce for this question. It isn't: Select("ROLE",
    # metric="files") is an equally valid, registry-checked choice for a
    # question naming one specific file (and is in fact the one the local
    # Ollama compiler picked on Bart's Windows machine, where it's actually
    # reachable - unreachable in the sandbox, so the rule-based fallback's
    # plain Select("ROLE") was the only shape ever exercised here before).
    # get_field() reads whichever real shape came back instead of assuming
    # one. See query_executor.py's get_field() CLAUDE-EDIT 2026-06-17 and
    # REFACTOR OPS BOARD.md's "algebra shape contract" entry, same date.
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        result = assessor.ask("what is the purpose of ingest.py")

        assert result["intent"] == "role_query"
        assert "Select" in result["compiled_ast"]
        assert "Combine" not in result["compiled_ast"]

        algebra_result = result["algebra_result"]
        files = get_field(algebra_result, "files")
        totals = get_field(algebra_result, "totals")

        assert files is not None or totals is not None, (
            "expected a ROLE-view result to expose at least one of "
            "files/totals, regardless of which valid metric was selected"
        )

        if totals is not None:
            assert totals.get("ingestion", 0) >= 1

        if files is not None:
            by_path = {f["file_path"]: f for f in files}
            assert by_path["ingest.py"]["roles"]["ingestion"] is True
    finally:
        oracle.conn.close()
        os.remove(tmp_path)



@pytest.mark.slow
def test_ask_role_question_is_deterministic():
    # CLAUDE-EDIT 2026-06-17 (later): was asserting first["compiled_ast"] ==
    # second["compiled_ast"] (and algebra_result equality on top of that) -
    # byte-identical AST across two separate live-Ollama calls. That's the
    # same wrong assumption as the original bug this file exists to guard
    # against, just one level up: for "what is the role of store.py",
    # Select("ROLE") and Select("ROLE", metric="files") are BOTH valid,
    # registry-checked compilations (query_compiler.py's MAPPING GUIDANCE
    # only says "prefer files when one file is named" - a preference, not a
    # hard constraint), and an LLM compiler at temperature 0.0 is not
    # guaranteed to land on the same one across separate calls (greedy
    # decoding is not bit-reproducible across requests in practice - known
    # llama.cpp/Ollama behavior from floating-point non-associativity in
    # parallel reduction, not a bug in this codebase). Bart hit this for
    # real on his Windows machine (first/second compiled_ast differed).
    # The correct invariant for an LLM-backed compiler that can validly
    # pick from a family of correct ASTs is "same answer content", not
    # "same AST text" - exactly the get_field() principle from
    # test_ask_purpose_question_routes_to_role_view above. See
    # REFACTOR OPS BOARD.md's 2026-06-17 "algebra shape contract audit"
    # entry and its determinism-test follow-up entry, same date.
    oracle, tmp_path = _seeded_oracle()
    try:
        assessor = Assessor(oracle)
        question = "what is the role of store.py"

        first = assessor.ask(question)
        second = assessor.ask(question)

        assert first["intent"] == second["intent"] == "role_query"

        for result in (first, second):
            files = get_field(result["algebra_result"], "files")
            totals = get_field(result["algebra_result"], "totals")
            assert files is not None or totals is not None, (
                "expected a ROLE-view result to expose at least one of "
                "files/totals, regardless of which valid metric was selected"
            )
            if files is not None:
                by_path = {f["file_path"]: f for f in files}
                assert by_path["store.py"]["roles"]["persistence"] is True
            if totals is not None:
                assert totals.get("persistence", 0) >= 1
    finally:
        oracle.conn.close()
        os.remove(tmp_path)


if __name__ == "__main__":
    tests = [
        test_role_in_all_views_real_data,
        test_algebra_select_role_real_view,
        test_detect_intent_routes_purpose_questions_to_role_query,
        test_ask_purpose_question_routes_to_role_view,
        test_ask_role_question_is_deterministic,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
