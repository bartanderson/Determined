#!/usr/bin/env python3
"""
tools/run_tests.py  —  targeted test runner for Determined

Two levels of selection:
  1. File level  — maps changed source files to related test files (FILE_MAP below)
  2. Test level  — greps each test file for changed function names to find the
                   specific test functions that exercise those functions

Usage:
    python tools/run_tests.py                  # changed files vs HEAD (working tree)
    python tools/run_tests.py --last-commit    # files changed in the last commit
    python tools/run_tests.py --staged         # files staged for commit
    python tools/run_tests.py --files f1 f2   # explicit source file list
    python tools/run_tests.py --list           # show targets without running
    python tools/run_tests.py --full-files     # skip function-level, run whole test files

MAINTENANCE: Keep FILE_MAP in sync with docs/TEST_MAP.md when adding new source or
test files. Add a new entry and the runner picks it up automatically.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# FILE_MAP: source file (repo-relative, forward slashes) -> test files
# Mirrors docs/TEST_MAP.md — update both when adding new files.
# ---------------------------------------------------------------------------
FILE_MAP: dict[str, list[str]] = {
    # determined/agent/
    "determined/agent/agent_prompt.py": [
        "tests/regression/test_agent_prompt.py"],
    "determined/agent/context_compactor.py": [
        "tests/regression/test_context_compactor.py"],
    "determined/agent/fsm_walker.py": [
        "tests/regression/test_fsm_walker.py"],
    "determined/agent/agent_resolver.py": [
        "tests/regression/test_agent_resolver.py",
        "tests/regression/test_technique3.py"],
    "determined/agent/agent_tools.py": [
        "tests/regression/test_agent_tools.py",
        "tests/regression/test_design_gaps.py",
        "tests/regression/test_detect_conventions.py",
        "tests/regression/test_detect_topology.py",
        "tests/regression/test_feature_shape.py",
        "tests/regression/test_feature_work_plan.py",
        "tests/regression/test_find_abc_gaps.py",
        "tests/regression/test_find_bridges_and_ghosts.py",
        "tests/regression/test_goal_intake.py",
        "tests/regression/test_http_chain.py",
        "tests/regression/test_implementation_order.py",
        "tests/regression/test_infer_behavior.py",
        "tests/regression/test_readiness_check.py",
        "tests/regression/test_scaffold_from_pattern.py",
        "tests/regression/test_search_web.py",
        "tests/regression/test_technique3.py",
        "tests/regression/test_verify_and_drift.py",
        "tests/regression/test_data_flow.py",
        "tests/regression/test_completion_contract.py",
        "tests/regression/test_edit_file.py"],
    "determined/agent/claim_verifier.py": [
        "tests/regression/test_claim_verifier.py"],
    "determined/agent/classify_stub.py": [
        "tests/regression/test_classify_stub.py"],
    "determined/agent/sketch_stub.py": [
        "tests/regression/test_classify_stub.py",
        "tests/regression/test_agent_tools.py"],
    "determined/agent/export_context.py": [
        "tests/regression/test_export_context.py",
        "tests/regression/test_agent_tools.py"],
    "determined/agent/corpus_projections.py": [
        "tests/regression/test_corpus_projections.py"],
    "determined/agent/doc_extractor.py": [
        "tests/regression/test_layer_rules.py"],
    "determined/agent/evaluator.py": [
        "tests/regression/test_evaluator.py"],
    "determined/agent/pattern_executor.py": [
        "tests/regression/test_pattern_executor.py",
        "tests/regression/test_technique3.py"],
    "determined/agent/stub_classifier.py": [
        "tests/regression/test_classify_stub.py",
        "tests/regression/test_corpus_projections.py"],
    "determined/agent/stub_projector.py": [
        "tests/regression/test_scaffold_from_pattern.py"],
    "determined/agent/tool_registry.py": [
        "tests/regression/test_agent_tools.py"],
    # determined/api/
    "determined/api/oracle_router.py": [
        "tests/regression/test_oracle_router_persistence_lock.py",
        "tests/regression/test_role_view_routing.py",
        "tests/regression/test_intent_budget_calibration.py"],
    # determined/assessor/
    "determined/assessor/assessor.py": [
        "tests/regression/test_detect_topology.py",
        "tests/regression/test_discovery_api_and_subsystem_fix.py",
        "tests/regression/test_drift_signals_wiring.py",
        "tests/regression/test_integrity_view_wiring.py",
        "tests/regression/test_oracle_router_persistence_lock.py",
        "tests/regression/test_query_result_shape_contract.py",
        "tests/regression/test_role_view_routing.py",
        "tests/regression/test_run_algebra_end_to_end.py",
        "tests/regression/test_single_file_filter_scoping.py",
        "tests/regression/test_subsystem_builtin_noise_filter.py"],
    "determined/assessor/query_session.py": [
        "tests/regression/test_oracle_router_persistence_lock.py"],
    # determined/classification/
    "determined/classification/classify_references.py": [
        "tests/regression/test_call_graph_accuracy.py",
        "tests/regression/test_runtime_bindings_wiring.py"],
    # determined/contracts/
    "determined/contracts/contract_drift_classifier.py": [
        "tests/regression/test_drift_signals_wiring.py"],
    # determined/core/
    "determined/core/pathing.py": [
        "tests/regression/test_subsystem_path_pollution_fix.py"],
    # determined/engine/
    "determined/engine/run_engine.py": [
        "tests/regression/test_subsystem_path_pollution_fix.py"],
    # determined/graph/
    "determined/graph/graph_builder.py": [
        "tests/regression/test_call_graph_accuracy.py"],
    "determined/graph/semantic_candidate_builder.py": [
        "tests/regression/test_runtime_resolution_lock.py"],
    "determined/graph/symbol_resolution_engine.py": [
        "tests/regression/test_runtime_resolution_lock.py"],
    # determined/ingestion/
    "determined/ingestion/cross_language_linker.py": [
        "tests/regression/test_cross_language_linker.py"],
    "determined/ingestion/shape_scanner.py": [
        "tests/regression/test_shape_scanner.py"],
    "determined/ingestion/shape_normalizer.py": [
        "tests/regression/test_shape_normalizer.py"],
    "determined/ingestion/dynamic_edges.py": [
        "tests/regression/test_dynamic_edges.py",
        "tests/regression/test_external_interface_dispatch.py",
        "tests/regression/test_http_chain.py"],
    "determined/ingestion/language_walker.py": [
        "tests/regression/test_language_walker.py",
        "tests/regression/test_language_walker_persist.py",
        "tests/regression/test_cross_language_linker.py",
        "tests/regression/test_rust_trait_dispatch.py"],
    "determined/ingestion/parse_ast.py": [
        "tests/regression/test_call_edge_extraction.py",
        "tests/regression/test_call_graph_accuracy.py",
        "tests/regression/test_classify_role_flask.py",
        "tests/regression/test_function_reference_edges.py",
        "tests/regression/test_inline_note_extraction.py",
        "tests/regression/test_runtime_bindings_wiring.py",
        "tests/regression/test_runtime_resolution_lock.py",
        "tests/regression/test_stub_detection.py"],
    "determined/ingestion/reingest_file.py": [
        "tests/regression/test_reingest_file.py"],
    "determined/ingestion/scan_project_files.py": [
        "tests/regression/test_call_graph_accuracy.py",
        "tests/regression/test_reingest_file.py"],
    "determined/ingestion/structure_induction.py": [
        "tests/regression/test_structure_induction.py"],
    # determined/intent/
    "determined/intent/knowledge_artifact.py": [
        "tests/regression/test_intent_layer_ab.py",
        "tests/regression/test_agent_tools.py",
        "tests/regression/test_annotate_function.py",
        "tests/regression/test_annotation_pass.py",
        "tests/regression/test_infer_behavior.py",
        "tests/regression/test_ui_surfaces.py"],
    "determined/intent/semantic_summary.py": [
        "tests/regression/test_intent_layer_ab.py",
        "tests/regression/test_agent_tools.py",
        "tests/regression/test_infer_behavior.py",
        "tests/regression/test_ui_surfaces.py"],
    # determined/oracle/
    "determined/oracle/db_oracle.py": [
        "tests/regression/test_detect_topology.py",
        "tests/regression/test_discovery_api_and_subsystem_fix.py",
        "tests/regression/test_drift_signals_wiring.py",
        "tests/regression/test_embedding_seed_discovery_fallback.py",
        "tests/regression/test_integrity_view_wiring.py",
        "tests/regression/test_oracle_router_persistence_lock.py",
        "tests/regression/test_query_result_shape_contract.py",
        "tests/regression/test_role_view_routing.py",
        "tests/regression/test_run_algebra_end_to_end.py",
        "tests/regression/test_single_file_filter_scoping.py",
        "tests/regression/test_subsystem_builtin_noise_filter.py",
        "tests/regression/test_subsystem_path_pollution_fix.py",
        "tests/regression/test_system_self_model.py"],
    "determined/oracle/embedding_model.py": [
        "tests/regression/test_embedding_seed_discovery_fallback.py"],
    # determined/persistence/
    "determined/persistence/persistence_engine.py": [
        "tests/regression/test_agent_tools.py",
        "tests/regression/test_annotate_function.py",
        "tests/regression/test_annotation_pass.py",
        "tests/regression/test_artifact_layer.py",
        "tests/regression/test_call_graph_accuracy.py",
        "tests/regression/test_detect_topology.py",
        "tests/regression/test_inline_note_extraction.py",
        "tests/regression/test_language_walker_persist.py",
        "tests/regression/test_oracle_router_persistence_lock.py",
        "tests/regression/test_reingest_file.py",
        "tests/regression/test_rust_trait_dispatch.py",
        "tests/regression/test_subsystem_path_pollution_fix.py",
        "tests/regression/test_task_generator.py",
        "tests/regression/test_task_rereferencer.py",
        "tests/regression/test_ui_surfaces.py"],
    # determined/representation/
    "determined/representation/symbol_environment.py": [
        "tests/regression/test_runtime_resolution_lock.py"],
    # determined/truth/
    "determined/truth/query_ast.py": [
        "tests/regression/test_query_result_shape_contract.py",
        "tests/regression/test_role_view_routing.py",
        "tests/regression/test_run_algebra_end_to_end.py",
        "tests/regression/test_single_file_filter_scoping.py"],
    "determined/truth/query_compiler.py": [
        "tests/regression/test_query_result_shape_contract.py",
        "tests/regression/test_single_file_filter_scoping.py"],
    "determined/truth/query_executor.py": [
        "tests/regression/test_query_result_shape_contract.py",
        "tests/regression/test_role_view_routing.py",
        "tests/regression/test_run_algebra_end_to_end.py",
        "tests/regression/test_single_file_filter_scoping.py"],
    "determined/truth/query_plan.py": [
        "tests/regression/test_query_result_shape_contract.py",
        "tests/regression/test_single_file_filter_scoping.py"],
    "determined/truth/subsystem_view.py": [
        "tests/regression/test_discovery_api_and_subsystem_fix.py",
        "tests/regression/test_subsystem_builtin_noise_filter.py"],
    # determined/ui/
    "determined/ui/ui_server.py": [
        "tests/regression/test_ui_surfaces.py"],
    "determined/ui/templates/console.html": [
        "tests/regression/test_ui_surfaces.py"],
    # determined/validation/
    "determined/validation/system_validator.py": [
        "tests/regression/test_integrity_view_wiring.py"],
}


def _git(args: list[str]) -> str:
    r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else ""


def get_changed_files(staged: bool = False, last_commit: bool = False) -> list[str]:
    if last_commit:
        out = _git(["diff", "--name-only", "HEAD~1", "HEAD"])
    elif staged:
        out = _git(["diff", "--name-only", "--cached"])
    else:
        out = _git(["diff", "--name-only", "HEAD"])
    return [f.strip() for f in out.splitlines() if f.strip()]


def get_changed_functions(source_file: str, last_commit: bool = False) -> list[str]:
    """Extract names of functions added or modified in the diff."""
    if last_commit:
        diff = _git(["diff", "HEAD~1", "HEAD", "--", source_file])
    else:
        diff = _git(["diff", "HEAD", "--", source_file])
    names: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("+"):
            continue
        m = re.match(r'^\+\s*def\s+(\w+)\s*\(', line)
        if m:
            names.add(m.group(1))
    return list(names)


def find_test_targets(test_file: str, fn_names: list[str]) -> list[str]:
    """
    Return specific test::function targets if any test in test_file
    references the changed function names. Falls back to the whole file.
    """
    path = ROOT / test_file
    if not path.exists():
        return []
    if not fn_names:
        return [test_file]

    text = path.read_text(encoding="utf-8", errors="ignore")
    test_names = re.findall(r'^def (test_\w+)', text, re.MULTILINE)
    matched: list[str] = []
    for test_name in test_names:
        start = text.find(f"def {test_name}")
        next_def = text.find("\ndef ", start + 1)
        body = text[start:next_def] if next_def != -1 else text[start:]
        if any(fn in body for fn in fn_names):
            matched.append(f"{test_file}::{test_name}")

    return matched if matched else [test_file]


def build_targets(
    source_files: list[str],
    full_files: bool = False,
    last_commit: bool = False,
) -> list[str]:
    test_files: set[str] = set()
    for src in source_files:
        src = src.replace("\\", "/")
        # If the changed file IS a test file, run it directly
        if src.startswith("tests/regression/test_"):
            test_files.add(src)
            continue
        for tf in FILE_MAP.get(src, []):
            test_files.add(tf)

    if not test_files:
        return []

    if full_files:
        return sorted(test_files)

    # Gather all changed function names across all changed source files
    all_fns: list[str] = []
    for src in source_files:
        src = src.replace("\\", "/")
        if src in FILE_MAP:
            all_fns.extend(get_changed_functions(src, last_commit=last_commit))

    targets: list[str] = []
    for tf in sorted(test_files):
        targets.extend(find_test_targets(tf, all_fns))

    return targets


def main() -> int:
    p = argparse.ArgumentParser(
        description="Targeted test runner — runs only tests related to changed files."
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--files", nargs="+", metavar="FILE",
                     help="Explicit source files to look up")
    src.add_argument("--staged", action="store_true",
                     help="Use staged changes (git diff --cached)")
    src.add_argument("--last-commit", action="store_true",
                     help="Use last commit (git diff HEAD~1 HEAD)")
    p.add_argument("--list", dest="list_only", action="store_true",
                   help="Print targets without running pytest")
    p.add_argument("--full-files", action="store_true",
                   help="Run whole test files instead of specific functions")
    args = p.parse_args()

    if args.files:
        source_files = args.files
    else:
        source_files = get_changed_files(
            staged=args.staged, last_commit=args.last_commit
        )

    if not source_files:
        print("No changed source files detected.")
        return 0

    print("Changed:", ", ".join(source_files))

    targets = build_targets(
        source_files, full_files=args.full_files, last_commit=args.last_commit
    )

    if not targets:
        print("No mapped tests found. Add an entry to FILE_MAP in tools/run_tests.py.")
        return 0

    print(f"\nTargets ({len(targets)}):")
    for t in targets:
        print(f"  {t}")

    if args.list_only:
        return 0

    print()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "--no-header"] + targets,
        cwd=ROOT,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
