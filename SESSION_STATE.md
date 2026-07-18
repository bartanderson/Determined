Written at commit: c05dcfb

# SESSION STATE — session 202
_Overwrite completely each session. Not authoritative — see docs/TRACKER.md and docs/CLOSURE.md for truth._

## Active branch: main [V]

## What happened this session (2026-07-17)

**Phase 1 of CLOSURE.md: complete [V]**
All corpus-level projection tools built, tested, wired, and validated against dj2.

**Phase 1a — Magic method handling [V] (continued from session 201)**
  classify_stub gains _is_lifecycle_method, _extract_class_context, file_path_hint.
  41 tests in test_classify_stub.py, all pass.

**Phase 1b/1c — corpus_projections.py [V]**
  Four new agent tools: stub_file_shape, stub_subsystem_shape,
  stub_prerequisite_map, stub_concept_ghost_map.
  Wired into TOOLS dict and tool_registry.py.
  35 new regression tests in test_corpus_projections.py.

**dj2 validation found two bugs, fixed same session [V]**

  Bug A — ghost map matching too loose:
    CombatFSM -> base "Combat" -> substring-matched "_validate_combat" -> PARTIAL.
    Fix: match full concept name in snake_case ("combatfsm") not stripped base.
    CombatFSM now correctly GHOST; EncounterFSM correctly live.

  Bug B — SetFit missed explicit-absence phrasing:
    "OG System doesn't have subraces" -> has_removal=False -> wrong hypothesis.
    Fix: _EXPLICIT_ABSENCE_RE fast-path in stub_classifier.py before SetFit.
    dnd_data.py stubs now all concept-not-applicable (dead-concept dominant). [V]

**dj2 validation findings (accurate, not bugs) [V]**
  world/ subsystem shows dead-concept (not design-skeleton) because 5 subrace
  stubs outnumber 5 AI-layer stubs. Will flip to design-skeleton after RM68.
  Prerequisite map: AI-layer stubs have bare docstrings, no "blocked on X" language.
  Tool correct; corpus content did not match the expected pass criterion.

**Phase 2: Determined convergence probe [V]**
  Q1 PASS: 160 EPs (internal utilities dominate, expected).
  Q2 PASS: dispatch HOT — 124 callers, 1069 extended impact.
  Q3 PASS: list_features works; 39% completeness in agent/ (cross-module missing expected).
  Q4 BUG FOUND AND FIXED: 9/12 stubs were test fixtures. Real stubs: 3.
  Q5 NOT TESTABLE: no layer rules / design notes ingested. Dead edges to
    query_router found in graph; module deleted but edges remain.
  Q6 BUG FOUND AND FIXED: graph_path traversed .append() list method as path hop.
    ask->dispatch path was entirely false. No real path exists (parallel entry points).

**Two Phase 2 bugs fixed [V]**

  Bug C — list_stubs showed test fixtures:
    Added AND file_path NOT LIKE '%/tests/%' to SQL. Output: 12->3 stubs.

  Bug D — shortest_path false hops through method calls:
    results.append(dispatch(...)) ingested as append->dispatch (receiver stripped).
    Fix: BFS only visits nodes in functions table. Method names excluded.
    test_graph_utils fixture updated to auto-populate functions from edges.

**Suite: 1144 pass, 1 skip [V] (last confirmed run: commit c05dcfb)**

## NEXT SESSION — start here

**Phase 2: dj2 convergence probe [next]**
  Run all 6 canonical questions against C_Users_bartl_dev_dj2.db.
  Known state: 10 stubs (5 subrace dead-concept, 5 AI-layer design-intent/unknown).
  Use probe_determined2.py as template — adapt args for dj2.
  Watch for: JS callee resolution gaps (RM62 fix); dj2 ignore dirs in .determinedignore.

**After dj2: remaining Phase 2 corpora**
  Commonplace -> rotjs -> dungeoncrawler -> dnd-dungeon-gen -> end-of-eden -> ruggrogue

**classify_stub file_path trap [V]**
  Must pass FULL ABSOLUTE PATH as stored in DB (e.g. C:/Users/bartl/dev/dj2/world/...).
  Relative paths silently fail — query returns nothing, error is "stub not found".
  Determined __init__ #2 is in determined/contracts/ not determined/assessor/ (old
  SESSION_STATE was wrong).

**Dead graph edges in Determined DB [V]**
  run_query -> determined.assessor.query_router.route_query exists as a graph edge
  but query_router module is deleted. Same for query_session. Ingestion artifact
  from deleted code. Will surface as noise in Q5/Q6 probes.

## Known issues (carried forward)

**agent_tools call pattern [V]:** Tools take (assessor, args_dict).
  Entry: determined/ask.py ask(db_path, question).
**DB schema [V]:** graph_edges: caller/callee not callee_fqdn; files uses file_path.
**dj2 ignore dirs [V]:** .determinedignore covers all exclusions.
**function_reference residual noise [V]:** ~10 false edges depth-1 local vars.
**EP inferred count floor [V]:** 331 dj2 / 160 Determined — dynamic dispatch not bugs.
**resolved col != unknown callee [V]:** resolved=0 means not annotation-resolved, not unknown.
**probe_pass2.py duplicate rows [?]:** LEFT JOIN artifact; unverified this session.
**classify_stub body_shape [?]:** _extract_body() not validated against all dj2 files.
**Corpus DB location [V]:** DBs in C:\Users\bartl\dev\Determined\*.db.
**SetFit model [V]:** C:\Users\bartl\models\setfit\stub_classifier\. Inference only.
**graph_path method call hops [V]:** FIXED — BFS now restricted to functions table.
  Consequence: ask->dispatch has no path (correct — parallel entry points).
**list_stubs test fixtures [V]:** FIXED — test/ files excluded from SQL query.
**Q5 not testable without design docs [V]:** check_design_violations needs layer rules;
  evaluate_claim needs design notes. Ingest docs first before running Q5.
