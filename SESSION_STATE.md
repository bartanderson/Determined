Written at commit: 626a2ed
# SESSION STATE - session 131 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 131, 2026-07-09)

**RM28 Stage 1: Guide toggle + localStorage scaffold + rail color dots -- DONE [V]**
- Added Guide toggle button to topbar (amber when on, neutral when off)
- Permanent dismiss: X button stores `det_guide_dismissed=1` in localStorage, toggle disappears
- Restore: tiny "Guide" link in sidebar panel footer clears flag and shows toggle again
- `.rail-dot` span added to each of the 4 rail icon buttons (corpus/navigate/tools/ask)
- `guideMarkVisited(key)` / `guideIsVisited(key)` -- localStorage `det:visited:<key>` pattern
- `guideUpdateDots()` -- sets dot color via inline `dot.style.background` (NOT CSS attr-selector;
  see HISTORY.md for the two traps hit this session)
- Stage 1 color grammar: unvisited=transparent, first-visit=green (one-action elements)
- Red/amber progression deferred to Stage 2 with guide card content
- Only `console.html` changed; no Python files touched
- 506 passed, 1 skipped [V] (confirmed this session)
- Committed 626a2ed [V]

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

**RM28 Stage 2** -- next thing to build.
- Guide card panel: appears below topbar when guide is on, keyed to (active_tab + corpus_phase)
- Content file: `determined/data/guide_commonplace.json`
  Shape: `{ "tab:frontier:skeleton": { "headline": "...", "body": "...", "what_to_notice": "..." }, ... }`
- Commonplace detection: key off `_db_path` containing "commonplace" (case-insensitive);
  serve flag from Python to JS (e.g. add to corpus_ready payload or a new socket event)
- Card updates as user clicks tabs / changes Frontier sub-mode (Direct/Orphan/ABC)
- No phase picker yet (Stage 3); for Stage 2 default phase = "skeleton"
- Files: `determined/ui/templates/console.html` (card HTML + JS),
         `determined/data/guide_commonplace.json` (content),
         `determined/ui/ui_server.py` (emit is_commonplace flag)
- Content source: `docs/COMMONPLACE_USER_JOURNEY.md` -- distill each phase/tab into card text

**RM20** (~1 hour, good warmup if Stage 2 feels large)
- File: `determined/agent/doc_extractor.py` -- store step inside `ingest_design_docs`
- Embed candidate rule; skip if cosine similarity >= 0.85 to any existing design_note before INSERT
- Reuses `embed_text` from `determined/oracle/embedding_model.py`

**RM21** -- build only after Technique 1 proves insufficient on real multi-hop queries.
