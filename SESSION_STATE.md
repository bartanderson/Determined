Written at commit: 3a69ef5
# SESSION STATE - session 103 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 103, 2026-07-06)

**RM15 Step 4 completed [V]:**
- Root cause found: seed DB had 0 SOTS tenets, 2 noise design_notes -- check_design_violations
  returned low-signal results until DESIGN.md was ingested
- `examples/commonplace/docs/DESIGN.md` already existed (not a missing file)
- Problem: `ingest_design_docs` uses `oracle.get_project_root()` which returns `seed/`,
  not `examples/commonplace/` -- DESIGN.md was never discovered
- Fix: direct `discover_docs` + `extract_rules` call on `examples/commonplace/`, inserted
  10 design_notes into seed DB manually via script
- After ingest: `check_design_violations("extract_metadata")` returns score=0.43 for
  "extractor.py: one module or three?" -- highest signal, correct hit [V]
- `reason_about`: "should extractor be split?" -> Keep unified, 95% confidence.
  Reasoning: 1 caller, 5 callees, SOTS "avoid unnecessary indirection" fires [V]

**RM15 Step 5 completed [V]:**
- Added 5 new service files to seed: tagger.py, linker.py, searcher.py, pipeline.py, processor.py
- Added routes/search.py, search_entries stub to storage/queries.py
- Wired capture.py to call `pipeline.enrich_entry`
- Reingested all 8 files via reingest_file()
- Topology after reingest [V via script output]:
  - Stubs: 2 -> 10, Implemented: 6 -> 16
  - Chain-head: 1 (enrich_entry -- called by capture, calls stub services)
  - Chain-tail: 2 (find_connections, suggest_tags)
  - ABC-interface: 2 (EntryProcessor.process, can_handle -- no override)
  - Orphaned-impl: 6 (_call_llm, _parse_tags, _similarity_score, etc.)
  - Disconnected: 1
- find_abc_gaps correctly surfaces EntryProcessor gap [V]
- Committed as 3a69ef5 [V]
- 440 passed, 1 skipped [V]

**Known issue discovered: ingest_design_docs project root mismatch**
The seed DB project root is `seed/` but DESIGN.md lives at `examples/commonplace/docs/`.
`ingest_design_docs` cannot find it via normal path. Workaround used this session:
direct script calling `discover_docs` + `extract_rules` on the parent dir.
This should probably be fixed in `ingest_design_docs` to accept an explicit path arg.

## Known issues (carried forward)

**UI Re-analyze+ does NOT use reingest_file [V]:** Runs background discover_run thread.
Workaround: call `reingest_file()` from Python CLI directly.

**Frontier Load button navigates to Chat [?]:** Clicking "Load + Enter" in Frontier tab
switches active tab back to Chat. Workaround: unknown.

**DB lock on Re-analyze [?]:** discover_run holds a second sqlite3 connection.
Workaround: kill server, delete seed.db, restart.

**Test count: 440 passed, 1 skipped [V]**

## NEXT SESSION -- start here

1. **RM15 Step 6:** Work the topology shapes
   - `find_abc_gaps` -- already verified working, returns EntryProcessor gap
   - `find_conditional_stubs` -- check if any conditional stubs exist in seed
   - `detect_topology` chain shapes -- reason about implementation order
   - Tool calls via Python script (same pattern as this session)

2. **Optional Determined improvement:** add `path` arg to `ingest_design_docs` so it
   doesn't require `get_project_root()` to find the design docs dir. Low effort, high
   value for any corpus where docs live outside the ingested root.

3. Seed DB is current -- no reingest needed before step 6.

4. Update `.claude/step_queue.md` CURRENT to step 6 when starting.

## Seed corpus DB
`C:/Users/bartl/dev/Determined/C_Users_bartl_dev_Determined_examples_commonplace_seed.db`
16 files, 10 stubs, 12 design_notes (10 from DESIGN.md + 2 auto-generated noise)
graph_edges populated [V]
