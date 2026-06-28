# SESSION STATE - session 27/28 handoff
_Overwrite completely each session. Not authoritative - see Determined/docs/TRACKER.md for truth._

## What happened this session (session 27)

**Spring cleaning of docs + UI fixes + hot-symbols regression fixed.**

### Bug fixes
- Hot symbols query in `ui_server.py::_corpus_map_data()` was using a broken
  LIKE clause that inflated counts massively (6013x for "get"). Fixed to use
  the existing `most_connected()` from `graph_utils.py` which correctly
  filters builtins/externals by requiring a known project file_path.
  This was a regression introduced in session 26 - new code bypassed the
  authoritative implementation. Root cause saved to memory.

- Two JS errors crashing page on load:
  1. modal-overlay div placed after script block - null on getElementById.
     Fixed: moved div before the script tag.
  2. bagSelect TDZ error in bagFetch() firing before initialization.
     Fixed: lazy getElementById lookup inside the function.

### UI changes (ui/corpus-map branch)
- Corpus map panel moved from main content area into sidebar
- All popups converted to modal overlay
- Resume replaced with single context-sensitive button (Analyze / Switch corpus)
- Query bar hidden by default, Ask toggle in sidebar reveals it
- Removed empty-state placeholder text from results area

### Spring cleaning
Docs reduced from ~3400 lines to ~1500 lines active:
- docs/PRACTICES.md - NEW: Be a Good Engineer + Pre-Code Checklist + DO/DON'T rules
- docs/TRACKER.md - slimmed to Dashboard + items 19-25 only (228 lines, was 855)
- docs/DESIGN.md - slimmed to active sections 1-3, 6-8 (715 lines, was 1290)
- docs/EXPERIMENTS.md - redirect to archive (1 line)
- docs/archive/ - all closed items, done phases, superseded sections, closed trials
- Determined CLAUDE.md updated with pre-code checklist

## Current state

Branch: ui/corpus-map (Determined), not yet merged to main
Tests: 321/322 passing (1 pre-existing stale fixture failure, unrelated)
dj2 corpus: loaded and working (150 files, 132 hot, 47 stubs, 615 artifacts)

## FIRST THING NEXT SESSION

1. Restart the Determined server
2. Load dj2 corpus via Switch corpus modal
3. Verify corpus map sidebar shows meaningful Roots/Core (not builtins - fixed this session)
4. If verdict is good: merge ui/corpus-map to main (item 25)

## What is next (after corpus map verdict)

Item 22 - Design doc extraction
  Read dj2/docs/design/ (00A ARCHITECTURAL_CONSTITUTION.md first).
  Build extractor using 3B model to pull invariants/rules/boundaries into
  design_note artifacts. Output shape matches DESIGN_NOTES in mine_design_docs.py.
  PRE-CODE: grep graph_utils.py and agent_tools.py before writing anything.

Item 23 - Frame comparison
  In spotlight + risk_profile handlers, look up design_note artifacts matching
  the symbol's file/classname and include them in LLM context.
  Requires item 22 first.

Item 24 - Goal intake
  Developer states intent, tool assembles: design rules + hot/safe zones +
  relevant stubs + safe insertion point. Returns navigation plan.
  Requires items 22 + 23 first.

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, separate venv
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Active branch: ui/corpus-map (Determined)
