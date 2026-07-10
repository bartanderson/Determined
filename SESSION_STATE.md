Written at commit: 9f342fa
# SESSION STATE - session 135 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 135, 2026-07-10)

**RM31: agent routing fixes -- DONE [V]**
- Committed 9f342fa
- Fix 1 (blast-radius): "what would break if X were removed?" was matching
  `corpus_synthesis` via its `what would break` regex. Added two `blast_radius`
  detection rules in `_DETECT_RULES` (before corpus_synthesis). Removed
  `what would break` from corpus_synthesis regex.
  New `blast_radius` tool in `agent_tools.py`: file target → enumerate symbols,
  list callers of each; symbol target → callers + risk badge + subgraph.
  TASK_PATTERN + REGISTRY entry added.
- Fix 2 (traversal): "path from the api to the database" grabbed "the" instead
  of "api" because `(\S+)` doesn't skip articles. Fixed `trace_data_flow` regex
  in `_DETECT_RULES` to add optional article skip before source and dest.
- 5 new tests in test_pattern_executor.py; TOOLS set and REGISTRY coverage test
  updated. 511 passed, 1 skipped. [V]

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

Active open items in priority order: RM32, RM33, RM34 (deferred), RM28 Stage 5 (deferred), RM29, RM30.

**RM32** -- next thing to build. Fact assembly fix in `agent_resolver.py`.
  When two or more symbols share a name (e.g. `search` in api.py, search.py,
  searcher.py), the facts block labels all of them identically and the model
  collapses them into one symbol.
  Fix: in `resolve_and_expand` or `facts_to_text` in `agent_resolver.py`,
  tag every symbol in the facts text with its file: "search (api.py)" not "search".
  Grounding already finds the file -- it just doesn't carry through to facts text.
  Entry point: `determined/agent/agent_resolver.py` -- `resolve_and_expand` (line ~1246)
  and `facts_to_text` (line ~1332).

**RM33** -- ASSEMBLE prompt fix. In `_assembly_hint()` in `local_agent.py`: detect
  comparative/boolean question shapes and inject a synthesis instruction.

**RM34** -- deferred. Do after RM31-33.
