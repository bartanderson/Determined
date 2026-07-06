Written at commit: 9c6163a
# SESSION STATE - session 100 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 100, 2026-07-06)

**RM15 started [V]:** Guided journey begun. Loaded seed corpus and walked Step 1 (Orient).

**Bug fixed -- nested class symbol leak (9c6163a) [V]:**
- `parse_ast._extract_functions` used `ast.walk(tree)` which traverses entire AST
- Inner class methods defined inside functions (e.g. `_P.handle_starttag` inside
  `extract_metadata`) leaked into symbol table and appeared as corpus roots
- Fix: replaced `ast.walk` with `_iter_top_level_functions` generator that only
  visits module-level and class-level defs, skipping function bodies
- Result: seed corpus Roots now correctly show only `capture` and `index`

**Seed fix -- extract_metadata made a stub (9c6163a) [V]:**
- `extract_metadata` in `seed/services/extractor.py` was fully implemented
  (with inner HTMLParser class) -- didn't match COMMONPLACE_VISION.md spec
- Made it a proper STUB returning empty dict
- Frontier now shows 2 direct-call stubs as designed:
  `extract_metadata > extract_full_content`, both called by `extract`

**Seed corpus state after ingest [V]:**
- 8 files · 0 hot · 2 stubs
- Roots: capture (↗11), index (↗2)
- Frontier Direct: 1 callers · 2 stubs · 0 chain · 2 edges
- `extract` → `extract_metadata` (stub) + `extract_full_content` (stub)
- GAPS: docs 63%, distilled 63%, 2 design notes, C: 63% (3 missing)

**DB lock issue observed [?]:**
- Re-analyzing the currently-loaded seed corpus triggered WinError 32 (file locked)
- Server's close-oracle-before-unlink logic (ui_server.py ~line 500) should handle this
- Workaround used: kill server, delete DB manually, restart server
- Root cause unclear -- may be `discover_run` background thread holding a second
  connection when Re-analyze fires. Not yet investigated fully.

**Test count: 440 passed, 1 skipped [V]** (run before commit)

## NEXT SESSION -- start here

1. **RM15 Step 2 -- Implement first stub:**
   frontier_priority points at `extract_metadata`. Run symbol_context on it in UI,
   implement it (urllib.request fetch + html.parser title extraction), reingest,
   watch Direct frontier drop from 2 stubs to 1.
   Seed corpus: `C:\Users\bartl\dev\Determined\examples\commonplace\seed`
   Server: restart with `start-server` or launch.json (`determined-ui`)

2. **DB lock bug (low priority):** investigate `discover_run` holding a second
   sqlite3 connection during Re-analyze; may need to join the thread before unlink.

3. **dj2 design notes still missing [?]:** 268 purged session 79; still empty for
   kind=design_note. Run ingest_design_docs via UI when dj2 corpus is loaded.
