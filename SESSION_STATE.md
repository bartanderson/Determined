Written at commit: 85d9bcb

# SESSION STATE -- dj2-state-machines-openspec wrap

## Active branch: dj2-state-machines-openspec [V]
## Working tree: clean, one untracked user file (memory/reference_autosaddler.md) [V]
## Tests: G1 + G2 pass (423 total); G3 fails on one pre-existing test (see below) [V]
## dj2 baseline: 598ed551d0538c1129c75aec0f708b20205c80af (matches proposal) [V]

---

## WHAT HAPPENED THIS SESSION

Completed the dj2-state-machine-handoff OpenSpec change end to end. This is
a self-contained change on branch dj2-state-machines-openspec, distinct from
Determined's main line of work.

Determined-side tooling (section 2 of the tasks): [V]
- 2.1 check_fsm_consistency tool + 6 tests
- 2.2 check_event_coverage tool + 8 tests
- 2.3 tools/handoff.py (make/verify/check) + 8 tests
- 2.4 handoffs/dj2/README.md and STATE.md

Bundle work (section 3): [V]
- 001 events foundation: config/events/initial_events.json, 7 event types
- 002 encounter FSM: fight_possible guard, four actions emit events,
  tests/unit/test_encounter_fsm.py (8 tests)
- 003 barter FSM: session_id in barter context, add_gold and execute_barter
  emit, tests/unit/test_barter_fsm.py (8 tests)
- 004 trade FSM: registry keys fixed to match trade.json, execute_purchase
  renamed execute_buy and emits, tests/unit/test_trade_fsm.py (8 tests)
- 005 context-builder: _get_encounter_context and _get_combat_context
  implemented as EventLog readers, tests/unit/test_context_builder_encounter.py
  (8 tests)

Close tasks (section 4): [V]
- 4.1a freshness check: dj2 origin/main is still at 598ed55, no drift
- 4.1a prefix test table: bundles 1..k applied to a fresh clone; the five
  headless dj2 test files pass at every k (16 passed at k=0 through k=5)
- 4.1 FSM consistency on the patched clone: BarterFSM, EncounterFSM,
  TradeFSM resolve cleanly
- 4.2 openspec validate dj2-state-machine-handoff --strict: valid

Also discovered and fixed during the session:
- generic_fsm.py send_event used **event_data; python-statemachine 3.x
  forwards only positional args to guard/action callbacks, so every
  callback received None. Fixed to pass positionally.
- check_fsm_consistency crashed on list-form "from" fields (barter.json
  and trade.json use them). Fixed with tests.

**Commits this session (10):** [V]
- e5cc4db -- openspec: task 2.4 - handoff README and STATE docs
- 25d4132 -- openspec: task 2.3 - handoff bundle tool (make/verify/check)
- 533b5ef -- openspec: task 2.2 - event coverage report; registry entries
- e654646 -- openspec: task 2.1 - FSM consistency check + 4 tests
- 3200684 -- openspec: task 3.1 - bundle 001 events foundation
- c1e671c -- openspec: task 3.2 - bundle 002 encounter FSM
- 73bdaf1 -- handoff: three-way apply fallback for cumulative bundles
- d6d28f3 -- openspec: task 3.3 - bundle 003 barter FSM
- 97f1957 -- openspec: task 3.4 - bundle 004 trade FSM
- 9f1c255 -- openspec: task 3.5 - bundle 005 context builder
- 85d9bcb -- openspec: check_fsm_consistency handles list 'from'

---

## BUNDLES VERIFIED, NOT YET APPLIED TO dj2

All five bundles under handoffs/dj2/ are ready: MANIFEST.json,
change.patch, rationale.md, verify.md present, all four files checked.
The patches apply cleanly to a fresh clone at 598ed55 and to a cumulative
clone (each on top of its predecessors). Not yet applied to the user's
working dj2 clone.

To apply: see handoffs/dj2/README.md. Use git apply --3way for bundles
002+ (they were generated against base_sha but the tree already has
earlier bundles).

After applying, the user commits to a dj2 feature branch and pushes; the
next Determined session records the new dj2 SHA in handoffs/dj2/STATE.md.

---

## dj2 TESTS NOT RUN AND WHY

- Anything requiring Postgres (psycopg2, pgvector): 30 files classified
  in BASELINE.md from the Linux baseline. Postgres is available on this
  Windows session but was not exercised; the change is FSM-only and no
  Postgres-dependent code path was touched.
