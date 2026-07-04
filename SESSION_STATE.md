# SESSION STATE - session 75 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 75, 2026-07-04)

### RM13 progress: A4 + F7 done

**A4 -- Universal sub-menu popover (DONE, verified in browser)**
- Left-click on any `.sym-link` now opens a sticky popover near the symbol
  instead of immediately opening the full spotlight panel.
- Popover shows: risk badge, symbol name, type/file/line, docstring snippet,
  caller/callee counts, and four action buttons: callers, callees, graph, spotlight.
- `symbol_quick` results cached in `_sqCache` Map so popover renders instantly
  for already-fetched symbols (sidebar symbols are pre-fetched for ambient badges).
- Hover tooltip suppressed when popover is open (`|| _popoverSym` guard).
- Closes on: Escape, click outside, or clicking same sym-link again.
- Spotlight still accessible via "spotlight" button in the popover.
- Cytoscape graph node tap also opens popover now.

**F7 -- Frontier Orphan/Disconnected mode (DONE, verified in browser)**
- Added `<option value="orphan">Orphan (disconnected)</option>` to fg-mode select.
- Backend: new `orphan` branch in `handle_get_frontier_graph()` queries implemented
  functions with no real callers. Labels: anticipatory (no callers at all) vs
  stranded (only stub callers).
- Frontend: blue nodes for anticipatory, gray for stranded. Status bar shows counts.
- dj2 corpus: 72 anticipatory nodes, 0 stranded.

426 tests passed, 1 skipped. Commit: c931879.

## NEXT SESSION -- start here

**Continue RM13: UI redesign pass**

Remaining items in recommended order:
1. **#1 -- Chat/ask bar hidden by default**: The query bar should be hidden on
   load, revealed only when Ask button is clicked. Verify current behavior --
   it may already be correct since `style="display:none"` is set in HTML.
   If it shows after corpus load, fix the corpus_ready handler.
2. **A3 -- Collapse duplicate Cytoscape edges**: Same caller to same callee via
   multiple paths should show as one edge with a count badge. Affects gx (call
   graph) and fg (frontier) tabs.
3. **W4-W5 -- Trail polish**: Breadcrumb shows file context alongside symbol name.
   Export trail as session summary (symbol path + risk scores + findings).
4. **#7 -- Context mode switching**: module-design / call-trace / gap-review modes
   as distinct contexts. Highest effort item; do last.

Do NOT batch multiple items. Verify each in browser before moving to next.

## Current Determined status

### Test count: 426 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- RM12: SearXNG web search agent tool (MEDIUM -- lower priority than UI redesign)
- RM13: UI redesign pass (HIGH -- in progress, A4+F7 done this session)

### Commonplace status
- Working skeleton: capture, browse, search, storage, utils all functional
- 8 stubs total across all topology shapes (all verified in corpus)
- Seed state built and verified (examples/commonplace/seed/)
- DESIGN.md ingested -- 10 rules live in Commonplace DB
- Missing: journey step validation (deferred), guided UI highlighting (deferred)

## Hardware facts
- llama-server-8b: NSSM auto service, port 8081 (8B on GPU, ~3s/call)

## Corpus state
- dj2 DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db (47 stubs, 35 ABC gaps)
- Commonplace DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
- Commonplace seed DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace_seed.db
- Determined DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, use python
Use PowerShell tool (not Bash). NEVER use python -c with inner quotes - write .py scripts.
