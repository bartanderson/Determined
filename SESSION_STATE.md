Written at commit: eac5371

# SESSION STATE -- session 313 final handoff

## Active branch: main [V]
## Working tree: clean [V]
## Tests: 684 passed, 9 deselected (last verified at 1c7efed) [V]
## call_arg_count: 22654/27190 edges populated (restored) [V]

---

## WHAT HAPPENED THIS SESSION

Investigated session 312's "real signal" (BagStore.add_item arg-count mismatch).
Found it was noise. Fixed the root causes in find_interplay_gaps section 6.
Fixed a separate bug in reingest_file that was silently dropping call_arg_count.

**Commits this session (2):** [V]
- 1c7efed -- fix: populate class_name for Python methods + cleaner section 6 arg-count mismatch detection
- eac5371 -- fix: pass call_arg_count through reingest_file -> GraphBuilder -> graph_edges

---

## WHAT WAS FOUND AND FIXED

**BagStore.add_item investigation (noise):**
bag_store.py is correct. `add_item(self, bag_id, item_type, content, key=None, note=None)`
-- callers pass 4-5 args using optional defaults. Not a bug.

**Section 6 find_interplay_gaps -- three noise sources fixed (1c7efed):**

1. JOIN ambiguity: bare name `add_item` matched both bag_store.add_item AND
   workflow_store.add_item. Root cause: `class_name` column existed in functions table
   but was never populated. Fix: `_iter_top_level_functions` now yields class_name;
   `FunctionRepresentation` carries it; persistence_engine INSERT stores it.
   Section 6 JOIN now uses class_name for class-qualified callees.

2. Stdlib C-stub noise: dict.get / sqlite3.Connection.execute were being matched
   to corpus functions with same bare name. Fix: added `AND f.is_stub = 0` to query.

3. Double-counting: when multiple functions matched same callee, both rows appeared.
   Fix: Python dedup -- keep row with minimum |call_argc - declared| per call site;
   if any match is exact, call is not a mismatch.

Net result: 57 false positives -> 8 findings. Section 6 current output:
  BagStore.add_edge/auto_add_items -> add_item  passed=4 declared=5  (optional params, benign)
  auto_questions -> DBOracle.find_files  passed=0 declared=3  (INVESTIGATE)
  _store -> Assessor.add_artifact  passed=4 declared=5  (likely optional params)
  survey_files -> DBOracle.find_files  passed=0 declared=3  (INVESTIGATE)
  survey_files -> Assessor.semantic_summary  passed=2 declared=3  (INVESTIGATE)
  LanguageWalker._c/cpp_symbols -> _make_symbol  passed=4 declared=7  (_make_symbol has many optional params, benign)

**reingest_file call_arg_count bug (eac5371):**
apply_file_delta called `builder.add_reference()` without `call_arg_count` kwarg.
Every incremental re-ingest since s312 silently wiped call_arg_count for that file's edges.
Fix: one kwarg added. Full-ingest path (EngineRunner) was always correct.

**DB side-effect this session:**
Used force_reingest.py (sets ingested_at='2000-01-01') + reingest_changed to do
bulk Python re-ingest twice. ingested_at timestamps for all 366 Python files are
now "now", not their actual last-changed dates. detect_changed_files() still works
(mtime vs ingested_at); it just means those files won't re-detect as changed until
actually modified. Acceptable; DB otherwise correct.

---

## WHAT TO DO NEXT SESSION

**Section 6 findings -- all investigated and closed (s314):**
  `auto_questions/survey_files -> DBOracle.find_files  passed=0 declared=3` -- benign.
    find_files(pattern=None, role=None, limit=None): all 3 params optional. Callers pass 0. Correct.
  `survey_files -> Assessor.semantic_summary  passed=2 declared=3` -- benign.
    semantic_summary(subject, kind="file", source_text=""): source_text optional. Caller passes (rel, kind="file"). Correct.
  Section 6 signal is clean. No real arg-count bugs remain.

**RM67 maintenance status:** no open regressions. Section 6 findings closed.

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
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes. Use plain hyphens only. [V s299/s311]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps. [V s300]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes not backslashes. [V s303]
- _ep_tier excludes .json/.yaml/.toml (protocol tier). FSM config symbols not inferred EPs. [V s305]
- _caller_names bare-name fallback: Class.method callers resolved via bare name + caller_file. [V s305]
- frontier_priority and _get_chain_positions: Class.method JOIN bug fixed; bare-name + caller_file fallback in all three SQL JOINs. [V s306]
- list_stubs LIMIT applies to non-FSM stubs only. FSM stubs always show in full. [V s306]
- list_features EntryPts = distinct callee symbols; CrossEdges = total edge count. [V s308]
- test coverage check in find_interplay_gaps: checks callee in test_callees (not exact pair). [V s310]
- dispatch test (test_agent_tools.py::test_dispatch_all_tools_registered): update expected set when adding new tools to TOOLS dict. [V s310]
- find_interplay_gaps and list_stubs call reingest_changed() at entry; guard with try/except FileNotFoundError for in-memory/mock DBs in tests. [V s311]
- age != staleness: time since last ingest is not corpus currency; detect_changed_files() (mtime vs ingested_at) is. [V s311]
- tools/query.py JSON args in PowerShell: use doubled inner quotes `"{""key"": ""val""}"` or pass via Python one-liner for complex args. [V s312]
- reingest_file does NOT use EngineRunner -- only handles Python files via parse_ast path. It now propagates call_arg_count correctly (fixed s313), but bulk reset via ingested_at manipulation corrupts timestamp history. [V s313]
- section 6 mismatch JOIN: class_name match required for class-qualified callees. class_name now populated on re-ingest. Old corpus DBs (pre-s313) have class_name=NULL for all functions -- section 6 will see 0 results for class-qualified callees until re-ingest. [V s313]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Tool access: `python tools/query.py <tool>` -- correct entry point, routes through dispatch().
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- Session arc: create session_arc.md in scratchpad at start; append per commit; promote at wrap.
- Self-probe using Determined against itself: use tools/query.py, not probe.py scripts.
- High-blast-radius files (>= 500 edges): any change requires full regression (tools/run_regression.py).
  Current list: agent_tools.py, ui_server.py, language_walker.py, graph_explorer.py, local_agent.py, parse_ast.py.
