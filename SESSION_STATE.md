# SESSION STATE - session 87 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main
Uncommitted changes from session 86 still pending. Regression tests not yet run.

## What happened this session (session 87, 2026-07-05)

No Determined code work done this session. Spent session investigating Claude Code
remote control setup -- trying to find a way to initiate a remote control session
from the CLI so Bart can continue on phone. Dead end: CLI requires API key (not
subscription), and Claude Code desktop can join but not initiate remote control
(known open issue with Anthropic). Created a desktop shortcut "Remote Control Claude"
that runs `claude --remote-control` for when/if the auth situation changes.

## NEXT SESSION -- start here

**Exact same next steps as session 86:**

1. Read .claude/step_queue.md
2. Run `pytest tests/regression/ -q` -- all tests must pass before commit
3. Commit: ui_server.py fix + COMMONPLACE_JOURNEY.md + SESSION_STATE.md
4. Walk journey step 7: Corpus panel -> 0 design notes -> needs Scan button (F2)
   F2 fix: add "Scan for design docs" button next to design notes count in corpus panel

## Changes uncommitted (carried over from session 86)

- `determined/ui/ui_server.py` -- reingest_file call fixed (_db_path not oracle)
- `docs/COMMONPLACE_JOURNEY.md` -- step 6 result recorded

## Current Determined status

### Test count: 436 passed, 1 skipped (as of session 85 -- not re-run)

### Open TRACKER items
- RM15: Commonplace guided journey (ACTIVE -- step 7 next)
  - Step 6 DONE: reingest bug fixed, loop verified
  - Step 7: design notes scan button (F2)
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass (FUTURE)

## Hardware facts
- llama-server: on-demand subprocess, port 8081, Qwen3-8B
- Lazy-started on first generate()/chat() call if not running
- SearXNG: user-run Docker, default http://localhost:8888
- UI server: process on port 5050, started manually

## Corpus state
- Commonplace seed DB: C_Users_bartl_dev_Determined_examples_commonplace_seed.db
  - 8 files, 0 hot, 1 stub (extract_full_content only)
- dj2 DB: C_Users_bartl_dev_dj2.db
- Commonplace full: C_Users_bartl_dev_Determined_examples_commonplace.db
- Determined: C_Users_bartl_dev_Determined.db
