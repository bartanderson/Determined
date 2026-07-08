Written at commit: c2a37e0
# SESSION STATE - session 110 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 110, 2026-07-07)

**dj2 TRACKER additions [V]:** Two items filed in `C:\Users\bartl\dev\dj2\TRACKER.md`:
- G10: Verb registry -- actions as first-class entities
- G11: Semantic sensor layer -- DFA pattern detection over event stream
Both stem from Ragel/beagle-ext discussion. Core idea: LLM translates messy
player speech → semantic tokens; DFAs recognize multi-event patterns → higher-level facts.

**RM15 Walk 2 complete (Steps 2-7) [V]:** Full guided journey loop executed
against the Commonplace seed corpus. All 6 steps committed:
- Step 2 (a0a090e): EnrichmentProcessor.can_handle + process implemented. ABC-interface 2→0.
- Step 3 (c21d8b6): search_bp registered in create_app; route calls semantic_search. Orphaned-impl 2→1.
- Step 4 (4aaa3f0): DESIGN.md ingested (10 rules). check_design_violations flagged
  searcher service-layer bypass at 0.61. reason_about recommended keeping extractor.py
  unified (SOTS: minimize indirection, 95%). Noise finding: duplicate PERMISSION rules.
- Step 5 (523c168): utils/validator.py added with conditional stub (validate_entry,
  if strict: raise NotImplementedError). capture.py wires validate_url(). find_conditional_stubs fires.
- Step 6 (4c0d0b0): Documented what conditional stubs teach vs detect_topology.
  reason_about recommended removing strict branch (95%, 0 callers, SOTS-grounded).
- Step 7 (c2a37e0): Removed strict branch. Reingested. find_conditional_stubs → 0.

**Seed corpus final state [V]:** 0 stubs, 0 ABC gaps, 0 conditional stubs,
1 known-false orphan (init_db -- Flask app-context call invisible to static analysis).
31 implemented functions. All topology shapes exercised across the walk.

**Determined gap found during Step 4 [V]:**
Duplicate design_note entries: deterministic + LLM extraction passes both store the
same rule. Deduplication uses 60-char prefix match -- insufficient when LLM rephrases.
Filed in COMMONPLACE_JOURNEY.md under "noise finding." Not yet filed as TRACKER item.

## NEXT SESSION -- start here

Read step_queue.md first: CURRENT is Step 8.

**RM15 Step 8:** Walk 2 wrap-up.
- Assess what the journey taught: which Determined outputs were high-signal vs noisy
- File any Determined gaps discovered as TRACKER items (duplicate rule noise is one)
- Update COMMONPLACE_JOURNEY.md WHAT WORKS section with Walk 2 verified capabilities
- Decide: continue to "complete" state (add browse route, models, storage queries)
  or pivot to other RM15 work

**After Step 8:** The seed journey is functionally complete. The natural next arc is
either:
1. Build the "complete" Commonplace state (adds browse, models, connections schema)
   to exercise chain shapes and more topology variety
2. Start RM19 Pass 3 filter improvement (cross-reference primitive_gap callees against
   symbols table to exclude constructors/stdlib, ~30 min, agent_tools.py:4642)

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** oracle.get_project_root() returns
seed/, not examples/commonplace/. DESIGN.md lives outside seed root -- must call
discover_docs + extract_rules directly with the correct path. Workaround confirmed
working in Step 4 (10 rules ingested via manual script).

**UI Re-analyze+ does NOT use reingest_file [V]:** Runs background discover_run thread.
Workaround: call reingest_file() from Python CLI directly.

**Duplicate design_note extraction [V]:** LLM pass re-extracts rules the deterministic
pass already found. 60-char prefix dedup insufficient when LLM rephrases. Results in
PERMISSION-prefixed duplicates in check_design_violations output. Not yet filed as item.

**primitive_gap noise [V]:** Constructors/stdlib pass bare-name filter. Fix deferred
to RM19 Pass 3.

**frontier_priority doesn't incorporate ABC gaps [?]:** Shows "no stubs" even when
ABC-interface count > 0. Not re-verified this session.

**Test count: 481 passed, 1 skipped, 18 deselected [?]** (not re-run this session --
no Determined engine files changed, only seed corpus files touched)
