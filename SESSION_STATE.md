Written at commit: a719ce7

# SESSION STATE -- session 312 final handoff

## Active branch: main [V]
## Working tree: clean [V]
## Tests: 471 passed, 8 deselected (last verified at aa9aa6b) [V]

---

## WHAT HAPPENED THIS SESSION

Fixed call_arg_count propagation bug, implemented RM71/72/73, added tools/query.py.
Started using Determined via dispatch() to probe itself rather than reading files.

**Commits this session (5):** [V]
- 0f1f997 -- fix: propagate call_arg_count through GraphEdge/GraphBuilder/EngineRunner
- f05d7c7 -- feat: RM71 epistemic_policy as mandatory query gate via dispatch()
- ea5dafb -- feat: RM72 high-blast-radius marking in responsibility_map + analyze_corpus
- aa9aa6b -- feat: RM73 observability scope + tools/query.py CLI dispatcher
- a719ce7 -- docs: HISTORY.md usage pattern notes

**What is live:**

`call_arg_count` now propagates: `GraphEdge` has the field, `GraphBuilder.add_reference()`
accepts it, `run_engine.py` passes `getattr(ref, "call_arg_count", None)` in the loop.
After full re-ingest: 22631/27169 edges populated. NULLs = non-static edges (correct).

`corpus_quick_check(conn)` in `epistemic_policy.py`: cheap SQL check (file count, edge
count). `dispatch()` in `agent_tools.py` calls it after every read-tool result and
prepends `[confidence: LOW -- reason]` when corpus is empty or very small (<10 files).
Write-side tools excluded via `_DISPATCH_NO_CONFIDENCE_CHECK`.

`get_high_blast_radius_files(conn)` in `responsibility_map.py`: queries graph_edges for
files with >= 500 outbound edges. `analyze_corpus` now appends a HIGH BLAST RADIUS FILES
section. Self-corpus flags 6 files: agent_tools.py (4840), ui_server.py (1535),
language_walker.py (1213), graph_explorer.py (702), local_agent.py (635), parse_ast.py (501).

`instruments.py` top block documents monitored vs not-monitored failure modes (RM73 Option B).

`tools/query.py`: CLI wrapper around `dispatch()`. Correct entry point for calling any
Determined tool from a session. See HISTORY.md for usage.

---

## WHAT TO DO NEXT SESSION

**All RM69-73 are now closed.** [V]

**RM73 Option A (follow-on):** grow observability coverage -- add signals for:
- Ingest failure (files skipped due to parse errors -- count already printed to stdout)
- Corpus empty on non-empty source (graph_instrument edge_count=0 with file_count>0)
- Schema staleness (call_arg_count=0 across >90% of edges)
Not filed as a tracker item yet; do Option A when RM67 regression work surfaces a
real monitoring gap.

**Self-probe (run tools/query.py against self-corpus):**
The corpus was re-ingested fresh this session. Run a self-probe to verify section 6
(call_arg_count mismatch detection) now works with populated data:
  python tools/query.py find_interplay_gaps
Check section 6 output -- should now show actual arg-count mismatches if any exist.

**Correct tool usage going forward:**
  python tools/query.py <tool_name>            # default: self-corpus DB
  python tools/query.py --db other.db <tool>   # other corpus
DO NOT write probe.py scripts. DO NOT import tool functions directly (bypasses
confidence check and requires knowing oracle-vs-assessor layer).

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
