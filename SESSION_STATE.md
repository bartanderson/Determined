Written at commit: 23dda34

# SESSION STATE -- session 311 final handoff

## Active branch: main [V]
## Working tree: clean [V]
## Tests: 92 passed (key files), 4 deselected [V]

---

## WHAT HAPPENED THIS SESSION

Incorporated Cook complex-systems failure notes (cook_design_notes.md, 9327759).
Verified and fixed CSF-3, filed RM69-73 for the rest, then worked through them.

**Commits this session (7):** [V]
- 106c12e -- fix: reingest_changed walks transitive dependents (Cook CSF-3)
- 51c9947 -- docs: add RM69-73 for Cook complex-systems failure constraints
- 4b196cc -- fix: propagate transitive reingest in ui_server and local_agent
- a22c798 -- feat: corpus staleness note (superseded next commit)
- 9e408d9 -- fix: replace staleness note with auto-reingest in list_stubs/find_interplay_gaps
- 23dda34 -- chore: delete three dead engine modules; close RM70

**What is live:**

`reingest_changed` now walks the imports table (BFS) to find all files that
transitively import from any changed file and re-ingests them too.
`find_transitive_dependents(db_path, seed_files)` is the public function.

`ui_server.py` auto-reingest-on-save now calls `reingest_changed` instead of
`reingest_file` -- transitive dependents are refreshed automatically.

`local_agent.py --reingest-file` calls `reingest_file` then `find_transitive_dependents`
and reingest each dependent in order.

`list_stubs` and `find_interplay_gaps` call `reingest_changed` at entry -- corpus
is always current before results come back. No staleness warning needed.

Three dead engine prototypes deleted (455 lines):
- engine_snapshot_diff.py (superseded by Assessor.run_integrity_check)
- structural_parity_diff.py (same; DB-only arch never produces file_analyses)
- pipeline_dependency_tracer.py (superseded by find_interplay_gaps sections 4/5)

RM69 closed. RM70 closed (superseded by CSF-3 work).
RM71, RM72, RM73 still open.

**Self-probe run against Determined corpus:** [V]
- 1 stub: suggest_tags (known accepted)
- Section 1/2 noise: stdlib calls (re.sub, json.loads) appearing as unresolved
  edges -- resolution ceiling, not real gaps
- Section 6: call_arg_count not populated -- corpus predates Layer 2 (b6bf393);
  full re-ingest needed

---

## WHAT TO DO NEXT SESSION

**Three self-probe bugs to fix (in order):**

1. **BagStore duplicate edges in find_interplay_gaps section 2:**
   `BagStore.__init__ -> BagStore._init_schema` emitted once per call site instead
   of once per (caller, callee) pair. Fix: dedupe on (caller, callee) before emitting
   in section 2 of `find_interplay_gaps` in `determined/agent/agent_tools.py`.

2. **Section 4 circular deps inflated by test fixtures:**
   528 pairs; test files sharing _make_db/_make_oracle/_seed_db produce false circular
   deps. Section 4 should filter test<->test pairs or show them separately.
   Fix: in `find_interplay_gaps`, check `_is_test_path()` on both files in each pair
   and emit them as a separate "test fixture sharing" bucket or suppress entirely.

3. **Full re-ingest of Determined corpus to populate call_arg_count:**
   Layer 2 (b6bf393) added call_arg_count to graph_edges but the self-corpus DB
   predates it. Run full re-ingest via the UI or reingest_changed after touching
   a file to trigger it. Then re-run self-probe to see section 6 results.

**Then continue Cook items:**
- RM71: epistemic_policy.py as mandatory query gate -- audit assessor.py and
  db_oracle.py call paths, add confidence note to low-confidence results.
- RM72: mark agent_tools.py high-blast-radius in responsibility_map.py.
- RM73: observability scope -- Option B first (document which failure modes are
  NOT monitored), Option A (grow coverage) as follow-on.

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
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages -- but Bash tool blocked on Windows; use
  PowerShell @'...'@ with plain hyphens only. [V s299/s311]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps. [V s300]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes not backslashes. [V s303]
- _ep_tier excludes .json/.yaml/.toml (protocol tier). FSM config symbols not inferred EPs. [V s305]
- _caller_names bare-name fallback: Class.method callers resolved via bare name + caller_file. [V s305]
- frontier_priority and _get_chain_positions: Class.method JOIN bug fixed; bare-name + caller_file
  fallback in all three SQL JOINs. [V s306]
- list_stubs LIMIT applies to non-FSM stubs only. FSM stubs always show in full. [V s306]
- list_features EntryPts = distinct callee symbols; CrossEdges = total edge count. [V s308]
- test coverage check in find_interplay_gaps: checks callee in test_callees (not exact pair). [V s310]
- dispatch test (test_agent_tools.py::test_dispatch_all_tools_registered): update expected
  set when adding new tools to TOOLS dict. [V s310]
- find_interplay_gaps and list_stubs call reingest_changed() at entry; guard with
  try/except FileNotFoundError for in-memory/mock DBs in tests. [V s311]
- age != staleness: time since last ingest is not a measure of corpus currency;
  detect_changed_files() (mtime vs ingested_at) is. [V s311]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- reingest_changed is available as a tool: call it when corpus may be stale.
- Session arc: create session_arc.md in scratchpad at start; append per commit; promote at wrap.
- dispatch test (test_agent_tools.py::test_dispatch_all_tools_registered): update expected
  set when adding new tools to TOOLS dict. [V s310]
- Self-probe (run Determined against itself) is the right tool for finding dead code and
  real gaps -- do it before filing tracker items, not after. [V s311]
