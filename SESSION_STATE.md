# SESSION STATE - session 77 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main (both repos)
Clean state. All commits landed.

## What happened this session (session 77, 2026-07-04)

### Cleanup: llama3.2 misses from session 76
- `determined/ui/preview.html` and `determined/ui/templates/console.html` had hardcoded
  "Ollama llama3.2:3b" / "llama3.2:3b" labels — missed because cleanup only targeted .py files.
- Added `LLM_DISPLAY_NAME = "Qwen3-8B"` to `llm_client.py` as single source of truth.
- `console.html` now uses `{{ model_name }}` injected from `render_template`.
- `preview.html` (static mock) updated to Qwen3-8B with sync comment.
- `tests/item14_phase2_instructions.md` marked HISTORICAL with correct backend info.
- Commits: 146ed09, 146ed09 (display name fix)

### On-demand LLM launch — NSSM service removed
- `llm_client.py`: added `LLM_SERVER_EXE`, `LLM_MODEL_PATH`, `LLM_SERVER_ARGS` constants;
  `start_server()` spawns subprocess if not running; `stop_server()` terminates it.
- `ui_server.py`: `run_server()` calls `start_server()` in background thread on UI launch;
  `stop_server()` registered via `atexit`. Old `_check_llm()` / `_warmup_llm()` removed.
- `local_agent.py`: error message updated (no more nssm reference).
- NSSM service `llama-server-8b` deleted from Windows.
- `CLAUDE.md` common mistakes updated.
- 426 tests passed, 1 skipped. Commits: a6321e8, 53d306f.

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
- llama-server: on-demand subprocess, port 8081, Qwen3-8B on GPU (~3s/call)
- Started by UI on launch (background thread), stopped on exit (atexit)
- No NSSM service. Configure via LLM_SERVER_EXE / LLM_MODEL_PATH in llm_client.py.

## Corpus state
- dj2 DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db (47 stubs, 35 ABC gaps)
- Commonplace DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
- Commonplace seed DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace_seed.db
- Determined DB: C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined.db

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, use python
Use PowerShell tool (not Bash). NEVER use python -c with inner quotes - write .py scripts.
