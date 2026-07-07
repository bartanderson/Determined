Written at commit: 7cce582
# SESSION STATE - session 102 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 102, 2026-07-06)

**RM15 Step 2 completed [V]:**
- Committed `examples/commonplace/seed/services/extractor.py` (94ce9df)
- `extract_metadata`: real implementation using `urllib.request.urlopen` + `html.parser.HTMLParser`
- `_TitleParser` inner class nested inside function body (skipped by `_iter_top_level_functions`)
- Frontier Direct: dropped from 2 stubs → 1 stub (`extract_full_content` only) [V via UI]
- Roots still only `capture` and `index` -- no inner class leakage [V via UI]

**Bug found and fixed: `reingest_file` graph_edges wipe [V]:**
- Root cause: when reingesting a stub file (zero outgoing calls), `symbol_references` is empty
  -> GraphBuilder produces no edges -> `files_in_run` = empty set -> `_persist_graph_edges`
  falls through to `DELETE FROM graph_edges` (full reset, not scoped)
- Fix in `determined/ingestion/reingest_file.py`: explicit `DELETE FROM graph_edges WHERE
  caller_file = ?` before building graph, then INSERT edges directly (bypasses
  `_persist_graph_edges` entirely for the reingest path)
- 440 passed, 1 skipped after fix [V]

**RM15 Step 3 completed [V]:**
- `examples/commonplace/seed/storage/queries.py` created -- `insert_entry` stub [V]
- `examples/commonplace/seed/routes/capture.py` wired: `from storage import queries` +
  `queries.insert_entry(entry)` call [V]
- DB state: `insert_entry` in Direct frontier (caller: capture), not Orphan [V via SQL]
- Stubs: `extract_full_content` + `insert_entry` = 2 total [V]

**HISTORY.md updated [V]** -- reingest_file bug + UI Re-analyze behavior documented.

## Known issues (carried forward)

**UI Re-analyze+ does NOT use reingest_file [V]:** Runs background discover_run thread.
Can conflict with open sqlite3 connections; graph_edges may be empty after UI reingest.
Workaround: call `reingest_file()` from Python CLI directly.

**Frontier Load button navigates to Chat [?]:** Clicking "Load + Enter" in Frontier tab
switches active tab back to Chat. Workaround: unknown.

**DB lock on Re-analyze [?]:** discover_run holds a second sqlite3 connection.
Workaround: kill server, delete seed.db, restart.

**Test count: 440 passed, 1 skipped [V]**

## NEXT SESSION -- start here

1. **RM15 Step 4:** Run `check_design_violations` on `extractor.py`
   - Should surface the 3-responsibility tension (fetch + parse + extract in one module)
   - Per COMMONPLACE_VISION.md Step 4 spec
   - Tool call via UI Chat or Python: `check_design_violations(assessor, {"symbol": "extract_metadata", "file": "...extractor.py"})`
   - LLM must be running (Qwen3-8B on port 8081, started automatically by UI)

2. Seed DB is up to date -- no reingest needed before step 4.

3. Update `.claude/step_queue.md` CURRENT to step 4 when starting.

## Seed corpus DB
`C:/Users/bartl/dev/Determined/C_Users_bartl_dev_Determined_examples_commonplace_seed.db`
9 files, 2 stubs, graph_edges populated [V]
