# SESSION STATE - session 82 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 82, 2026-07-05)

### Commonplace work arc clarified and recorded
- Realized RM15 (Commonplace guided journey) was the missing next item -- it was in
  COMMONPLACE_VISION.md but not connected to active work tracking.
- COMMONPLACE_VISION.md updated: added "The actual work arc" section at the top with
  clear framing of the two paths and the iterative approach.
- TRACKER.md: RM15 filed as ACTIVE next item. Dashboard updated.

### The work arc (important -- read this)
Two paths through the Commonplace journey:
- **Easy path**: start from seed skeleton, use Determined to understand and fill it out
- **Hardcore path**: build seed from scratch with Determined open, ingest as you go

Both converge at seed → complete → enhance (tagger, semantic search, connections).

This is iterative work: start server, point at seed (or blank dir), walk journey steps,
fix Determined when something breaks, continue. Not a one-shot audit.

## NEXT SESSION -- start here

**Active item: RM15 -- Commonplace guided journey**
Start the Determined server, point it at examples/commonplace/seed/, and walk the
journey steps from COMMONPLACE_VISION.md. Fix the tool where the experience breaks.

**Pending housekeeping (do first):**
- Run `ingest_design_docs` via the UI to re-extract clean design notes from dj2 docs.
  (All 268 old notes purged session 79; DB is empty for kind=design_note until re-extracted.)

**FUTURE items (not next):**
- Item 27: Standards self-review
- RM9: Connect to Q4 MCTS
- RM10: DeRe-CoT recomposition pass in goal_intake

## Current Determined status

### Test count: 436 passed, 1 skipped

### Open TRACKER items
- RM15: Commonplace guided journey (ACTIVE)
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)

### Commonplace status
- Working skeleton: capture, browse, search, storage, utils all functional
- 8 stubs across all topology shapes (direct-call, chain, ABC, conditional)
- Seed state built and verified (examples/commonplace/seed/)
- Complete app at examples/commonplace/
- DESIGN.md has 6 authority rules + 4 open design tensions + stub roadmap
- Guided UI highlighting: deferred (Phase 4) -- not needed to run the journey

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
