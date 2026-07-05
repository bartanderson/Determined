# SESSION STATE - session 78 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 78, 2026-07-05)

### W4-W5 -- Trail polish (RM13)
- Trail chips now show file context alongside symbol name (e.g. `dm_response world_app.py`).
- Risk-colored borders on chips: WARM=orange tint, HOT=red tint.
- File/risk data pulled from `symbol_quick_result` cache; enriched retroactively
  via `_trailEnrichFromCache()` when quick data arrives after the chip is created.
- "Export" button added to trail bar: copies markdown session summary to clipboard.
  Format: `# Session Trail\n1. **symbol** (file.py) [RISK]`
- CSS additions: `.trail-file`, `.trail-chip-hot`, `.trail-chip-warm`, `.trail-export`
- Verified in browser: two symbols, correct file labels, correct risk colors, export output confirmed.
- 426 tests passed, 1 skipped. Commit: 9ac1f4d.

### Stale design_note cleanup
- Spotlight panel for `process_message` surfaced a design_note with stale NSSM/llama3.2-3b info.
- Source: `dj2/SESSION_STATE.md` and usage docs still referenced NSSM/llama3.2-3b.
- Fixed: updated `dj2/SESSION_STATE.md` hardware facts, removed Ollama pipe examples
  from `dj2/ai_context/USAGE.md` and `dj2/Scripts/README_CONTEXT_SYSTEM.md`.
- Purged all 268 design_notes from dj2 corpus DB (re-extract clean on next ingest_design_docs run).
- dj2 commit: b173d68.

## NEXT SESSION -- start here

**Continue RM13: UI redesign pass**

Remaining item:
1. **#7 -- Context mode switching**: module-design / call-trace / gap-review modes
   as distinct contexts that each surface the right panels. Highest effort item.

Also pending:
- Run `ingest_design_docs` via the UI agent to re-extract clean design notes from dj2 docs.
  (All 268 old notes purged; DB is empty for kind=design_note until re-extracted.)

Do NOT batch multiple items. Verify each in browser before moving to next.

## Current Determined status

### Test count: 426 passed, 1 skipped

### Open TRACKER items
- Item 27: Standards self-review (FUTURE)
- RM9: Connect to Q4 MCTS (FUTURE)
- RM10: DeRe-CoT recomposition pass in goal_intake (FUTURE)
- RM12: SearXNG web search agent tool (MEDIUM -- lower priority than UI redesign)
- RM13: UI redesign pass (HIGH -- in progress, #1+A3+A4+F7+W4+W5 done, #7 remains)

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
