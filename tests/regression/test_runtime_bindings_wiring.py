# tools/analysis/tests/regression/test_runtime_bindings_wiring.py
#
# TRACKER.md item 23: dead runtime_bindings wiring.
#
# scan_project_files.py passes a permanent `runtime_bindings = {}`
# placeholder into parse_ast(), and parse_ast() set FileAnalysis.runtime_bindings
# directly from that parameter - even though _extract_symbol_references()
# (called from inside the same parse_ast()) already computes the real,
# tree-derived bindings via _extract_runtime_bindings() for its OWN
# internal use, then discards them. The result: classify_references()'s
# production routing call - route_symbol(name=ref.callee,
# runtime_bindings=analysis.runtime_bindings, ...) - always received an
# empty dict, so the "runtime" bucket could never be assigned in
# production, no matter what the source actually contained.
#
# The existing unit test (test_symbol_classification_runtime_contract.py)
# never caught this because it builds its fixtures by calling
# _extract_runtime_bindings() directly and feeding the result straight
# into ProjectGraphContext/route_symbol - it never goes through
# FileAnalysis.runtime_bindings or scan_project_files()/parse_ast() at
# all, so it was structurally incapable of noticing the wiring gap.
#
# This test goes through the REAL pipeline entrypoints
# (parse_ast() -> classify_references()) - the same two calls
# analyze_files()/scan_project_files() chain together in production -
# against a fixture with a real runtime attribute-chain binding
# (`ai = engine.ai_system`), and proves the resulting SymbolReference
# is classified bucket="runtime" end-to-end, not via direct-fixture
# construction.

import os

from determined.ingestion.parse_ast import parse_ast
from determined.classification.classify_references import classify_references

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "sample_project",
    "runtime_bucket_case.py",
)


def _real_pipeline_analysis():
    """
    Mirrors analyze_files() in scan_project_files.py: parse_ast() with
    project_symbols attached afterward, exactly as production does it.
    """
    analysis = parse_ast(
        FIXTURE,
        global_known_symbols=set(),
        runtime_bindings={},  # the same permanent placeholder scan_project_files.py passes
    )
    assert analysis is not None
    analysis.project_symbols = set()
    return analysis


def test_parse_ast_populates_real_runtime_bindings():
    """
    FileAnalysis.runtime_bindings must reflect the tree-derived bindings
    parse_ast() actually computed, not the always-empty placeholder
    parameter scan_project_files.py passes in.
    """
    analysis = _real_pipeline_analysis()

    assert analysis.runtime_bindings != {}
    assert analysis.runtime_bindings.get("ai") == "engine.ai_system"
    assert analysis.runtime_bindings.get("engine.ai_system") == "ai"


def test_classify_references_assigns_runtime_bucket_end_to_end():
    """
    The actual production call site (classify_references -> route_symbol)
    must classify the `ai()` call as bucket="runtime", using nothing but
    real pipeline output - no direct ProjectGraphContext construction.
    """
    analysis = _real_pipeline_analysis()
    classify_references(analysis, project_prefixes=[])

    runtime_refs = [r for r in analysis.symbol_references if r.bucket == "runtime"]
    assert runtime_refs, (
        f"expected at least one bucket='runtime' reference, got buckets: "
        f"{[r.bucket for r in analysis.symbol_references]}"
    )
    assert any(r.callee == "engine.ai_system" for r in runtime_refs)


def test_regression_guard_empty_runtime_bindings_loses_the_bucket():
    """
    Locks in WHY the fix matters: forcing FileAnalysis.runtime_bindings
    back to {} (the exact pre-fix production state) on the same fixture
    must change the classification away from "runtime" - proving this
    test would have failed against the old code, not just passed
    trivially regardless of the bug.
    """
    analysis = _real_pipeline_analysis()
    analysis.runtime_bindings = {}  # simulate pre-fix production state
    classify_references(analysis, project_prefixes=[])

    assert not any(r.bucket == "runtime" for r in analysis.symbol_references)


if __name__ == "__main__":
    tests = [
        test_parse_ast_populates_real_runtime_bindings,
        test_classify_references_assigns_runtime_bucket_end_to_end,
        test_regression_guard_empty_runtime_bindings_loses_the_bucket,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print("ALL TESTS PASSED")
