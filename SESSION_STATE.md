Written at commit: 35dc19c
# SESSION STATE - session 132 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 132, 2026-07-10)

**RM28 Stage 2: Guide card panel + guide_commonplace.json content -- DONE [V]**
- Guide card (`#guide-card`) appears below topbar when guide is on + Commonplace corpus loaded
- Card keyed to `(active_tab + fg_mode + phase)`, updates on tab switch / fg-mode change
- `determined/data/guide_commonplace.json` created (13 tab keys, skeleton phase)
- Inline `GUIDE_DATA` JS object in console.html mirrors the JSON (two separate stores -- see HISTORY.md)
- `is_commonplace` flag added to `corpus_ready` payload (detects "commonplace" in `_db_path`)
- Committed bda6d29 [V]

**RM28 Stage 3: Corpus phase picker + phase switching -- DONE [V]**
- Phase picker pills (Skeleton / Complete) appear inside guide card when is_commonplace
- Active phase highlighted blue; pills disabled if companion DB not found on disk
- Clicking a pill emits `load_db` → corpus reloads → card updates to new phase content
- Server: `_corpus_phase()` (detects "seed" in DB name) + `_phase_dbs()` (computes companion paths)
- `corpus_phase` + `phase_dbs` added to `corpus_ready` payload
- Complete-phase content added to both JSON and inline JS (13 more keys, all tabs covered)
- Card key now uses `_activePhase` instead of hardcoded "skeleton"
- 506 passed, 1 skipped [V]
- Committed 35dc19c [V]

## Current state of seed/ [V]
17 files, original baseline. No additions staged or tracked.

## Known issues (carried forward)

**GUIDE_DATA sync trap [V]:** `guide_commonplace.json` and inline `GUIDE_DATA` in console.html are separate stores -- both must be updated together when adding card content. No auto-sync.
**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.

## NEXT SESSION -- start here

Active open items in TRACKER.md: RM28, RM21, RM20.

**RM28 Stage 4** -- next thing to build (~30 min).
- Completion state: when all colorable elements are green, guide card shows "You've explored
  everything. The guide will step back." then calls `guidePermanentDismiss()`.
- Requires counting total colorable elements vs. visited, detecting all-green state.
- File: `determined/ui/templates/console.html` only.

**RM28 Stage 5 (deferred)** -- general guide layer for non-Commonplace corpora.
- `guide_general.json` keyed to element only (no corpus phase). Build after Commonplace proves pattern.

**RM20** (~1 hour, good next after Stage 4)
- File: `determined/agent/doc_extractor.py` -- embed candidate rule at store time; skip INSERT
  if cosine similarity >= 0.85 to any existing design_note. Reuses `embed_text` from
  `determined/oracle/embedding_model.py`.

**RM21** -- build only after Technique 1 proves insufficient on real multi-hop queries.
