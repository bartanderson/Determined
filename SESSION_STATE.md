# SESSION STATE - session 76 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 76, 2026-07-04)

### RM13 progress: #1 verified, A3 done

**#1 -- Chat/ask bar hidden by default (VERIFIED, no change needed)**
- `style="display:none"` is set in HTML at page load.
- `setCorpusLoaded()` does not touch the query bar.
- Ask toggle correctly reveals/hides it. Already correct.

**A3 -- Collapse duplicate Cytoscape edges (DONE, verified in browser)**
- Added `dedupeEdges(rawEdges)` helper near graph section.
- Groups same source->target edges into one element with `count` field.
- Used in both `graph_result` (gx) and `frontier_graph` (fg) handlers.
- Status bar appends "(N raw)" when duplicates were collapsed.
- GX_STYLE and FG_STYLE both have `edge[count > 1]` selector showing
  count as a small label on the edge (font-size 8, auto-rotated).
- Verified with synthetic data: 3 duplicate a->b edges collapse to one
  with count=3. Live graph renders cleanly with no regression.

426 tests passed, 1 skipped. Commit: 7041b0e.

### Ollama/3B/27B/qwen cleanup (DONE)
- All active "Ollama" references replaced with "LLM" throughout codebase.
- Port 8080 -> 8081 everywhere active (not historical).
- OLLAMA_MODEL/OLLAMA_URL/OLLAMA_TIMEOUT constants removed from
  semantic_summary.py; model_version now writes "llm-client".
- LLM_TIMEOUT import alias in local_agent.py cleaned up.
- Error messages updated to reference llama-server/8081.
- CLAUDE.md common mistakes updated.
- docs/DESIGN.md model references generalized.
- test function renames: no_ollama -> no_llm.
- determined/cmd/tune.py deleted (two-tier 3B+27B allocator, dead).
- Internal _call_ollama / _synthesize_with_ollama names preserved.
- Historical mentions in TRACKER.md / bug-context test comments preserved.

426 tests passed, 1 skipped. Commit: c641f15.

## NEXT SESSION -- start here

**Continue RM13: UI redesign pass**

Remaining items in recommended order:
1. **W4-W5 -- Trail polish**: Breadcrumb shows file context alongside symbol name.
   Export trail as session summary (symbol path + risk scores + findings).
2. **#7 -- Context mode switching**: module-design / call-trace / gap-review modes
   as distinct contexts. Highest effort item; do last.

Do NOT batch multiple items. Verify each in browser before moving to next.

## Current Determined status

### Test count: 426 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- RM12: SearXNG web search agent tool (MEDIUM -- lower priority than UI redesign)
- RM13: UI redesign pass (HIGH -- in progress, #1+A3+A4+F7 done)

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
