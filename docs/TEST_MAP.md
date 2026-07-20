# Test Map

For any change, run the listed test file(s) first. Run the full suite only before committing.

```
pytest tests/regression/<file>  [<file2> ...]
```

---

## determined/agent/

| Source module | Test file(s) |
|---|---|
| agent_prompt.py | test_agent_prompt.py |
| agent_resolver.py | test_agent_resolver.py test_technique3.py |
| agent_tools.py | test_agent_tools.py test_design_gaps.py test_detect_topology.py test_feature_shape.py test_feature_work_plan.py test_find_abc_gaps.py test_find_bridges_and_ghosts.py test_goal_intake.py test_http_chain.py test_implementation_order.py test_infer_behavior.py test_readiness_check.py test_scaffold_from_pattern.py test_search_web.py test_technique3.py test_verify_and_drift.py test_data_flow.py test_completion_contract.py test_edit_file.py |
| claim_verifier.py | test_claim_verifier.py |
| classify_stub.py | test_classify_stub.py |
| corpus_projections.py | test_corpus_projections.py |
| doc_extractor.py | test_layer_rules.py |
| evaluator.py | test_evaluator.py |
| pattern_executor.py | test_pattern_executor.py test_technique3.py |
| stub_classifier.py | test_classify_stub.py test_corpus_projections.py |
| stub_projector.py | test_scaffold_from_pattern.py |

## determined/api/

| Source module | Test file(s) |
|---|---|
| oracle_router.py | test_oracle_router_persistence_lock.py test_role_view_routing.py test_intent_budget_calibration.py |

## determined/assessor/

| Source module | Test file(s) |
|---|---|
| assessor.py | test_detect_topology.py test_discovery_api_and_subsystem_fix.py test_drift_signals_wiring.py test_integrity_view_wiring.py test_oracle_router_persistence_lock.py test_query_result_shape_contract.py test_role_view_routing.py test_run_algebra_end_to_end.py test_single_file_filter_scoping.py test_subsystem_builtin_noise_filter.py |
| query_session.py | test_oracle_router_persistence_lock.py |

## determined/classification/

| Source module | Test file(s) |
|---|---|
| classify_references.py | test_call_graph_accuracy.py test_runtime_bindings_wiring.py |

## determined/contracts/

| Source module | Test file(s) |
|---|---|
| contract_drift_classifier.py | test_drift_signals_wiring.py |

## determined/core/

| Source module | Test file(s) |
|---|---|
| pathing.py | test_subsystem_path_pollution_fix.py |

## determined/engine/

| Source module | Test file(s) |
|---|---|
| run_engine.py | test_subsystem_path_pollution_fix.py |

## determined/graph/

| Source module | Test file(s) |
|---|---|
| graph_builder.py | test_call_graph_accuracy.py |
| semantic_candidate_builder.py | test_runtime_resolution_lock.py |
| symbol_resolution_engine.py | test_runtime_resolution_lock.py |

## determined/ingestion/

| Source module | Test file(s) |
|---|---|
| cross_language_linker.py | test_cross_language_linker.py |
| shape_scanner.py | test_shape_scanner.py |
| dynamic_edges.py | test_dynamic_edges.py test_external_interface_dispatch.py test_http_chain.py |
| language_walker.py | test_language_walker.py test_language_walker_persist.py test_cross_language_linker.py test_rust_trait_dispatch.py |
| parse_ast.py | test_call_edge_extraction.py test_call_graph_accuracy.py test_classify_role_flask.py test_function_reference_edges.py test_inline_note_extraction.py test_runtime_bindings_wiring.py test_runtime_resolution_lock.py test_stub_detection.py |
| reingest_file.py | test_reingest_file.py |
| scan_project_files.py | test_call_graph_accuracy.py test_reingest_file.py |
| structure_induction.py | test_structure_induction.py |

## determined/intent/

| Source module | Test file(s) |
|---|---|
| knowledge_artifact.py | test_intent_layer_ab.py test_agent_tools.py test_annotate_function.py test_annotation_pass.py test_infer_behavior.py test_ui_surfaces.py |
| semantic_summary.py | test_intent_layer_ab.py test_agent_tools.py test_infer_behavior.py test_ui_surfaces.py |

## determined/oracle/

| Source module | Test file(s) |
|---|---|
| db_oracle.py | test_detect_topology.py test_discovery_api_and_subsystem_fix.py test_drift_signals_wiring.py test_embedding_seed_discovery_fallback.py test_integrity_view_wiring.py test_oracle_router_persistence_lock.py test_query_result_shape_contract.py test_role_view_routing.py test_run_algebra_end_to_end.py test_single_file_filter_scoping.py test_subsystem_builtin_noise_filter.py test_subsystem_path_pollution_fix.py test_system_self_model.py |
| embedding_model.py | test_embedding_seed_discovery_fallback.py |

## determined/persistence/

| Source module | Test file(s) |
|---|---|
| persistence_engine.py | test_agent_tools.py test_annotate_function.py test_annotation_pass.py test_artifact_layer.py test_call_graph_accuracy.py test_detect_topology.py test_inline_note_extraction.py test_language_walker_persist.py test_oracle_router_persistence_lock.py test_reingest_file.py test_rust_trait_dispatch.py test_subsystem_path_pollution_fix.py test_task_generator.py test_task_rereferencer.py test_ui_surfaces.py |

## determined/representation/

| Source module | Test file(s) |
|---|---|
| symbol_environment.py | test_runtime_resolution_lock.py |

## determined/truth/

| Source module | Test file(s) |
|---|---|
| query_ast.py | test_query_result_shape_contract.py test_role_view_routing.py test_run_algebra_end_to_end.py test_single_file_filter_scoping.py |
| query_compiler.py | test_query_result_shape_contract.py test_single_file_filter_scoping.py |
| query_executor.py | test_query_result_shape_contract.py test_role_view_routing.py test_run_algebra_end_to_end.py test_single_file_filter_scoping.py |
| query_plan.py | test_query_result_shape_contract.py test_single_file_filter_scoping.py |
| subsystem_view.py | test_discovery_api_and_subsystem_fix.py test_subsystem_builtin_noise_filter.py |

## determined/ui/

| Source module | Test file(s) |
|---|---|
| ui_server.py | test_ui_surfaces.py |
| templates/console.html | test_ui_surfaces.py |

## determined/validation/

| Source module | Test file(s) |
|---|---|
| system_validator.py | test_integrity_view_wiring.py |

---

## Broad-impact modules (run these extra test groups when touching them)

These modules are imported by many tests — a change here warrants running more than just the direct match:

- **persistence_engine.py** — imported by ~15 test files; run `test_agent_tools.py test_language_walker_persist.py test_reingest_file.py` as minimum, full suite before commit
- **agent_tools.py** — imported by ~10 test files; run `test_agent_tools.py test_design_gaps.py test_feature_shape.py test_find_abc_gaps.py` as minimum
- **db_oracle.py** — imported by ~12 test files; run `test_detect_topology.py test_oracle_router_persistence_lock.py test_role_view_routing.py` as minimum
- **parse_ast.py** — imported by ~8 test files; run `test_stub_detection.py test_call_edge_extraction.py test_call_graph_accuracy.py` as minimum
