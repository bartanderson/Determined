Written at commit: fc0e843
# SESSION STATE - session 137 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 137, 2026-07-10)

**RM33: comparative synthesis hint in _assembly_hint() -- DONE [V]**
- Committed fc0e843
- Problem: when question asks "is there any function that does both X and Y?",
  the model summarizes facts individually instead of cross-referencing them.
- Fix: added `_COMPARATIVE_RE` regex to `local_agent.py` (module level) that
  detects multi-condition question shapes (requires explicit conjunction: and/both,
  or also+and).
- Threaded `question` param into `_assembly_hint(needs, question="")` and
  `_assemble_prompt` now passes `question` to it.
- When matched, injects: "Cross-reference the facts above to find symbols that
  satisfy ALL stated conditions. Answer YES or NO first. If YES, name the
  specific symbol(s) and cite which facts support each condition."
- 5 new tests in test_local_agent.py (12 total in that file). 522 passed, 1 skipped. [V]

## Known issues (carried forward)

**GUIDE_DATA sync trap [V]:** `guide_commonplace.json` and inline `GUIDE_DATA` in console.html
are separate stores -- both must be updated together when adding card content. No auto-sync.
**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.

## NEXT SESSION -- start here

Active open items in priority order: RM34 (deferred), RM28 Stage 5 (deferred), RM29, RM30.

**RM34** -- next. Method confabulation via claim_verifier extension.
  The claim_verifier (RM21 Technique 1) currently checks CALLS/NO_CALLERS claims.
  RM34: extend to also catch method confabulation -- when the model claims a method
  exists on a class that doesn't have it.
  Entry point: `determined/agent/claim_verifier.py`.

**RM29** -- duplicate symbol detection / surfacing. Two functions with the same name
  in different files appear as two graph nodes; nothing says WHY one appears as orphan.
  See HISTORY.md entry 2026-07-09.

**RM30** -- (check TRACKER.md for details).
