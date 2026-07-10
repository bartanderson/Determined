Written at commit: 588d0b0
# SESSION STATE - session 139 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 139, 2026-07-10)

**RM28 Stage 5: general guide layer for non-Commonplace corpora -- DONE [V]**
- Committed 588d0b0
- Created `determined/data/guide_general.json` -- 13 entries keyed by tab or tab:mode
  (chat, call_tree, graph, imports, frontier, frontier:direct, frontier:orphan,
  frontier:abc, bag, editor, dochealth, knowledge, build_queue).
  Each entry: headline, body, what_to_notice.
- Modified `guideUpdateCard()` in console.html to branch on `_isCommonplace`:
  - Non-Commonplace path: uses GUIDE_GENERAL (inline JS object mirroring the JSON),
    key = tab or tab:mode only, hides phase picker row.
  - Commonplace path: unchanged (uses GUIDE_DATA, key = tab:mode:phase, shows phase row).
- Browser-verified against Determined corpus: Knowledge tab showed correct card.
  Phase picker row hidden. Card switches correctly on tab change.

**RM21 probe against Determined corpus -- 3 pass, 2 partial, 1 improved [V]**
- Q1: PARTIAL -- describes ui_server.py correctly but says "ML platform" (stale
  semantic summary in DB -- data issue, not engine bug)
- Q2: PASS -- correctly identifies run_question and _answer as dependents
- Q3: PASS -- correct
- Q4: PARTIAL -- correctly uncertain given facts don't show import relationships
  (structural gap, not engine bug)
- Q5: IMPROVED -- traces route_query -> run_query path; still uncertain on DB leg
- Q6: PASS -- lists all 30 DBOracle methods correctly

Four bugs found and fixed (committed 3052381):
- Q6 method confabulation: added tip to DECOMPOSE_SYSTEM in local_agent.py
  ("NEED: symbols in the_file.py" not "symbols named ClassName")
- Q2 blast-radius wrong symbol: pattern_executor.py detect rule added
  change[sd]/modif/refactor to optional verb group so "changed" is consumed
  before the symbol capture group
- Q2 blast-radius heuristic: agent_resolver.py _HEURISTICS past-tense verb forms added
- Q2 blast_radius TypeError: agent_tools.py blast_radius() -- set() cast before
  set subtraction (subgraph_around returns sorted list, not set)

Remaining gaps (not bugs -- structural/data limits):
- Q1: stale semantic summary for ui_server.py says "ML platform"; regenerate to fix
- Q4: import relationships not surfaced by current fact layer
- Q5: DB leg of route_query -> DB path not traced; graph may not have edge

**533 tests passed, 1 skipped [V]**

## Known issues (carried forward)

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and inline GUIDE_DATA in
console.html are separate stores -- both must be updated together. No auto-sync.
Same pattern applies to guide_general.json vs inline GUIDE_GENERAL.

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.

**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries
before clean demo.

**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI
for single file.

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

**Complete corpus DB path [V]:**
C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db

**topology tab missing from guide_general.json [?]:** guide_commonplace.json has a
"topology" entry; guide_general.json does not. Low urgency.

## NEXT SESSION -- start here

**RM21 Technique 1 arc is complete. RM28 all stages done.**

**True open items:**
- RM10 (FUTURE): DeRe-CoT recomposition pass in goal_intake.
- RM13 (FUTURE): Self-Harness -- mine adversarial traces into routing heuristics.
- RM21 Techniques 2-6: on hold, gated on Technique 1 proving insufficient.

**Best next move:** Run the Q&A pipeline against a fresh corpus (dj2 or harrow) to
surface the next real failure mode before building more. Or pick up dj2 game work.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
Started via UI (port 5050) or manually.
