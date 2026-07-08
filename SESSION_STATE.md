Written at commit: 1a34081
# SESSION STATE - session 121 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 121, 2026-07-08)

**RM28 Stage 2: Tour mode -- DONE [V]**
- 3 files changed, 318 insertions (commit 1a34081)
- ui_server.py: _TOUR_STEPS (8-step list) + get_tour_steps socket handler +
  tour_run_step socket handler (background thread, dispatches via agent_tools.dispatch)
- console.html: Tour tab button + panel-tour (step header, progress dots,
  instruction, output pre, explanation callout, nav buttons, corpus hint banner)
- console.html: Tour JS (tourLoad, tourRender, tourRunStep, tourNext, tourPrev,
  socket.on tour_steps/tour_step_result, localStorage persistence)
- step_queue.md advanced to Stage 3
- 506 tests passed, 1 skipped [V]
- Verified in browser: step 1 runs knowledge_status, shows output + explanation;
  Next advances to step 2; corpus hint banner fires when non-seed corpus loaded [V]

**Tour steps (8 total):**
  1. Orient -- knowledge_status (file count, structural facts, gaps at a glance)
  2. Frontier Direct -- frontier_coverage (stub count, direct call stubs)
  3. Frontier Orphan -- find_orphaned_impls (anticipatory + stranded)
  4. Frontier ABC -- find_abc_gaps (abstract method coverage)
  5. Topology -- detect_topology (full structural picture + action queues)
  6. Conditional stubs -- find_conditional_stubs (hidden runtime gaps)
  7. Doc health -- docstring_health (missing + stale docstrings)
  8. Gap analysis -- gap_analysis (LLM brainstorm, stores proposals in build queue)

## NEXT SESSION -- start here

**RM28 Stage 3: Workbench palette**

Discovery tools exposed ad hoc with artifact output. Each tool run produces a
named artifact. User chains them manually. No sequence enforced.

**What to build:**
- Workbench tab (or panel within Build queue) with tool palette
- Each palette item: tool name, one-line description, [Run] button
- Running a tool stores result as artifact (kind=artifact) in workflow_items
- Artifacts panel (already exists in Build queue tab) shows results with status
- Tools to expose: all 8 tour steps + concept_search, docstring_health,
  check_design_violations, ingest_design_docs, extract_design_facts, gap_analysis

**Where to start:**
1. Read TRACKER.md RM28 for Workbench spec
2. Read Build queue tab HTML (panel-build_queue, around line 395 of console.html)
3. Read arLoad() and get_artifacts socket handler to understand existing artifact flow
4. Decide: new Workbench tab vs. sub-panel in Build queue tab

**Key constraint:** Workbench should feed artifacts into the existing Artifacts
sub-panel in Build queue. Don't duplicate artifact storage.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [V]:** Clear design_notes + semantic_summaries
  before a clean demo. Structural facts (entry, hot, dead) are valid, keep them.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**Tour on non-seed corpus [V]:** Shows corpus hint banner; runs tools against whatever
  corpus is loaded (explanations are Commonplace-specific but output is real).
