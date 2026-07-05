# SESSION STATE - session 85 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main
Clean state. All commits landed.

## What happened this session (session 85, 2026-07-05)

### Step-queue constraint system (new)
Discussed behavioral constraint architecture. Agreed on a rolling 3-step micro-queue
(PREVIOUS/CURRENT/NEXT) maintained in .claude/step_queue.md, enforced by a
PreToolUse hook that fires before Edit/Write/preview_eval/preview_click/preview_fill/
mcp__claude-in-chrome. Hook injects queue contents as additionalContext so Claude
must verify its action serves CURRENT before proceeding. Blocks if file is missing.

Files added:
- .claude/step_queue_hook.ps1 -- the hook script
- .claude/step_queue.md -- the rolling queue (update each step)
- .claude/settings.json -- PreToolUse hook wired in

### RM15 journey fixes (from prior session, now committed)
- CSS: .tab-content grid-row 4->5 (Frontier/Graph/Topology now render at full height)
- ui_server: auto-reingest after save_file + emit corpus_ready (closes edit loop)
- console.html toast: "re-ingesting..." not "re-analyze corpus"
- extractor.py seed: extract_metadata stub implemented (stub count should drop to 1)
- CLAUDE.md: UI testing constraint added (fresh load, no eval injection)
- COMMONPLACE_JOURNEY.md: cumulative walk log, steps 1-5 verified

## NEXT SESSION -- start here

**Step queue entry point** (.claude/step_queue.md already set):
- CURRENT: Walk journey step 6 -- Editor save + reingest verification

**Concrete steps:**
1. Read .claude/step_queue.md -- it tells you where you are
2. Start server (preview_start "determined-ui")
3. Switch corpus to C_Users_bartl_dev_Determined_examples_commonplace_seed.db
   via the UI corpus switcher (fresh page load, not eval injection)
4. Editor tab -> open extractor.py -> confirm extract_metadata has real implementation
5. The reingest fix is already in -- corpus_ready should fire after any save
6. Verify stub count drops (extractor.py save -> corpus panel shows 1 stub)
7. Record result in docs/COMMONPLACE_JOURNEY.md

**Step queue discipline:**
Before every Edit/Write/UI action, the hook will inject PREVIOUS/CURRENT/NEXT.
Update step_queue.md after each step completes. This is the new operating mode.

**FUTURE items (not next):**
- F1: Frontier mode default to Direct on tab open
- F2: "0 design notes" Scan button in corpus panel
- F3: REPL startup hint when coverage 0%
- Item 27: Standards self-review
- RM9/RM10: MCTS / DeRe-CoT

## Current Determined status

### Test count: 436 passed, 1 skipped

### Open TRACKER items
- RM15: Commonplace guided journey (ACTIVE -- step 6 next)
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass (FUTURE)

## Hardware facts
- llama-server: on-demand subprocess, port 8081, Qwen3-8B
- Lazy-started on first generate()/chat() call if not running
- Started by UI on launch, stopped on exit
- SearXNG: user-run Docker, default http://localhost:8888

## Corpus state
- Commonplace seed DB: C_Users_bartl_dev_Determined_examples_commonplace_seed.db
  - 8 files, 2 stubs (extract_metadata NOW IMPLEMENTED -- reingest needed to confirm)
- dj2 DB: C_Users_bartl_dev_dj2.db (design_notes purged session 79, not yet repopulated)
- Commonplace full: C_Users_bartl_dev_Determined_examples_commonplace.db
- Determined: C_Users_bartl_dev_Determined.db
