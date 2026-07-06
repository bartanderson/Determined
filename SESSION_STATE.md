# SESSION STATE - session 90 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main
All changes committed. Tests passing at 436/1 skip.

## What happened this session (session 90, 2026-07-05)

1. RM17 executed: two-pass cold analysis of Commonplace full corpus.
2. 10 gaps ranked, filed as docs/RM17_findings.md.
3. Late correction: Gap 1 and Gap 10 are largely test artifacts.

## Key correction (end of session)

The full Commonplace DB was ingested BEFORE commit a7dc167 ("F2: wire
ingest_design_docs into post-ingest pass"). So the DB has 0 design notes
not because the tool can't do it, but because the DB is stale.

ingest_design_docs DOES run automatically during the analyze flow (ui_server.py
line 538). It does NOT run on load_db (switching to an already-built corpus).

Gap 1 finding ("violations invisible") and Gap 10 ("no auto-discovery") are
both overstated. The tool already auto-ingests design docs on analyze.

## NEXT SESSION -- start here (RM18)

1. Re-ingest the full Commonplace corpus (Analyze button in UI) so
   ingest_design_docs runs and populates the knowledge tab.
2. Re-check violation detection on capture() and browse.py routes.
3. See what actually surfaces before building new features.
4. Then: Gap 2 (Flask @route = entry_point heuristic) is still valid and easy.

## Test count: 436 passed, 1 skipped
