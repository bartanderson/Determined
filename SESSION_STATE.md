# SESSION STATE - session 81 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 81, 2026-07-05)

### TRACKER housekeeping
- RM13 marked DONE (was still open; git log showed all sub-items landed sessions 75-79)
- Dashboard blurb updated to reflect session 80 state

### Sidebar icon-nav (DONE)
- 4-icon vertical rail replaces the old flat sidebar
- Icons: 🗄 Corpus / 🧭 Navigate / 🔧 Tools / 💬 Ask (pinned bottom)
- Corpus panel: Analyze/switch + corpus map (Roots/Core) + Gaps at a glance
- Navigate panel: Start here (6 quick-start shortcuts only, clean/uncluttered)
- Tools panel: query shortcuts (open file, inspect symbol, callers, explain, findings, files)
- Ask icon: toggles query bar independently of panel state
- Clicking active icon collapses panel to rail-only (40px) for max editor space
- Shell grid: 40px rail + 210px panel + 1fr main (was 210px + 1fr)
- panel-collapsed class replaces sidebar-collapsed
- Spotlight updated to 4-col grid when open
- Inline padding moved to .sb-tools-body CSS class (per design token rules)
- 436 tests pass. Commit: 380814c.

## NEXT SESSION -- start here

**Pending housekeeping:**
- Run `ingest_design_docs` via the UI to re-extract clean design notes from dj2 docs.
  (All 268 old notes purged session 79; DB is empty for kind=design_note until re-extracted.)

**Next open items (from TRACKER.md):**
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)

No immediate next item filed. Ask Bart what's next.

## Current Determined status

### Test count: 436 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)

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
- SearXNG: user-run (Docker or standalone), default http://localhost:8888
  Configure SEARXNG_URL in llm_client.py. search_web returns "not configured" if None.

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
