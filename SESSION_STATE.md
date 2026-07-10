Written at commit: 287f0ce
# SESSION STATE - session 130 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 130, 2026-07-09)

**RM30: filter class methods from duplicate name count -- DONE [V]**
- Changed dupe query in `determined/ui/ui_server.py` `_corpus_status()` to add
  `WHERE class_name IS NULL` -- only module-level functions count as real duplicates.
- 506 passed, 1 skipped [V]
- Committed ac746b7

**RM28: full design agreed and documented [V]**
- Old "three-mode UX" concept replaced with "training mode" design.
- Full spec written into TRACKER.md RM28 entry (committed 287f0ce).
- Core decisions (all agreed with Bart):
  - Small toggle in header, permanent dismissal via X to localStorage flag,
    restorable via tiny "Guide" footer link (no manual localStorage deletion)
  - Adaptive guide: no mode choice, guide watches what user does and surfaces
    contextual card keyed to (active_tab + active_mode + corpus_phase)
  - Color grammar on UI elements: no color=unvisited, red=<half explored,
    amber=half+ explored, green=fully explored; one-action elements skip red to green
  - Completion: all green -- auto-dismiss message -- toggle permanently disappears
  - Corpus phase picker (skeleton/complete/enhanced) + live code injection via
    reingest_file -- user watches metrics shift as implementations are added
  - Content in `determined/data/guide_commonplace.json` keyed by element+phase
  - General guide layer (non-Commonplace) deferred -- RM16 one-liners cover floor
  - Commonplace detection: `_db_path` contains "commonplace" (case-insensitive)
- Build order: Stage 1 (toggle+localStorage+color rail) -- Stage 2 (guide
  card+content JSON) -- Stage 3 (phase picker+injection) -- Stage 4 (completion) --
  Stage 5 (general guide, deferred)

## Current state of seed/ [V]
17 files, original baseline. No additions staged or tracked.

## Known issues (carried forward)

**ingest_design_docs project root mismatch [V]:** Must call with explicit path.
**Seed DB carries developer artifacts [?]:** Clear design_notes + semantic_summaries before clean demo.
**UI Re-analyze does NOT use reingest_file [V]:** Call reingest_file() from Python CLI for single file.
**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.
**Complete corpus DB path [V]:** C:\Users\bartl\dev\Determined\C_Users_bartl_dev_Determined_examples_commonplace.db
**LLM restart required after ctx-size change [V]:** --ctx-size 32768 only takes effect after full UI restart.

## NEXT SESSION -- start here

Active open items in TRACKER.md: RM28, RM21, RM20.

**RM28 Stage 1** -- first thing to build. Small, verifiable in browser.
- Add toggle to header in `determined/ui/templates/console.html`
- localStorage keys: `det_guide_dismissed` (permanent hide), `det:visited:<key>` (per element)
- Color indicators on tab rail icons (the 4-icon sidebar rail)
- No content yet -- just the scaffold and color grammar working in browser
- Files: `determined/ui/templates/console.html` + inline CSS/JS in same file

**RM20** (design_note dedup) -- ~1 hour, self-contained, good warmup if RM28 feels large.
- File: `determined/agent/doc_extractor.py` store step inside `ingest_design_docs`
- Check cosine similarity >= 0.85 to any existing design_note before INSERT

**RM21** (small-model reasoning Techniques 2-6) -- build only after Technique 1
proves insufficient on real multi-hop queries.
