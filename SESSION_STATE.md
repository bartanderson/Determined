Written at commit: 77fccdd

# SESSION STATE — session 224
Written at commit: 77fccdd (2026-07-20)

## Active branch: main [V]

## What happened this session

**Lesson locked: stale handoff → mention and move on [V]**

SESSION_STATE said "RM69 step 5 corpus aggregation" was next. Pre-code checklist
found all three projections already implemented and 42/42 tests passing. Right
response: one-sentence mention, update docs, proceed. No re-test needed to confirm
what the code already proves.

**RM69 corpus aggregation — confirmed DONE [V]**

stub_file_shape, stub_subsystem_shape, stub_prerequisite_map all in corpus_projections.py,
wired in agent_tools.py, 42 tests passing. Smoke test against live dj2 correct.

**RM71 Phase 1 — shape scanner shipped [V]**

Wrong start: began writing fsm_ingestor.py (format-specific). Bart corrected: wrong
abstraction. Deleted it. Built determined/ingestion/shape_scanner.py instead:
- Format-agnostic: JSON/YAML/TOML (structured) + .md/.txt/.rst (prose)
- Four passes: node_collection, reference, topology, hierarchy
- Convergence gating → ShapeFinding(kind, confidence, missing_refs)
- Runs automatically at ingest end (hooked into ui_server.py)
- Agent tool: list_shape_findings()
- 13/13 tests [V]
- Smoke test on dj2: 39 findings, all 5 FSMs at 100% confidence [V]
- encounter.json: directed_graph, 4 nodes, 5 edges [V]

**RM71 Phase 2 — normalizer shipped [V]**

determined/ingestion/shape_normalizer.py:
- Driven by shape_finding artifacts (not format assumptions)
- High-confidence directed_graph findings re-parsed → graph_edges (edge_type='config_edge')
- States/actions/guards → knowledge_artifacts (fsm_state/fsm_action/fsm_guard)
- Idempotent (skips files already normalized)
- Agent tool: normalize_shape_findings()
- 14/14 tests [V]
- E2E on dj2: 5 FSMs, 27 edges, 16 nodes [V]
- encounter.json: start_combat linked to awaiting_choice → resolving_fight [V]

**Design decision: shape scanner philosophy [V]**

Not per-format parsers. Multi-method induction mirroring structure_induction.py.
Scope: all non-code files. Investigative scanner reports findings; normalizer
writes graph edges from high-confidence hits. Bart's framing: "it just runs and reports."

## Known issues [V = verified, ? = recalled]

**`_get_combat_context` UNCERTAIN [?]:** Was UNCERTAIN at session start. RM71 phase 2
now puts start_combat + encounter FSM edges in graph_edges. Classify_stub probe not
yet run with new config-edge data — resolution unverified this session.

**Prose false positives in shape scanner [V]:** .recall/history.md (95%) and
SESSION_STATE.md (65%) detected as directed_graph from -> arrows in prose. Normalizer
correctly errors on these ("could not parse") since it only handles structured formats.
Acceptable for now.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**Verify `_get_combat_context` resolution.** Run classify_stub on _get_combat_context
against a freshly re-ingested dj2 DB (so config_edge rows are present). Expected:
UNCERTAIN → blocked-on-prerequisite with config-layer evidence from encounter.json.

Command to test:
```
.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.')
from determined.oracle.db_oracle import DBOracle
from determined.assessor.assessor import Assessor
from determined.agent.classify_stub import classify_stub
oracle = DBOracle('C_Users_bartl_dev_dj2.db')
assessor = Assessor(oracle)
print(classify_stub(assessor, {'name': '_get_combat_context'}))
"
```

If still UNCERTAIN: the classify_stub signal extraction doesn't yet query config_edge
rows. Check stub_classifier.py for where corpus signals are gathered and add a
config_edge presence check.

If resolved: move to RM70 (convention detector) or RM69 ranking integration per
TRACKER sequencing.

**Re-ingest dj2 first** so shape scan + normalize run against the real DB.
