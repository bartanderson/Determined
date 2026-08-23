Written at commit: d20cf90

# SESSION STATE — session 310 final handoff

## Active branch: main [V]
## Working tree: clean [V]
## Tests: 338 passed, 4 deselected [V]

---

## WHAT HAPPENED THIS SESSION

CSF (component substitution fallacy) operationalized in Determined. Source: csf.md
committed last session (b8dc661). DetMoE determined the capability was required.

**Commits this session (5):** [V]
- ab1d4e7 -- list_stubs: add co-stub edge count (+N stub edges) as CSF defense
- a68efe4 -- list_stubs: hard WARNING, rule out system interplay before individual fixes
- 424b0b3 -- fix 3 defects: dead stub_name_set, wrong note scope, no investigation method
- 9a93d23 -- list_stubs: show connected stub names; WARNING as plain steps
- d20cf90 -- find_interplay_gaps: Layer 1 CSF defense for implemented modules

**What is live:**

`list_stubs` now shows `+N stub edges [name1, name2]` on any stub connected to other
stubs in the corpus. Hard WARNING follows the list: look at named stubs, ask if
implementing one requires the other's output; if yes, design the interface first.

`find_interplay_gaps` (new tool) surfaces 5 interaction patterns between implemented
modules -- run BEFORE treating any issue as a single-module fix:
1. Unresolved edges between implemented functions (interface drift)
2. Production edges not exercised in tests (invisible contract errors)
3. Interaction hubs -- high fan-in AND fan-out
4. Circular file dependencies
5. Tightly-coupled file pairs

Registered in TOOLS dict and tool_registry. 10 regression tests. FILE_MAP updated.

**Memory updated:** [V]
- `reference_component_substitution_fallacy.md` -- hard rule + investigation method
- `MEMORY.md` index -- description updated to surface at the right moment

---

## WHAT TO DO NEXT SESSION

**Layer 2: call-site argument capture** -- the remaining CSF gap.

Goal: add `call_arg_count` to `graph_edges` so `find_interplay_gaps` can flag
argument count mismatches between caller and callee on resolved edges.

Files to touch (in order):
1. `determined/shared/types.py` -- add `call_arg_count: Optional[int] = None` to `SymbolReference`
2. `determined/persistence/persistence_engine.py` -- add column to CREATE TABLE,
   add migration in `_migrate()`, add to INSERT in both Python and JS/TS paths
3. `determined/ingestion/parse_ast.py` -- at each `ast.Call` node, count
   `len(node.args) + len(node.keywords)`; set -1 if `*args` or `**kwargs` present;
   populate `SymbolReference.call_arg_count`
4. `determined/ingestion/language_walker.py` -- same at call sites in each language handler;
   `walker.call_edges()` returns `(caller, callee, etype, resolved)` -- needs to carry count too
5. `determined/agent/agent_tools.py` -- add section 6 to `find_interplay_gaps`:
   for resolved edges where `call_arg_count >= 0`, compare against callee's required
   parameter count from `functions.arguments_json`; flag mismatches

Key design decisions already made:
- -1 = uncountable (*args/**kwargs), skip the check for those
- Default parameters mean required count = non-default subset of arguments_json
- NULL = old row (pre-migration), handle gracefully (skip check)
- Compare call_arg_count against required params only, not total params

After Layer 2, dj2 work begins (RM68 subrace removal, 5 production stubs).

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed -- don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n`. [V s291]
- pytest `-m` on CLI REPLACES addopts -- never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns -- handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) -- don't treat as low-priority. [V s295]
- frontier_priority [test] tag uses _is_test_path() -- keep in sync with _is_test_feature(). [V s296]
- list_stubs caller count = ALL edges (resolved + unresolved); frontier_priority = resolved only. [V s297]
- dj2 "tail" stubs: prior session (298) concluded "phantom edges, lower priority" -- WRONG. [V s305]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages. [V s299]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps. [V s300]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes not backslashes. [V s303]
- persist_file_analysis ingested_at fix: old DBs pre-d48836f have NULL ingested_at for Python files. [V s304]
- _ep_tier excludes .json/.yaml/.toml (protocol tier). FSM config symbols not inferred EPs. [V s305]
- _caller_names bare-name fallback: Class.method callers resolved via bare name + caller_file. [V s305]
- frontier_priority and _get_chain_positions: Class.method JOIN bug fixed; bare-name + caller_file
  fallback in all three SQL JOINs. [V s306]
- list_stubs LIMIT applies to non-FSM stubs only. FSM stubs always show in full. [V s306]
- list_features EntryPts = distinct callee symbols; CrossEdges = total edge count. [V s308]
- test coverage check in find_interplay_gaps: checks callee in test_callees (not exact pair).
  Tests that call B by any name count as coverage for any prod edge A->B. [V s310]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- reingest_changed is available as a tool: call it when corpus may be stale.
- Session arc: create session_arc.md in scratchpad at start; append per commit; promote at wrap.
- dispatch test (test_agent_tools.py::test_dispatch_all_tools_registered): update expected
  set when adding new tools to TOOLS dict. [V s310]
