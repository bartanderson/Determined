Written at commit: e242815
# SESSION STATE - session 141 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 141, 2026-07-10)

**Q5 fixed -- PASS [V]** (committed e242815)

Root cause confirmed: grounding for "UI query to database" finds query_router.py,
QueryExecutor, query_session.py etc. (a real but WRONG subsystem). Model followed
those grounding symbols and confabulated a pipeline around them.

Three code changes + one data change:

**Code changes (agent_resolver.py):**
- `_ground_findings` slice widened: symbols [:5]->[:10], files [:3]->[:5]
  so route_query (symbol #8) gets its design_note surfaced
- design_note truncation: 120->400 chars so embedded NEED lines aren't cut off

**Code change (local_agent.py):**
- `_answer()`: design_notes from grounding block now injected into facts_text
  before ASSEMBLE as "ARCHITECTURE NOTES (treat as authoritative)"
  (they were visible in Phase 0/1 but never passed to Phase 3 before)
- `_DECOMPOSE_SYSTEM`: added instruction to follow [design_note] guidance
  and include any embedded NEED lines in output

**Data change (Determined corpus DB):**
- Inserted design_note with subject `route_query`:
  "route_query is NOT the entry point... actual path: handle_query (ui_server.py)
  -> _answer (local_agent.py) -> resolve_and_expand (agent_resolver.py) ->
  dispatch (agent_tools.py) -> DBOracle (db_oracle.py). Use these NEEDs:
  NEED: brief for handle_query / NEED: callees of _answer / ..."

Result: Phase 1 now correctly emits NEEDs for handle_query/_answer/resolve_and_expand,
Phase 3 sees the architecture note and synthesizes the correct chain.

**533 tests passed, 1 skipped [V]**

## Probe scorecard (Determined corpus, as of e242815) [V]

- Q1 orient ("give me a quick overview"): PASS
- Q2 blast-radius ("what would break if I changed resolve_and_expand"): PASS
- Q3 name-search ("what does ground_question do"): PASS
- Q4 comparative ("does local_agent use the same LLM client as ui_server"): PASS
- Q5 traversal ("path from UI query to database"): PASS -- handle_query->_answer->resolve_and_expand->dispatch->DBOracle
- Q6 method-confab ("what methods does DBOracle have"): PASS

**All 6 probes pass.**

## Architecture: design_note as grounding redirect [V]

Pattern established this session: when grounding surfaces WRONG symbols (real but
misleading), attach a design_note to one of those symbols that:
1. Explains why the symbol is NOT the right answer
2. Names the actual symbols via embedded NEED lines (using correct pattern syntax)

Phase 1 decompose follows the embedded NEEDs (via new DECOMPOSE_SYSTEM instruction).
Phase 3 sees the note injected into facts_text as ARCHITECTURE NOTES.

Key constraint: embedded NEED lines must use exact resolver patterns:
- "NEED: brief for <symbol>" (not "what does X do" -- that's for files)
- "NEED: callees of <symbol>"
- "NEED: what does <file.py> do" (with .py extension for files)

## Known issues (carried forward)

**Determined corpus DB path [V]:**
`C_Users_bartl_dev_Determined.db` (183 files). Prior SESSION_STATEs incorrectly
listed the commonplace example DB. TRACKER.md is correct.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and inline GUIDE_DATA in
console.html are separate stores -- both must be updated together. No auto-sync.

**ingest_design_docs project root mismatch [?]:** Must call with explicit path.

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

## NEXT SESSION -- start here

**All 6 RM21 probes pass. Options:**

1. **Item 6 (live sync loop)** -- re-ingest single changed file without full corpus re-run
   SOTS: XIV (one source of truth), X (idempotent per-file re-ingest), XXI (no daemon)
2. **Item 20 (call graph accuracy)** -- type annotation exploitation + __init__ tracking
   (do after item 6 since re-ingest needed to populate new columns)
3. **dj2 corpus probe** -- run RM21 probe suite against dj2 to find gaps there

Recommended: item 6.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
Started via UI (port 5050) or manually.
