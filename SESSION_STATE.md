Written at commit: 431c5eb (Determined)
# SESSION STATE - session 117 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 117, 2026-07-08)

**RM23: Phase 3 extras walk -- DONE [V]**
- Detected DB stale (3 Walk 4 files newer than DB): reingested linker.py, searcher.py, search.py
- Ran knowledge_status, find_abc_gaps, frontier_coverage, find_orphaned_impls,
  check_design_violations on complete Commonplace corpus (25 files, 64 functions)
- Actuals: 0 stubs, 0 ABC gaps, 16 anticipatory orphans, knowledge layer empty (correct)
- Phase 3 section of COMMONPLACE_USER_JOURNEY.md updated with tool outputs [V]
- step_queue.md corrected (session 116 claimed advancement but file was never written -- caught hallucination)
- TRACKER RM23 marked DONE [V]
- Committed: 65ef660 [V]

**RM27: GRASP vocabulary -- DONE [V]**
- Created determined/data/grasp_principles.json: 9 GRASP principles (Larman),
  each with violation_signal and ask fields for detection use [V]
- Created determined/data/grasp_loader.py: mirrors sots_loader.py pattern,
  load_principles() / principle_texts() / search_principles() [V]
- Wired into _check_design_violations_core alongside SOTS tenets:
  extra_items now = tenet_texts() + principle_texts() [V]
- Added GRASP label regex in results loop: [GRASP-N] -> "GRASP-N" subject [V]
- Updated "no violations" message to mention GRASP count [V]
- Live test: GRASP-9 Protected Variations surfaced on check_design_violations
  itself (score 0.33) against Determined corpus [V]
- 481 passed, 1 skipped [V]
- Committed: 431c5eb [V]

**Confirmed: RM20 (design_note dedup) not needed [?]**
Bart noted no duplicates occur in practice on the Determined corpus.
Not verified independently -- flagged [?].

## NEXT SESSION -- start here

**RM21: Verification loops (Technique 1)**
Model generates a claim -> Determined checks against DB -> if wrong, feeds
correction back -> model revises. No new infrastructure; pure tool-call pattern
on top of existing evaluate() + agent_tools.

**Why this is next:** RM27 is done, which was the prerequisite -- richer correction
language (GRASP + SOTS) makes the loop more useful from the start.

**Design note (from session discussion):**
- RM27 feeds RM21: corrections now carry named principles, not just contradictions
- RM21 stress-tests RM27: loop exposes which GRASP vocabulary is missing or unused
- Build Technique 1 first; Techniques 2-5 only if 1 proves insufficient

**Where to implement:** determined/agent/evaluator.py (evaluate() function) +
determined/agent/local_agent.py (the agentic loop). The verify step sits between
evaluate() returning a judgment and the caller acting on it.

**TRACKER.md RM21 entry:** still marked [FUTURE], condition was "after RM15 done."
RM15 is now done. Update status to ACTIVE when starting.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**UI Re-analyze does NOT use reingest_file [V]:** Workaround: call from Python CLI.
**Duplicate design_note extraction [?]:** RM20 -- Bart says no duplicates in practice; not re-verified.
**primitive_gap noise [V]:** Fix is RM19 Pass 3.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = gap reported even if override exists.
**GRASP threshold:** principles surface at 0.30 same as SOTS. May need tuning once
  we see real usage -- thin docstrings won't reach threshold (observed on Commonplace).
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
