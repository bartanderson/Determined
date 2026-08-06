Written at commit: 12de8a9

# SESSION STATE — session 309 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

Single action: declared Determined complete.

- All open TRACKER items (RM21, RM73, RM75, RM76, RM77, RM-Perf) deleted.
- RM67 moved to maintenance mode: fix regressions when they appear, no scheduled development.
- TRACKER reduced from 383 lines to 77. [V]
- Memory updated: `feedback_work_focus.md` reflects complete status and hard rule. [V]
- Committed: 12de8a9 [V]

**Bart's rule (session 309):** No Determined feature work while dj2 development is active.
Determined sessions = probe + regression fix only. Two active dev threads = cognitive overhead
that defeats the purpose of building the tool.

---

## WHAT TO DO NEXT SESSION

**Determined is complete. Next work is dj2 development.**

Start a dj2 session. Use Determined to analyze dj2 (read-only probes). Make game
code changes in dj2. Do not make Determined feature changes.

First things to do in dj2 (from last RM67 probe):
- RM68: remove subrace stubs from dnd_data.py, character_generator.py, authority_system.py
  (5 stubs: subraces, get_subraces_for_race, get_race_for_subrace, semantic_match_subrace,
  semantic_match_fighting_style)
- 5 production stubs to implement: _get_combat_context, _get_encounter_context,
  on_arc_completed, process_consequences, _register_world_tools

Run Determined against dj2 at session start to get current state before touching anything.

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
