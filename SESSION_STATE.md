# SESSION STATE - session 88 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main
All changes committed. Tests passing at 436/1 skip.

## What happened this session (session 88, 2026-07-05)

1. Ran regression tests (436 passed, 1 skipped) -- all green.
2. Committed session 86 carry-over: ui_server.py reingest fix + step 6 journey result.
3. F2: wired ingest_design_docs into post-ingest pass (commit a7dc167).
4. F1: Frontier tab resets to Direct mode on every open (commit 5c396b3).
5. F3: REPL startup hints "run orient or discover" when coverage < 10% (commit 5c396b3).
6. RM16 filed: UI concept documentation pass -- explain every panel/mode/concept
   in one line, always visible. Walk-driven, to be done after F1/F3.
7. COMMONPLACE_JOURNEY.md updated: F1/F2/F3 all marked DONE.

## NEXT SESSION -- start here

1. Read .claude/step_queue.md
2. Continue the Commonplace journey walk -- all known findings (F1/F2/F3) resolved.
   Next step: walk the journey fresh from step 1 with fixed tool, look for new gaps.
   OR: start RM16 (UI concept documentation pass) -- one sentence per panel/mode.

## Changes uncommitted
None -- all committed.

## Commits this session
- 42ef9e5: session 86 carry-over (reingest fix + journey step 6)
- a7dc167: F2 fix (ingest_design_docs in post-ingest pass)
- f243cf7: session 88 handoff + COMMONPLACE_JOURNEY step 7
- 1f07f40: RM16 filed
- 5c396b3: F1/F3 fixes

## Current Determined status

### Test count: 436 passed, 1 skipped

### Open TRACKER items
- RM15: Commonplace guided journey (ACTIVE -- re-walk or start RM16)
- RM16: UI concept documentation pass (FILED -- next after re-walk)
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
  - 8 files, 0 hot, 1 stub (extract_full_content only after step 6 reingest)
- dj2 DB: C_Users_bartl_dev_dj2.db
- Commonplace full: C_Users_bartl_dev_Determined_examples_commonplace.db
- Determined: C_Users_bartl_dev_Determined.db
