Written at commit: 8314e60
# SESSION STATE - session 101 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 101, 2026-07-06)

**Step queue updated [V]:**
- Updated `.claude/step_queue.md` to reflect session 101 state:
  PREVIOUS = "session 100 wrap committed"
  CURRENT  = "RM15 step 2 -- implement extract_metadata stub, reingest, watch frontier drop"
  NEXT     = "RM15 step 3 -- add storage queries, watch orphaned-impl drop"

**RM15 Step 2 -- extract_metadata implemented (uncommitted) [V]:**
- `examples/commonplace/seed/services/extractor.py` -- extract_metadata is now real code
- Uses `urllib.request.urlopen` to fetch URL, `html.parser.HTMLParser` subclass
  `_TitleParser` (inner class inside function body) to extract `<title>` tag
- Returns `{"title": ..., "description": "", "raw_html": ...}`
- `extract_full_content` is still a stub (returns "")
- `_TitleParser` inner class methods (`handle_starttag`, `handle_endtag`,
  `handle_data`) are defined inside the function body -- `_iter_top_level_functions`
  (fixed last session) skips these, so they will NOT appear as corpus roots

**NOT YET DONE:**
- No reingest run -- server was not started this session
- No commit for the extractor.py change

## NEXT SESSION -- start here

1. **Commit the extractor.py change:**
   `git add examples/commonplace/seed/services/extractor.py`
   `git commit -m "RM15 step 2: implement extract_metadata (urllib + html.parser)"`

2. **Start the server** (launch.json `determined-ui` or `.venv\Scripts\python.exe determined/ui/ui_server.py`)

3. **Load seed corpus** (`examples/commonplace/seed`) and reingest

4. **Verify Frontier Direct drops from 2 stubs to 1:**
   - `extract_metadata` should become a normal implemented symbol (no longer red)
   - `extract_full_content` should remain the only stub
   - Roots should still show only `capture` and `index` (no inner class leakage)

5. **RM15 Step 3** (after step 2 verified): add storage queries to seed
   (`storage/db.py` has `init_db` implemented; step 3 likely means adding
   query functions that are stubs -- check COMMONPLACE_VISION.md Step 3 spec)

## Known issues

**DB lock on Re-analyze [?]:** discover_run background thread holds a second
sqlite3 connection; close-oracle logic in ui_server.py ~line 500 doesn't close it.
Workaround: kill server, delete seed.db, restart. Low priority.

**dj2 design notes [?]:** 268 purged session 79, still empty for kind=design_note.
Run ingest_design_docs via UI when dj2 corpus is loaded.

**Test count: 440 passed, 1 skipped [V]** (from session 100 run; no .py engine
changes this session so still valid)
