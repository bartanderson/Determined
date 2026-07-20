Written at commit: 7ecf5b4

# SESSION STATE — session 224
Written at commit: 7ecf5b4 (2026-07-20)

## Active branch: main [V]

## What happened this session

**Lesson locked: stale handoff → mention and move on [V]**

SESSION_STATE said "RM69 step 5 — corpus aggregation" was next. Pre-code
checklist found all three projections already implemented and passing (42/42).
Right response: note it in one sentence, update docs, proceed. No re-testing
needed to confirm what exists in code.

**RM69 corpus aggregation — confirmed DONE [V]**

stub_file_shape, stub_subsystem_shape, stub_prerequisite_map all exist in
corpus_projections.py, all wired into agent_tools.py TOOLS registry, all 42
regression tests passing. Smoke test against live dj2 DB produces correct output.
No work needed.

**RM71 Phase 1 — shape scanner shipped [V]**

Wrong first attempt: started writing fsm_ingestor.py (format-specific, wrong
abstraction). Bart corrected: the right tool is format-agnostic shape induction.
Deleted fsm_ingestor.py.

Built determined/ingestion/shape_scanner.py:
- Format-agnostic: JSON/YAML/TOML (structured) + .md/.txt/.rst (prose)
- Four detection passes: node_collection, reference, topology, hierarchy
- Convergence gating → ShapeFinding with kind + confidence + missing refs
- Runs automatically at end of ingest (hooked into ui_server.py handle_ingest)
- Agent tool list_shape_findings() queries stored findings
- 13/13 regression tests passing [V]

Smoke test against live dj2:
- 39 findings total — 9 directed_graph, 7 tabular, 18 tree, 2 manifest, 3 flat
- All 5 FSMs (barter, buy, encounter, sell, trade) at 100% confidence [V]
- encounter.json: directed_graph 100%, 4 nodes, 5 edges [V]
- Known false positives: .recall/history.md and SESSION_STATE.md picked up
  as directed_graph (65%/95%) from -> arrows in prose. Acceptable noise.

**Design decision: shape scanner philosophy [V]**

Not a per-format parser. Multi-method induction (mirrors structure_induction.py
for prose, same Dempster-Shafer convergence philosophy). Scope: all non-code
files — JSON, YAML, markdown, text, comments. Reports findings; normalizer
(phase 2) writes graph_edges from high-confidence hits. Scanner is investigative,
not prescriptive.

## Known issues [V = verified, ? = recalled]

**`_get_combat_context` UNCERTAIN [?]:** trivial_return body + CombatFSM present
but no behavioral intent. Gate: RM71 phase 2 (normalizer writing encounter.json
edges to graph_edges so classify_stub can see start_combat is gated).

**Prose false positives in shape scanner [V]:** .recall/history.md (95%) and
SESSION_STATE.md (65%) detected as directed_graph from -> arrows in prose.
Filter by file type or add a prose_arrow_only exclusion if this causes noise.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**RM71 Phase 2 — normalizer.** Shape scanner finds structure; normalizer writes
it to graph_edges. This unlocks `_get_combat_context` resolution.

For high-confidence directed_graph findings, extract the transitions already
detected by the topology pass and write to graph_edges (edge_type='fsm_transition'
or 'config_edge'). States/actions/guards → knowledge_artifacts.

The normalizer takes ShapeFinding output — not the raw file — so it's driven
by scanner confidence, not format assumptions. Start with a query over
kind='shape_finding' where confidence >= 0.7 and kind='directed_graph'.

Files to touch:
- determined/ingestion/shape_normalizer.py (new)
- determined/agent/agent_tools.py (wire normalize_shape_findings tool)
- tests/regression/test_shape_normalizer.py (new)

PRE-CODE CHECKLIST: grep agent_tools.py and graph_edges for any existing
normalization of config edges before writing.

Also worth: add a scope filter to scan_corpus so it can be re-run on a
subdirectory without scanning the whole corpus again.
