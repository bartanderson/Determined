Written at commit: bd39950
# SESSION STATE - session 127 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 127, 2026-07-09)

**GETTING_STARTED.md rewrite -- in progress [V]**
- Full rewrite of Phase 1 (skeleton walk) with peer-hacker voice
- Covers: corpus panel, Frontier (Direct/Orphan/ABC), Topology, Call tree, seed structure
- Phase 2 started: models layer + routes layer additions with actual observations
- Key lessons captured in doc:
  - Determined finds stubs, not missing symbols
  - Orphan mode reveals design intent ahead of wiring
  - Call graph built from imports/calls, not intent
  - Duplicate symbols: genuine gap in the tool (filed RM29)
- Dropped noseed/Terminal 0 concept -- skeleton is the right starting point
- Core framing established: comprehension tool, not a linter; "what was this trying to become?"

**Re-analyze UX fixes [V]**
- WinError 32: clear tables in place instead of deleting DB (Defender/Search holds file)
- Re-analyze now skips Load/Re-analyze modal -- goes straight to ingest
- Discovery batch size 20→5 for more frequent progress updates
- WAL/SHM sidecars cleaned on re-analyze

**seed/ additions [V]**
- examples/commonplace/seed/models/ -- Entry, Connection, Tag dataclasses
- examples/commonplace/seed/routes/api.py and browse.py -- new route layer

**RM29 filed [V]**
- Duplicate symbol detection: automatic and prominent when found
- SQL sketch: SELECT name, COUNT(DISTINCT file_path) FROM functions GROUP BY name HAVING COUNT > 1

**Memory updated [V]**
- project_getting_started_intent.md: voice guidance, Phase 2 file order, comprehension framing,
  no-manufacturing-stubs rule all captured

## Current state of seed/

23 files total when analyzed. Orphan mode shows: validate_entry, validate, to_dict (3 anticipatory).

**Still to add for Phase 2 walk:**
- utils/text.py (truncate, clean, make_excerpt helpers)
- utils/url.py (normalize, validate_url -- NOTE: duplicate of validator.py::validate_url, intentional lesson)

After utils walk, revert seed/ additions with git clean + git checkout.

## NEXT SESSION -- start here

**Primary task: finish GETTING_STARTED.md**

Phase 2 walk remaining:
1. Add utils/text.py and utils/url.py to seed → re-analyze → observe orphans + duplicate validate_url
2. Write that section with the duplicate symbol lesson
3. Revert seed/ to original state with git
4. Write Phase 3: complete corpus (examples/commonplace) -- load it, walk Frontier/Topology
5. Write closing section

Rules in force (see memory/project_getting_started_intent.md):
- Peer-hacker voice: explain why, not what
- Each control transition must name what previous couldn't tell you
- Do NOT manufacture stubs to force demo results
- Do NOT load finished corpus and describe it -- live through the walk
- Bart walks in browser, doc written from actual observations

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [V]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.
**RM29 duplicate symbol detection [V]:** Not yet implemented. Filed this session.
