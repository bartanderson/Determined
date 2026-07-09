Written at commit: 4abb452
# SESSION STATE - session 128 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 128, 2026-07-09)

**GETTING_STARTED.md -- COMPLETE [V]**
- Phase 2 walk: added utils/text.py and utils/url.py to seed, re-analyzed, observed
- Actual Frontier → Orphan (25-file seed): 5 anticipatory (validate_entry, make_excerpt,
  normalize, validate, to_dict). validate_url missing -- duplicate symbol lesson.
- Phase 3 walk: loaded examples/commonplace (complete corpus), observed actuals:
  12 anticipatory orphans, 1 stub, 60 implemented, 1 direct-call in Implement Now queue
- Closing section written
- Committed 79eabb5

**Seed/ reverted to 17-file baseline [V]**
- models/, routes/api.py, routes/browse.py, utils/text.py, utils/url.py all removed
- Committed 4abb452

**LLM discovery removed from ingest path [V]**
- semantic_summary loop was blocking UI for minutes after every re-analyze
- Stripped discover_run loop from handle_reingest in ui_server.py
- Main UI (Frontier, Topology, Call tree, corpus panel) is pure graph -- no LLM needed
- "discover more" in Ask bar still available for manual run
- LLM fires on-demand via symbol spotlight
- 506 passed, 1 skipped [V]
- Committed bba5b3e

## Current state of seed/ [V]
17 files, original baseline. No additions staged.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.
**RM29 duplicate symbol detection [V]:** Not yet implemented. Filed session 127.

## NEXT SESSION -- start here

GETTING_STARTED.md is done. Active open items in TRACKER.md: RM29, RM28, RM21, RM20.

**Recommended next:** RM29 (duplicate symbol detection) -- small, self-contained SQL query +
surface in corpus panel and Orphan mode. Implementation sketch already in TRACKER.md.
Or RM28 (Three-mode UX) if Bart wants to go bigger.