- tests/test_trade_fsm.py imports world.fsm.trade_machine, a module that
  does not exist at base_sha. Left broken (out of scope); flagged in
  bundle 004's rationale.

---

## PRE-EXISTING FAILURES (not caused by this session)

tools/run_regression.py G3 has one failure:
  tests/regression/test_design_oracle.py::test_design_oracle_opportunity_context
  sqlite3.OperationalError: no such column: class_name

The test fixture does not create a class_name column, but design_oracle
queries it. The test file was last touched in commit 471ee71 (adding
design_oracle); class_name was added to the schema later (Determined
session 313). The test predates that addition. Not related to this
branch's work; fix is deferred.

---

## FINDINGS DEFERRED TO A LATER CHANGE

Surfaced during task 4.1's check_fsm_consistency run on the patched clone.
Not in scope for this change (wave-1 machines only):

  buy.json [BuyFSM] and sell.json [SellFSM] declare guards: {} and
  actions: {}, yet their transitions reference price_too_low,
  store_offer, execute_purchase, execute_sell. Ten unresolved references
  total. These two FSMs cannot fire their offer/confirm events as written.

  Per the proposal's non-goals ("no wave-1 stubs outside the three FSMs
  and the two context-builder stubs"), a follow-up change handles them.

  Wave-1 machines (BarterFSM, EncounterFSM, TradeFSM) resolve cleanly.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need position:relative;overflow:hidden. [V s290]
- llm_client.chat() reasoning_content fallback removed -- don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains \n. [V s291]
- pytest -m on CLI REPLACES addopts -- never pass -m by hand. [V]
- Old corpus DBs may lack http_route/is_tool/is_stub columns -- handle
  gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) -- don't treat as
  low-priority. [V s295]
- New tools registered in TOOLS dict: add AFTER function def, not inside
  the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes
  and smart quotes. Use plain hyphens only. [V s299/s311]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub
  list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes
  not backslashes. [V s303]
- dispatch test (test_agent_tools.py::test_dispatch_all_tools_registered):
  update expected set when adding new tools to TOOLS dict. [V s310]
- reingest_file does NOT use EngineRunner -- only handles Python files via
  parse_ast path. call_arg_count propagation fixed s313. [V s313]
- section 6 mismatch JOIN: class_name match required for class-qualified
  callees. Old corpus DBs (pre-s313) have class_name=NULL. [V s313]
- [NEW s314] python-statemachine 3.x: send_event callbacks receive only
  positional args, not kwargs. Pass event_data as a single positional
  argument. [V]
- [NEW s314] handoff.py writes patches with newline="\n" explicitly;
  Windows Path.write_text defaults to CRLF and breaks git apply. [V]
- [NEW s314] handoff.py verify: direct apply first, then git apply --3way
  fallback for cumulative bundles. Clone HEAD check allows base_sha as an
  ancestor rather than requiring equality. [V]
- [NEW s314] check_fsm_consistency handles 'from' as a string OR a list of
  state names. [V]

## RESOURCE / PROCESS RULES [V]

- Test runner: tools/run_tests.py only. Never pytest directly, never full
  suite.
- Tool access: python tools/query.py <tool> -- correct entry point, routes
  through dispatch().
- High-blast-radius files (>= 500 edges): any change requires full
  regression (tools/run_regression.py). Current list: agent_tools.py,
  ui_server.py, language_walker.py, graph_explorer.py, local_agent.py,
  parse_ast.py. agent_tools.py and tool_registry.py both changed this
  session; regression was run (G1 + G2 pass; G3 has the pre-existing
  design_oracle failure above).

---

## WHAT TO DO NEXT SESSION

Two independent lines of work now:

1. If the user has applied the bundles to dj2 and pushed, record the new
   SHA in handoffs/dj2/STATE.md (task 4.4's reverse-sync step), re-ingest
   at that SHA, and confirm no drift.

2. If the user wants to revisit buy.json / sell.json, open a new change
   (not this one) that fixes the ten unresolved references. Same shape as
   bundle 004's trade fix: either add the missing guards/actions to the
   JSON, or rename builtins to match the JSON per design D2.

3. The pre-existing test_design_oracle failure is orthogonal and can be
   fixed any time: add class_name to the test fixture schema in
   tests/regression/test_design_oracle.py.

---

## FIRST COMMAND NEXT SESSION

git log --oneline -3