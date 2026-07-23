"""
run_regression.py — run the full regression suite in serial groups.

Never runs all tests at once. Groups are executed sequentially; each group
must finish before the next starts. Stops on first group failure unless
--continue-on-fail is passed.

Usage:
    python tools/run_regression.py               # all groups
    python tools/run_regression.py --list        # print groups and exit
    python tools/run_regression.py --group G1    # run one group by name
    python tools/run_regression.py --continue-on-fail

To add a new test file: append it to the last group in GROUPS, or start a
new group if the last one already has 10+ files. Do not reorder existing groups.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTEST = str(ROOT / ".venv" / "Scripts" / "pytest")
TEST_DIR = "tests/regression"

# ---------------------------------------------------------------------------
# GROUPS — serial, alphabetical batches, ~8 files each.
# Append new test files to the last group or create a new group.
# Do NOT reorder existing entries.
# ---------------------------------------------------------------------------
GROUPS: dict[str, list[str]] = {
    "G1": [
        "test_agent_prompt.py",
        "test_agent_resolver.py",
        "test_agent_tools.py",
        "test_annotate_function.py",
        "test_annotation_pass.py",
        "test_artifact_layer.py",
        "test_call_edge_extraction.py",
        "test_call_graph_accuracy.py",
    ],
    "G2": [
        "test_claim_verifier.py",
        "test_classify_role_flask.py",
        "test_classify_stub.py",
        "test_completion_contract.py",
        "test_context_compactor.py",
        "test_conventions_and_ranking.py",
        "test_corpus_projections.py",
        "test_cross_language_linker.py",
    ],
    "G3": [
        "test_data_flow.py",
        "test_design_gaps.py",
        "test_design_oracle.py",
        "test_detect_conventions.py",
        "test_detect_topology.py",
        "test_discovery_agent.py",
        "test_discovery_api_and_subsystem_fix.py",
        "test_drift_signals_wiring.py",
    ],
    "G4": [
        "test_dynamic_edges.py",
        "test_edit_file.py",
        "test_embedding_seed_discovery_fallback.py",
        "test_evaluator.py",
        "test_explain_file_wiring.py",
        "test_external_interface_dispatch.py",
        "test_feature_shape.py",
        "test_feature_work_plan.py",
    ],
    "G5": [
        "test_find_abc_gaps.py",
        "test_find_bridges_and_ghosts.py",
        "test_find_duplicates.py",
        "test_find_primitive_gaps.py",
        "test_fsm_walker.py",
        "test_function_reference_edges.py",
        "test_goal_intake.py",
        "test_graph_utils.py",
    ],
    "G6": [
        "test_graph_viz.py",
        "test_http_chain.py",
        "test_implementation_order.py",
        "test_infer_behavior.py",
        "test_inline_note_extraction.py",
        "test_integrity_view_wiring.py",
        "test_intent_budget_calibration.py",
        "test_intent_layer_ab.py",
    ],
    "G7": [
        "test_intent_view_wiring.py",
        "test_language_walker.py",
        "test_language_walker_persist.py",
        "test_layer_rules.py",
        "test_local_agent.py",
        "test_oracle_cli_smoke.py",
        "test_oracle_router_persistence_lock.py",
        "test_pattern_executor.py",
    ],
    "G8": [
        "test_query_result_shape_contract.py",
        "test_readiness_check.py",
        "test_reingest_file.py",
        "test_role_view_routing.py",
        "test_run_algebra_end_to_end.py",
        "test_runtime_bindings_wiring.py",
        "test_runtime_resolution_lock.py",
        "test_rust_trait_dispatch.py",
    ],
    "G9": [
        "test_scaffold_from_pattern.py",
        "test_search_web.py",
        "test_shape_normalizer.py",
        "test_shape_scanner.py",
        "test_single_file_filter_scoping.py",
        "test_structural_gap_tools.py",
        "test_structure_induction.py",
        "test_stub_detection.py",
    ],
    "G10": [
        "test_subsystem_builtin_noise_filter.py",
        "test_subsystem_path_pollution_fix.py",
        "test_system_self_model.py",
        "test_task_generator.py",
        "test_task_rereferencer.py",
        "test_technique3.py",
        "test_ui_surfaces.py",
        "test_verify_and_drift.py",
    ],
}


def run_group(name: str, files: list[str]) -> tuple[bool, float]:
    """Run one group. Returns (passed, elapsed_seconds)."""
    paths = [f"{TEST_DIR}/{f}" for f in files]
    cmd = [PYTEST, "-q", "--tb=short"] + paths
    print(f"\n{'='*60}")
    print(f"  {name}  ({len(files)} files)")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(ROOT))
    elapsed = time.time() - t0
    return result.returncode == 0, elapsed


def main() -> None:
    args = sys.argv[1:]
    continue_on_fail = "--continue-on-fail" in args
    args = [a for a in args if a != "--continue-on-fail"]

    if "--list" in args:
        for name, files in GROUPS.items():
            total = sum(1 for _ in files)
            print(f"{name}: {total} files")
            for f in files:
                print(f"    {f}")
        return

    if "--group" in args:
        idx = args.index("--group")
        target = args[idx + 1] if idx + 1 < len(args) else None
        if not target or target not in GROUPS:
            print(f"Unknown group. Available: {', '.join(GROUPS)}")
            sys.exit(1)
        passed, elapsed = run_group(target, GROUPS[target])
        print(f"\n{target}: {'PASS' if passed else 'FAIL'} ({elapsed:.1f}s)")
        sys.exit(0 if passed else 1)

    # Run all groups serially
    results: list[tuple[str, bool, float]] = []
    for name, files in GROUPS.items():
        passed, elapsed = run_group(name, files)
        results.append((name, passed, elapsed))
        if not passed and not continue_on_fail:
            print(f"\nStopped at {name} (use --continue-on-fail to run all groups)")
            break

    print(f"\n{'='*60}")
    print("  REGRESSION SUMMARY")
    print(f"{'='*60}")
    total_elapsed = 0.0
    all_passed = True
    for name, passed, elapsed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:6s}  {status}  {elapsed:.1f}s")
        total_elapsed += elapsed
        if not passed:
            all_passed = False

    ran = len(results)
    total = len(GROUPS)
    print(f"\n  {ran}/{total} groups ran  |  total {total_elapsed:.1f}s")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
