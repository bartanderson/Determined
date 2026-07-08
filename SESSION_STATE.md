Written at commit: 837d185
# SESSION STATE - session 111 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 111, 2026-07-07)

**RM15 Step 8: Walk 2 wrap-up [V]** (commit 837d185)
- COMMONPLACE_JOURNEY.md WHAT WORKS section expanded with Walk 2 verified capabilities
  and signal calibration (check_design_violations actionable at 0.45+, noisy at 0.30-0.40)
- Step 7 section added (strict branch removed, find_conditional_stubs -> 0)
- Step 8 wrap-up section added (high-signal vs noisy assessment, next arc options)
- TRACKER.md dashboard updated

**RM20 filed [V]:** design_note deduplication via embedding similarity.
- LLM extraction pass re-extracts rules deterministic pass already stored.
- 60-char prefix match insufficient when LLM rephrases.
- Recommended fix: embed each candidate at store time, skip if cosine >= 0.85
  to any existing design_note. ~1 hour, no schema change.
- Location: `determined/agent/doc_extractor.py` store step inside `ingest_design_docs`.

## Walk 2 final state [V]

Seed corpus: 0 stubs, 0 ABC gaps, 0 conditional stubs, 1 known-false orphan (init_db).
31 implemented functions. All four gap shapes exercised:
- ABC-interface: detect -> implement override -> reingest -> 0
- Orphaned-impl: detect -> wire caller -> reingest -> count drops
- Design violations: ingest DESIGN.md -> check -> reason_about decision
- Conditional stub: find_conditional_stubs -> reason_about -> remove branch -> 0

## Signal calibration (Walk 2 verified) [V]

High-signal:
- find_abc_gaps: no false positives on seed
- find_conditional_stubs: fires correctly, clears correctly
- check_design_violations at >= 0.45: real matches
- reason_about: recommendations correct, SOTS grounding adds real weight

Noisy (calibrate before trusting):
- check_design_violations at 0.30-0.40: cross-symbol contamination common
- Duplicate design_note entries inflate violation count (RM20 fix pending)
- Static-analysis orphan false positives: Flask app_context, aliased imports

## NEXT SESSION -- start here

Read step_queue.md: CURRENT is TBD (next arc decision needed).

**Next arc options (decide before coding):**
1. Build Commonplace "complete" state -- add browse route, Entry/Tag models,
   storage queries. Exercises chain shapes, richer topology, call graph variety.
   Purpose: stress-test Determined against a fuller codebase, find more gaps.
2. RM19 Pass 3 filter improvement -- cross-reference primitive_gap callees against
   symbols table to exclude constructors/stdlib (~30 min, agent_tools.py:4642).
   Purpose: reduce noise in existing tool, quick win.
3. RM20 -- implement design_note dedup via embedding similarity (~1 hour,
   doc_extractor.py). Purpose: fix a confirmed noise source found during Walk 2.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** oracle.get_project_root() returns
seed/, not examples/commonplace/. DESIGN.md lives outside seed root -- must call
discover_docs + extract_rules directly with the correct path.

**UI Re-analyze+ does NOT use reingest_file [V]:** Runs background discover_run thread.
Workaround: call reingest_file() from Python CLI directly.

**Duplicate design_note extraction [V]:** Filed as RM20. Not yet fixed.

**primitive_gap noise [V]:** Constructors/stdlib pass bare-name filter. Fix is RM19 Pass 3.

**frontier_priority doesn't incorporate ABC gaps [?]:** Not re-verified this session.

**Test count: 481 passed, 1 skipped [?]** (not re-run this session -- no engine files changed)
