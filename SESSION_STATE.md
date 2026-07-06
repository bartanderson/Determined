# SESSION STATE - session 90 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main
All changes committed (pending this session's commit). Tests passing at 436/1 skip.

## What happened this session (session 90, 2026-07-05)

1. RM17 executed: two-pass cold analysis of Commonplace full corpus.
   - Pass 1: loaded full corpus via JS socket.emit workaround (corpus picker bug discovered),
     walked orient → frontier (Direct + ABC mode) → topology → knowledge → spotlight on
     capture and _call_llm. All tool output recorded to scratchpad BEFORE reading source.
   - Pass 2: read actual source files (routes/capture.py, services/processor.py, pipeline.py,
     tagger.py, linker.py, searcher.py, extractor.py, models/, docs/DESIGN.md, app.py, browse.py).
   - Gap analysis: 10 gaps ranked, filed as docs/RM17_findings.md.

2. TRACKER.md updated: RM17 marked DONE with summary. RM18 filed as next.

3. HISTORY.md updated: 3 non-obvious findings added.

## Key RM17 findings (top 3)

**Gap 2 (HIGH, easy fix):** Flask @route decorator = entry point, not orphan.
17 of 18 "orphaned-impl" are route handlers. Fix: detect @*.route() at ingest time,
classify as entry_point role.

**Gap 1 (HIGH, medium):** Layer-import violations invisible without design doc ingest
+ structured layer rules. 4+ planted violations (routes calling storage directly) went
completely undetected. Root: Knowledge tab = 0 artifacts. Even with ingest, cosine-
similarity isn't enough -- need explicit import-path rule type.

**Gap 10 (MEDIUM, easy):** DESIGN.md auto-discovery. Corpus was built FOR Determined's
violation detection; DESIGN.md says "Ingest with ingest_design_docs." But the tool
never prompts. Auto-run discover_docs on corpus load and surface the result.

## NEXT SESSION -- start here (RM18)

**Act on RM17 gaps. Priority order:**

1. **Gap 2: Flask entry-point heuristic (easy, high value)**
   - In `parse_ast.py` `_classify_role()` or `_extract_functions`:
     detect functions decorated with `@<name>.route(...)` and set role="entry_point"
   - Verify: re-ingest Commonplace, check capture(), index(), entry_detail() no longer
     appear as orphaned-impl in topology
   - Expected: orphaned count drops from 18 to ~2-3

2. **Gap 10: Auto-discover design docs on corpus load (easy, high value)**
   - In ui_server.py after corpus load: call discover_docs, if markdown with constraint
     density found, emit a notice ("Found design docs -- run ingest_design_docs")
   - Or: surface discover_docs result in corpus map gap section

3. **Gap 1: Structured layer-rule violations (medium, after 1+2)**
   - New knowledge_artifact kind=layer_rule with from_layer/to_layer/forbidden fields
   - Query: for each symbol in routes/, find imports from storage/ -- flag as violation
   - Requires design docs ingested first

## Changes uncommitted this session
- docs/RM17_findings.md (new)
- docs/TRACKER.md (RM17 DONE, RM18 filed)
- docs/HISTORY.md (3 entries)
- .claude/step_queue.md (updated)
- SESSION_STATE.md (this file)

## Corpus switch bug discovered
The "Switch corpus" picker rows didn't respond to clicks reliably (CDP timeout during
screenshot). Workaround: socket.emit('load_db', {path: full_absolute_path}).
Root cause unclear -- low priority, not filed.

## Test count: 436 passed, 1 skipped
