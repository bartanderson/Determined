# SESSION STATE - session 79 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 79, 2026-07-05)

### RM13 #7 -- Context mode switching (DONE)
- Three mode buttons in topbar: 📐 Design / 🔗 Trace / ✅ Review
- Each switches to its primary tab (Knowledge / Call tree / Doc health)
- Highlights related tabs with colored underline (blue/orange/green)
- Shows a slim mode banner above the tab bar with colored label + hint text
- Clicking the active mode button again clears the mode
- CSS: `.mode-btn`, `.mode-banner`, per-mode tab `border-bottom` highlights, trail-bar glow in Trace mode
- JS: `setMode()`, `clearMode()`, `_MODES` config object
- style.css: added 4th `auto` row to `.main` grid-template-rows to accommodate banner
- Verified in browser: all three modes switch tabs, colored labels correct, tab highlights visible
- Also fixed: call tree double-expand race -- clicking ▶ twice before server responded
  created two `.ct-children` divs; fold only hid the first. Guard added: `if (li._ctPending) return`
- 426 tests passed, 1 skipped. Commit: f269117.

## NEXT SESSION -- start here

**RM13 is now fully done** (#1+A3+A4+F7+W4+W5+#7 all landed).

**Pending housekeeping:**
- Run `ingest_design_docs` via the UI to re-extract clean design notes from dj2 docs.
  (All 268 old notes purged last session; DB is empty for kind=design_note until re-extracted.)

**Next open items (from TRACKER.md):**
- RM11: edit_file agent tool (LOW effort -- wiring only, write logic already exists)
- RM12: SearXNG web search agent tool (MEDIUM)
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)

Do NOT batch multiple items. Verify each in browser before moving to next.

## Current Determined status

### Test count: 426 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- RM11: edit_file agent tool (LOW -- wiring only)
- RM12: SearXNG web search agent tool (MEDIUM)
- RM13: UI redesign pass -- DONE (#1+A3+A4+F7+W4+W5+#7 all done)

### Commonplace status
- Working skeleton: capture, browse, search, storage, utils all functional
- 8 stubs total across all topology shapes (all verified in corpus)
- Seed state built and verified (examples/commonplace/seed/)
- DESIGN.md ingested -- 10 rules live in Commonplace DB
- Missing: journey step validation (deferred), guided UI highlighting (deferred)

## Hardware facts
- llama-server: on-demand subprocess, port 8081, Qwen3-8B on GPU (~3s/call)
- Started by UI on launch (background thread), stopped on exit (atexit)
- No NSSM service. Configure via LLM_SERVER_EXE / LLM_MODEL_PATH in llm_client.py.

## Corpus state
- dj2 DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db (47 stubs, 35 ABC gaps)
  - design_notes: PURGED (268 deleted). Re-run ingest_design_docs to repopulate.
- Commonplace DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
- Commonplace seed DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace_seed.db
- Determined DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, use python
Use PowerShell tool (not Bash). NEVER use python -c with inner quotes - write .py scripts.
