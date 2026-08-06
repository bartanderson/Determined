Written at commit: 0481245

# SESSION STATE — session 308 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

Single focused task: Option A from s307 — `list_features` vs `feature_shape` EP count
discrepancy.

### Bug found and fixed: list_features EP definition (8176fc1) [V]

**Symptom:** `list_features` showed world/ with 164 EntryPts; `feature_shape('world')`
showed 39. Same label "Entry points," no explanation.

**Root cause:**
- `list_features` counted cross-feature call *edges* (feat_entry_points += 1 per edge).
  Same symbol called N times from outside counted as N EPs.
- `feat_entry_points` and `feat_cross_edges` were incremented in the same statement --
  both columns were always identical (redundant).
- `feature_shape` uses a set: distinct callee symbols with at least one external caller.

**Fix in `determined/agent/agent_tools.py`:**
- `feat_entry_points` changed to `defaultdict(set)`, `.add(callee)` instead of `+= 1`.
- `feat_cross_edges` stays as int edge counter -- columns now meaningfully differ.
- Compiled-output warning switched to use `feat_cross_edges` (edge volume is the right
  signal for "compiled output mirroring"; symbol count would be too low to trigger).
- 459 tests pass. [V]

**dj2 full list_features after fix (key numbers):** [V]
```
world_app.py   107 syms  0 stubs   86 EP  160 CrossEdges
world          564 syms 10 stubs   39 EP  164 CrossEdges
dungeon_neo    141 syms  0 stubs    6 EP    6 CrossEdges
config          45 syms 12 stubs    0 EP    0 CrossEdges
```
world/ CrossEdges >> EntryPts (164 vs 39): high call concentration on ~39 symbols.
meta_agent.py 4 EP / 22 edges: tiny surface, heavily called.
config: 0 external callers -- its 12 stubs don't block anything wired in yet.

Logged in `docs/DELTA_LOG.md`. TRACKER updated (0481245). [V]

---

## WHAT TO DO NEXT SESSION

**Option B: New corpus for RM67 probe loop.**
Clone a new corpus into `C:\Users\bartl\dev\corpora\`, ingest with
`tools/ingest_lang_corpus.py`, run the RM67 probe (6 canonical questions).
Candidates: anything not yet at "Full convergence" in TRACKER RM67 table, or a
brand-new corpus to extend language coverage.

**Option C: dj2 development session.**
Run Determined on a real dj2 gap -- pick one of the 5 production stubs
(_get_combat_context, _get_encounter_context, on_arc_completed,
process_consequences, _register_world_tools), use feature_shape + frontier_priority
to scope it, then fix it in dj2. This is the "real failures define what experts need"
loop that precedes the companion MoE framework.

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
- list_features EntryPts = distinct callee symbols; CrossEdges = total edge count.
  These were identical before s308 (both counted edges). Now meaningfully separate. [V s308]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- reingest_changed is available as a tool: call it when corpus may be stale.
- Session arc: create session_arc.md in scratchpad at start; append per commit; promote at wrap.
