Written at commit: 5fbd981

# SESSION STATE — session 306 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

**Option A from s305 handoff: RM67 dj2 convergence probe update.**
Re-ran list_stubs + frontier_priority on dj2 after s305 _caller_names fix.
Found two more deltas; both fixed. Also fixed list_stubs display-limit bug.

### Delta 1: frontier_priority Class.method caller JOIN bug (commit 3cc2529) [V]

`frontier_priority` SQL query and both queries in `_get_chain_positions`
(`has_functional_caller`, `has_stub_caller`) had `JOIN functions caller_fn ON
caller_fn.name = ge.caller` — same root cause as s305 `_caller_names` fix.
graph_edges stores callers as "ContextBuilder.build"; functions stores bare "build".
No match → production stubs (_get_combat_context, _get_encounter_context,
on_arc_completed, _register_world_tools) were invisible to frontier_priority entirely.
The note "all priority stubs are in test files" was a lie caused by this bug.

Fix: bare-name + caller_file SQL fallback added to all three JOINs.
After fix: all 5 production stubs appear in frontier_priority with score=1.

### Delta 2: list_stubs LIMIT 20 applied before FSM/non-FSM split (commit f0d6683) [V]

SQL `LIMIT 20` was applied to the combined query before Python split FSM vs non-FSM.
On dj2 (12 FSM stubs), FSM stubs consumed 12 of 20 slots, leaving only 8 for Python
stubs. `subraces` and `semantic_match_fighting_style` were silently cut from output.

Fix: removed LIMIT from SQL; applied `regular_rows[:limit]` after split. FSM stubs
always show in full. Limit now constrains non-FSM stubs only.

459 tests pass [V].

### TRACKER dj2 entry updated (commit 5fbd981) [V]

dj2 now: 25 stubs — 12 FSM (accepted), 3 test (accepted), 5 subrace/RM68 delete
candidates (subraces, get_subraces_for_race, get_race_for_subrace,
semantic_match_subrace, semantic_match_fighting_style), 5 production gaps
(_get_combat_context, _get_encounter_context, on_arc_completed, process_consequences,
_register_world_tools). All 3 convergence criteria met.

---

## WHAT TO DO NEXT SESSION

**Step 0 — DB state.** dj2 DB last written 2026-08-05 evening (s305 probe).
No code changes to dj2 since then. No re-ingest needed.

**Option A: Option D from s305 — list_features vs feature_shape EP count discrepancy.**
list_features shows world/ with 164 EntryPts; feature_shape('world') shows 39 Entry
points. Different definitions, same label, no explanation. Not logged yet — worth
logging in DELTA_LOG and deciding if terminology should be unified.

**Option B: New corpus for RM67 probe loop.**
RM75 (corpus expansion) is closed. If a new corpus is wanted, clone into
`C:\Users\bartl\dev\corpora\`, ingest with `tools/ingest_lang_corpus.py`,
run the RM67 probe (list_stubs, frontier_priority, find_abc_gaps, detect_topology).

**Option C: Companion framework (out-of-band).**
Bart is planning a deterministic mixture-of-experts framework as a separate project.
Agreed: start it after a few real dj2 development sessions through Determined; real
failures will define the chapter plan better than speculation. Not a Determined task.

---

## PROCESS RULE (standing) [V]

Every session: run Determined on dj2, compare tool output to what Claude would say,
log delta in DELTA_LOG.md, fix the tool. Never synthesize without fixing.

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
- dj2 "tail" stubs: prior session (298) concluded "phantom edges, lower priority" for
  _get_encounter_context etc. -- that was WRONG. Those callers ARE in the corpus. [V s305]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages. [V s299]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps. [V s300]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes not backslashes. [V s303]
- persist_file_analysis ingested_at fix: Python file rows now get ingested_at on every write.
  Old corpus DBs ingested before d48836f have NULL ingested_at for Python files. [V s304]
- _ep_tier excludes .json/.yaml/.toml (protocol tier). FSM config symbols not inferred EPs. [V s305]
- _caller_names bare-name fallback: Class.method callers resolved via bare name + caller_file.
  Re-run list_stubs on any corpus with prior "(unresolved)" surprises. [V s305]
- frontier_priority and _get_chain_positions: same Class.method JOIN bug now fixed in SQL.
  All three JOINs use bare-name + caller_file fallback. [V s306]
- list_stubs LIMIT applies to non-FSM stubs only. FSM stubs always show in full. [V s306]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- reingest_changed is available as a tool: call it when corpus may be stale.
