Written at commit: 892ce84

# SESSION STATE — session 203
_Overwrite completely each session. Not authoritative — see docs/TRACKER.md and docs/CLOSURE.md for truth._

## Active branch: main [V]

## What happened this session (2026-07-17)

**Phase 2: dj2 convergence probe — complete [V]**
All 6 canonical questions answered against C_Users_bartl_dev_dj2.db.

- Q1 PASS: 93 HTTP routes. Flask structure correctly identified (dungeon_app.py,
  world_app.py, routes/api.py). EP detection works. [V]
- Q2 PASS: main HOT — 140 direct callers, 681 extended impact. [V]
  Note: blast_radius arg is `target` not `symbol`.
- Q3 PASS with note: list_features correct (world/: 564 syms, 10 stubs).
  feature_shape BFS (world/): 43 reachable syms, 0 stubs shown — by-design
  limitation. BFS only traverses reachable-from-external-EP nodes; stubs with
  only internal callers invisible to stub count. Use list_stubs for authoritative
  stub count. [V]
- Q4 PASS: 10 stubs found, 0 false positives. test_encounter_fsm.py stub
  (check_parley) correctly excluded by `%/test_%` filter. [V]
- Q5 PASS: ai_command surfaces 5 design-note hits (scores 0.37-0.46 from
  requirements doc). Requires `symbol` arg. [V]
- Q6 PASS: graph_path finds real paths (main->interactive_mode 1-hop,
  main->print_result 2-hop). walk_call_chain: 48-node chain from __init__. [V]
  Note: graph_path uses `src`/`dst` args not `start`/`end`.

**Arg name reference (confirmed against code) [V]:**
  blast_radius: `target` (not `symbol`)
  graph_path: `src`, `dst` (not `start`, `end`)
  check_design_violations: `symbol`
  list_entry_points: `feature_path`, `tier`, `top_n`
  feature_shape: `feature_path`, `prefix`
  list_stubs: `limit`

## NEXT SESSION -- start here

**Phase 2: Commonplace convergence probe [next]**
  DB: C_Users_bartl_dev_Determined_examples_commonplace.db (237KB, not the 0-byte one)
  Known state: 1 stub (suggest_tags), should classify as design-intent-stated.
  6 canonical questions. Use probe pattern from dj2 session.
  Arg names above -- don't re-derive.

**After Commonplace: remaining Phase 2 corpora**
  rotjs (scope to src/) -> dungeoncrawler -> dnd-dungeon-gen (re-ingest first) ->
  end-of-eden -> ruggrogue

## Known issues (carried forward)

**feature_shape stub count [V]:** BFS from external EPs may miss stubs with
  only internal callers. Authoritative count: list_stubs. Not a bug -- by-design.
**arg name asymmetry [V]:** blast_radius uses `target`; graph_path uses `src`/`dst`.
  Other tools use `symbol`. Document before calling, don't guess.
**Dead graph edges in Determined DB [V]:** run_query -> query_router / query_session
  (module deleted). Ghost callee noise. Ingestion artifact.
**dj2 ignore dirs [V]:** .determinedignore covers all exclusions.
**function_reference residual noise [V]:** ~10 false edges depth-1 local vars.
**classify_stub file_path trap [V]:** Must pass FULL ABSOLUTE PATH as stored in DB.
  Relative paths silently fail.
**Commonplace DB [?]:** C_Users_bartl_dev_Commonplace.db is 0 bytes. Use
  C_Users_bartl_dev_Determined_examples_commonplace.db (237KB) or re-ingest.
**SetFit model [V]:** C:\Users\bartl\models\setfit\stub_classifier\. Inference only.
**graph_path method call hops [V]:** FIXED -- BFS restricted to functions table.
**list_stubs test fixtures [V]:** FIXED -- test_ prefix excluded from SQL.
**Suite: 1144 pass, 1 skip [?]:** Not re-run this session (no code changes).
