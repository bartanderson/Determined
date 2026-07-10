Written at commit: da81931
# SESSION STATE - session 137 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 137, 2026-07-10)

**RM33: comparative synthesis hint in _assembly_hint() -- DONE [V]**
- Committed fc0e843
- Added `_COMPARATIVE_RE` regex to `local_agent.py` (module level).
  Detects multi-condition question shapes ("is there any function that does X and Y?",
  "which function has both X and Y?"). Requires explicit conjunction (and/both, or also+and).
- Threaded `question` param into `_assembly_hint(needs, question="")`.
- When matched, ASSEMBLE prompt says: answer YES/NO first, name symbols, cite facts.
- 5 new tests in test_local_agent.py. [V]

**RM34: method confabulation detection in claim_verifier -- DONE [V]**
- Committed da81931
- Added `HAS_METHOD` claim kind to `claim_verifier.py`.
- 4 regex patterns detect "X has a Y method", "X.Y()", "class X implements Y", "X's Y method".
- `verify_claim` queries `classes.methods_json`, emits correction if method absent.
  Unknown classes silently skipped (can't refute what's not in DB).
- 7 new tests in test_claim_verifier.py; 529 passed, 1 skipped. [V]

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

Active open items: RM28 Stage 5 (deferred), RM29, RM30.

**RM29** -- duplicate symbol detection / surfacing. Two functions with the same name
  in different files appear as two graph nodes; nothing says WHY one appears as orphan.
  See HISTORY.md entry 2026-07-09.
  Entry point: TBD -- likely agent_tools.py or a new tool.

**RM30** -- (check TRACKER.md for details).
