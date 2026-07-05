# SESSION STATE - session 84 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 84, 2026-07-05)

### corpus panel UX pass (RM15 prep)
Bart flagged several issues with the corpus panel section: Roots/Core unlabeled,
Gaps disconnected from stubs, distilled showing 101%, view stubs firing an LLM query.

Changes (commit 1982667):
- Roots / Core toggle: one section visible at a time, Roots default, hover tooltips
  explain the distinction on each tab label
- Gaps consolidated inside corpus-map-inner (renderCorpusMap now owns it), directly
  below Roots/Core -- stubs count + coverage gaps grouped as "what's incomplete"
- view stubs now calls activateTab('frontier') directly, no LLM needed, tooltip
  explains what stubs are
- distilled% capped at 100% (was showing 101%)
- Removed standalone #gap-summary-section div from HTML
- llm_client: _ensure_server() lazy-start wrapper added to generate() and chat()
  so the LLM restarts on demand if it crashed after server launch

436 passed, 1 skipped.

### Design principle articulated by Bart (internalize this)
Everything surfaced in the UI earns its place by being explainable in one hover
sentence. If it can't be explained that way, it belongs in the tutorial (the
Commonplace guided journey). The move is always "find where it belongs and make
the purpose legible" -- not cut. The tutorial is where each piece gets explained
once, in context, as the user actually needs it. The journey + polish iterate
together from real use.

### Housekeeping NOT done
ingest_design_docs for dj2 was attempted but failed -- llama-server was down
(that's what surfaced the lazy-start gap). With lazy-start now in place, this
should work next session once the server restarts.

## NEXT SESSION -- start here

**Active item: RM15 -- Commonplace guided journey**
1. Start server (pointing at dj2 for housekeeping first, OR switch straight to seed)
2. Run ingest_design_docs for dj2 (design notes were purged session 79; 268 deleted)
3. Switch corpus to examples/commonplace/seed/
4. Walk the journey steps from COMMONPLACE_VISION.md
5. Fix Determined where the experience breaks

The lazy-start wrapper means ingest_design_docs should now work even if
llama-server wasn't running when the server launched.

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

## Hardware facts
- llama-server: on-demand subprocess, port 8081, Qwen3-8B on GPU (~3s/call)
- Now also lazy-started on first generate()/chat() call if not running
- Started by UI on launch (background thread), stopped on exit (atexit)
- No NSSM service. Configure via LLM_SERVER_EXE / LLM_MODEL_PATH in llm_client.py.
- SearXNG: user-run (Docker or standalone), default http://localhost:8888

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
