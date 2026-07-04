# SESSION STATE - session 74 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 74, 2026-07-04)

### UI redesign scoped -- DISCOVERY_MODEL closed

Reconciled all DISCOVERY_MODEL items against UI_VISION.md (GOT model).
Filed RM13 in TRACKER.md as the single UI redesign pass item.

**UI items folded into RM13:**
- F7: Frontier tab Orphan/Disconnected mode
- A3: Collapse duplicate graph edges (Cytoscape)
- A4: Universal sub-menu popover (symbol_context inline anywhere)
- W4-W5: Trail rendering and export polish

**UI_VISION.md open items also in RM13:**
- #1: Chat/ask bar hidden by default
- #7: Context mode switching (module-design / call-trace / gap-review modes)

**Non-UI items disposition:**
- F1 (false positive audit): backend accuracy, file separately if needed
- A1 (resolved flag + is_project_call): fold into item 20 territory
- A2 (access_paths query): file separately when needed
- A5 (multi-hop type trace): file separately when needed
- Q4: already RM9 (FUTURE)
- T5: FUTURE, post-production

DISCOVERY_MODEL is closed as a tracking category.

## NEXT SESSION -- start here

**Begin RM13: UI redesign pass**

Start with the highest-leverage items first:
1. A4 -- universal sub-menu popover: symbol_context as inline popover on
   any symbol reference (chat results, editor, call tree rows). This is
   the core GOT gear-on-gear interaction. Read `determined/ui/ui_server.py`
   and the existing spotlight implementation before touching anything.
2. F7 -- Frontier tab: add Orphan/Disconnected mode to the type selector.
   Mechanical, low risk. `find_orphaned_impls()` already exists in agent_tools.py.
3. After both verified in browser, continue with #1 (chat hidden), A3 (edge
   collapse), W4-W5 (trail), and #7 (context modes) in that rough order.

Do NOT batch all items into one large change. Verify each in browser before
moving to the next. Follow UI verify rule from CLAUDE.md.

## Current Determined status

### Test count: 426 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- RM11: DONE (edit_file agent tool)
- RM12: SearXNG web search agent tool (MEDIUM -- lower priority than UI redesign)
- RM13: UI redesign pass (HIGH -- start here)

### Commonplace status
- Working skeleton: capture, browse, search, storage, utils all functional
- 8 stubs total across all topology shapes (all verified in corpus)
- Topology shapes in corpus: ABC-interface (2), chain-head (1), chain-tail (2),
  direct-call (5), conditional stub (1), disconnected (1)
- DESIGN.md ingested -- 10 rules live in Commonplace DB
- Seed state built and verified (examples/commonplace/seed/)
- Three-phase build model documented in COMMONPLACE_VISION.md
- Missing: journey step validation (deferred -- tool not stable enough yet),
  guided UI highlighting (deferred -- UI redesign first)

## Hardware facts
- llama-server-8b: NSSM auto service, port 8081 (8B on GPU, ~3s/call)

## Corpus state
- dj2 DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db (47 stubs, 35 ABC gaps)
- Commonplace DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db (8 stubs, 10 design rules)
- Commonplace seed DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace_seed.db
- Determined DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, use python
Use PowerShell tool (not Bash). NEVER use python -c with inner quotes - write .py scripts.
