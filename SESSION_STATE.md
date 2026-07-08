Written at commit: 0aaa111 (Determined)
# SESSION STATE - session 115 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 115, 2026-07-08)

**CWD desktop adapter deleted [V]**
User decided the fold benefits don't apply to this workflow (Claude Code already reads
files on demand). Deleted C:\Users\bartl\dev\context-warp-drive clone entirely.
Nothing pushed upstream, no impact. Memory saved: project_tool_call_repair.md
(validate-then-repair pattern for open model tool calls, four failure modes).

**RM15 Walk 4 Extra 1: wire suggest_tags to llama-server [V]**
- pipeline.enrich_entry: added llm_endpoint param, forwards to suggest_tags
- routes/capture.py: reads LLM_ENDPOINT from app config, passes to both call sites
- services/processor.py: fixed arg bug (EnrichmentProcessor was passing id as content)
- Seed left unchanged (TAGGING_ENABLED=False correct for seed state)
- Committed: da8b15e

**RM15 Walk 4 Extra 2+3: semantic_search + _similarity_score upgrade [V]**
- utils/text.py: added get_embed_model() lazy singleton (all-MiniLM-L6-v2) + cosine_similarity()
- services/searcher.py: semantic_search now embeds query + all entries, ranks by cosine (threshold 0.25), falls back to text search
- services/linker.py: _similarity_score upgraded from Jaccard to embedding cosine similarity, same fallback
- routes/search.py: now calls semantic_search instead of search
- Committed: d241528

**RM15 Walk 4 wrap-up: COMMONPLACE_USER_JOURNEY.md Phase 3 fully documented [V]**
All three extras verified and recorded with actuals. Phase 3 section updated from
NOT YET WALKED to PARTIALLY WALKED (all three done). Committed: 0df2a2c

**RM22 Phase 0 bootstrap: UI guidance [V]**
- console.html hint text: explains bootstrap pattern (write first .py, then Analyze, then reingest_file)
- scan_result handler: 0-file directories now show 3-step bootstrap guide instead of confusing modal
- Modal verified in browser (showModal test). Committed: 0aaa111

**Test count: 481 passed, 1 skipped [V]** (run at da8b15e, d241528, 0aaa111 -- all clean)

**Tool call repair pattern saved to memory [V]**
memory/project_tool_call_repair.md: four failure modes, validate-then-repair inversion,
relational invariants, schema hints. Applies to Determined/RM21.

## NEXT SESSION -- start here

**Step 0: update step queue [V needed]**
File: .claude/step_queue.md -- shows CURRENT as RM22 Phase 0 bootstrap (done).
Advance to RM22 walk.

**RM22 walk: Phase 0 scratch-to-seed (next concrete task)**
Write the Commonplace seed files one by one from a blank directory, document
actuals in COMMONPLACE_USER_JOURNEY.md Phase 0 section.

Approach: use the reverse-seed diff to determine file creation order.
  git diff examples/commonplace/seed/ examples/commonplace/ -- shows what the
  complete corpus adds over seed. Reverse = what to write to go seed→complete.
  For scratch→seed: start from nothing, write seed files in dependency order.

The two-step bootstrap (verified working):
  1. Write first file to empty directory
  2. Hit Analyze in UI → DB created
  3. reingest_file for each subsequent file

Prerequisite: create a blank working directory for the walk (not inside the repo).

**RM22 TRACKER: partially done**
UI piece done (committed 0aaa111). Walk documentation not yet done.
TRACKER.md RM22 item should be updated to reflect UI done, walk pending.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path, not auto-discovery.
**UI Re-analyze does NOT use reingest_file [V]:** Workaround: call from Python CLI directly.
**Duplicate design_note extraction [V]:** Filed as RM20. Not yet fixed.
**primitive_gap noise [V]:** Fix is RM19 Pass 3.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
