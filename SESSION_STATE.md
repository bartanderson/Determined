Written at commit: eb7e5e3 (Determined)
# SESSION STATE - session 120 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 120, 2026-07-08)

**RM28 Stage 1: Artifact layer -- DONE [V]**
- 7 files changed, 452 insertions (commit eb7e5e3)
- workflow_store.py: VALID_KINDS gains 'artifact'; ensure_artifact_columns()
  migration adds tool_name/artifact_status/feeds_into to workflow_items and
  ingested_at to files; store_artifact(), get_artifact_by_name(),
  list_artifacts(), mark_stale_by_files(), _cascade_staleness() added
- persistence_engine.py: _migrate() adds files.ingested_at to existing corpus DBs
- reingest_file.py: apply_file_delta() stamps files.ingested_at after each reingest
- ui_server.py: get_artifacts socket handler (ensure_artifact_columns safe on old DBs)
- console.html: Artifacts sub-panel in Build queue tab (name/tool/status/timestamp)
- 13 new tests; 506 passed, 1 skipped [V]

**step_queue.md updated [V]**
- Was pointing at RM15 (done); now points at RM28 Stage 2 next

## NEXT SESSION -- start here

**RM28 Stage 2: Tour mode**

Scripted step-by-step walkthrough of the Commonplace corpus. Proves the mode
concept before building Workbench (Stage 3) or Discovery (Stage 4).

**What to build:**
- Tour panel in UI: current step, instruction text, Run button, explanation
- Tour script (static, Python list or JSON): step name, instruction, tool to
  call, explanation of output
- Steps mirror COMMONPLACE_USER_JOURNEY.md arc:
  1. Orient (corpus map, entry points, gap summary)
  2. Frontier Direct (stubs)
  3. Frontier Orphan (unwired impls)
  4. Frontier ABC (interface gaps)
  5. Topology (action queue)
  6. Tools (gap analysis, docstring health, design violations)
  7. Knowledge (distillation, design notes)
- Each step: instruction shown -> user clicks Run -> tool fires -> output in
  main panel -> explanation shown -> Next advances
- Completion tracked per step (localStorage or session state)
- Free exploration allowed; AI Q&A available throughout (existing Ask bar)

**Where to start:**
1. Read TRACKER.md RM28 (full spec, tour arc section)
2. Read console.html for tab/panel structure to decide Tour placement
3. Define tour script as Python list in ui_server.py or a JSON file
4. Build Tour panel HTML + JS + socket handlers

**Key constraint:** Tour is Commonplace-only (scripted known content).
Use COMMONPLACE_USER_JOURNEY.md as source of truth for step descriptions.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [V]:** Clear design_notes + semantic_summaries
  before a clean demo. Structural facts (entry, hot, dead) are valid, keep them.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
