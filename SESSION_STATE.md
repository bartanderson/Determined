# SESSION STATE - session 80 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 80, 2026-07-05)

### RM11 close-out (already done in prior session, just not tracked)
- edit_file(assessor, args) was fully implemented: read_file, write_file, replace_in_file ops
- Path-boundary guard against project root. TOOLS dict, tool_registry entry, 12 regression tests.
- TRACKER updated to DONE.

### RM12 -- SearXNG web search agent tool (DONE)
- search_web(assessor, args) in agent_tools.py
- Hits SearXNG /search?format=json, returns top-N results as title/URL/snippet text
- SEARXNG_URL config in llm_client.py (default http://localhost:8888; None = disabled)
- Graceful degradation when SearXNG is unreachable (returns message, does not raise)
- Wired into TOOLS and tool_registry (category: external)
- 10 new regression tests. 436 passed, 1 skipped. Commit: c34f65e.

### Sidebar icon-nav concept (designed, not built)
- Proposed: 4-icon vertical rail replaces the current 6-section sidebar
- Icons: Corpus (database) / Navigate (compass) / Tools (tool) / Ask (message, pinned bottom)
- Clicking active icon collapses panel to rail-only (max editor space)
- CSS: .shell grid gets 3 columns (40px rail + panel + 1fr main)
- Mockup shown in session. Ready to implement when Bart says go.

## NEXT SESSION -- start here

**Pending housekeeping:**
- Run `ingest_design_docs` via the UI to re-extract clean design notes from dj2 docs.
  (All 268 old notes purged session 79; DB is empty for kind=design_note until re-extracted.)

**Next open items (from TRACKER.md):**
- Sidebar icon-nav (UI improvement, ~1.5h -- see mockup from this session)
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)

Do NOT batch multiple items. Verify each in browser before moving to next.

## Current Determined status

### Test count: 436 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- Sidebar icon-nav: UI improvement (not filed in TRACKER yet -- file when starting)

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
