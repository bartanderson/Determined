Written at commit: 237886b

# SESSION STATE — session 298 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**Delta loop ran 1 pass against dj2; 2 more gaps found and closed** [V]

**Gap 9 (detect_topology):** FSM stubs were counted in "Disconnected — Decide" (18 total).
12 of those are FSM stubs — real unimplemented game mechanics, not "possibly dead" code.
Fixed: FSM-dispatch row added to shape table; Disconnected drops from 18 to 6.
Action queue now: "FSM mechanics: 12 stubs with string dispatch — real work, not dead code."

**Gap 10 (list_stubs):** Stubs with 1-3 callers showed counts without names, making it
impossible to verify if the caller was real. Fixed: caller names shown inline.
Extended: also annotate caller as (unresolved)/(stub)/bare depending on resolution status.
Key finding: ALL 5 "tail" stubs in dj2 have unresolved callers — phantom edges, not real
call paths. "ContextBuilder.build (unresolved)" etc. These stubs are effectively as isolated
as the 0-caller stubs, despite appearing connected in the raw graph.

459 tests passed. 10 total gaps closed across sessions 296-298.

---

## CURRENT TOOL STATE FOR dj2 (verified at 237886b)

**detect_topology:** Synthesis fires. FSM-dispatch: 12 / Disconnected: 6. Action queues
cover FSM mechanics, ABC classify pointer, orphaned-impl. Complete.

**frontier_coverage:** LOW stub pressure + connectivity synthesis. Complete.

**frontier_priority:** 1 result (test stub, tagged [test]) + "all test files" note. Complete.

**list_stubs:** Regular stubs with caller names+resolution. FSM section. Footer note.
Key output: all "tail" stubs have unresolved callers — developer knows not to chase them.

**list_features:** Built-but-not-integrated (dungeon_neo) + Wired-but-incomplete
(world, config). Complete.

---

## CONVERGENCE ASSESSMENT

After 10 gap fixes, the tool output for dj2 now says — without Claude synthesis:
1. Primary gap is connectivity (941 orphaned impls), not stubs (25)
2. The only production priority stub is a test fixture
3. FSM stubs are real work but not statically resolvable
4. dungeon_neo is complete but unwired; config/world are wired but incomplete
5. All "tail" stubs have phantom callers — lower priority than their label suggests

This matches what Claude would say. Next question: does dj2 now reach RM67 convergence?
Check the probe acceptance criteria in TRACKER.md before declaring it.

---

## WHAT TO DO NEXT SESSION

1. **Check other corpora for false positives.** The new signals (FSM-dispatch, wired-but-
   incomplete, built-but-not-integrated, connectivity synthesis) must not misfire on clean
   corpora. Run detect_topology + list_features against commonplace and rotjs.
2. **RM67 convergence assessment for dj2.** Read TRACKER.md RM67 criteria. Has dj2 met
   all 3 convergence criteria? If yes, update probe table and mark dj2 probed.
3. **find_abc_gaps() on dj2.** 39 ABC-interface gaps shown in detect_topology. Run
   find_abc_gaps() and count real vs. accepted scaffolds. Does the tool output explain
   the breakdown clearly enough?
4. **Consider: delta loop on Determined itself.** Run the 5 tools against the Determined
   corpus — does the tool correctly diagnose its own shape?

---

## PROCESS RULE (standing) [V]

Every session: run Determined on dj2, compare tool output to what Claude would say,
log delta in DELTA_LOG.md, fix the tool. Never synthesize without fixing.
See memory/feedback_core_job.md.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n`. [V s291]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns — handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) — don't treat as low-priority. [V s295]
- RM-Perf profile tier deferred — trigger is "something feels slow in real use." [V s295]
- frontier_priority [test] tag uses _is_test_path() — keep in sync with _is_test_feature(). [V s296]
- list_stubs caller count = ALL edges (resolved + unresolved); frontier_priority = resolved only. [V s297]
- dj2 "tail" stubs ALL have unresolved callers — phantom edges, not real call paths. [V s298]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
