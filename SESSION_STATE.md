Written at commit: a502d83
# SESSION STATE - session 136 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 136, 2026-07-10)

**RM32: fact assembly name-collision fix -- DONE [V]**
- Committed a502d83
- Problem: `symbol_context` picked `sym_rows[0]` and used header `=== symbol_context: search ===`
  with no file qualifier. When 3 files each have a "search" function, the model saw 3 identical
  headers and collapsed them into one symbol.
- `list_callers` returned callers of all "search" definitions merged, with no note.
- Fix 1 (`symbol_context` in agent_tools.py):
  - Header now includes file: `=== symbol_context: search (api.py) ===` for single file,
    or `=== symbol_context: search (defined in 3 files: api.py, search.py, searcher.py) ===`
    for multi-file.
  - `[DECLARATION]` block now shows ALL file declarations, each tagged with short filename.
  - `[DOCSTRING]` shows per-file docstrings when multiple definitions exist.
- Fix 2 (`list_callers` in agent_tools.py):
  - Multi-file check moved before the no-callers early return.
  - When multiple definitions: header says `[NOTE: 'search' is defined in 3 files (...) - callers of all definitions combined]:`
  - When no callers + multiple files: no-callers message also includes the NOTE.
  - Single-file case: header includes file tag `Direct callers of 'search' (api.py):`.
- 5 new tests in test_agent_tools.py; 516 passed, 1 skipped. [V]

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

Active open items in priority order: RM33, RM34 (deferred), RM28 Stage 5 (deferred), RM29, RM30.

**RM33** -- next thing to build. Synthesis gap in `_assembly_hint()` in `local_agent.py`.
  When the question is comparative/boolean ("is there any function that does both X and Y?",
  "which X has both Y and Z?"), the model summarizes facts rather than cross-referencing them.
  The ASSEMBLE prompt says "answer using ONLY the facts below" but doesn't steer toward
  comparison reasoning.
  Fix: detect comparative/boolean question shapes in `_assembly_hint()` and inject a
  synthesis instruction: "Compare the behaviors of the symbols above. Answer YES/NO first,
  then name the specific symbol if YES."
  Entry point: `determined/agent/local_agent.py` -- `_assembly_hint()`.

**RM34** -- deferred. Method confabulation via claim_verifier extension. Do after RM33.
