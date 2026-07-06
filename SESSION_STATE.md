# SESSION STATE - session 92 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main
All changes committed (3f61ab9). Tests passing at 436/1 skip.

## What happened this session (session 92, 2026-07-06)

1. Re-analyze button: always visible in corpus panel, labeled "Re-analyze" when
   corpus loaded, pre-fills path from _source_path. Fixes dead end where a loaded
   corpus had no way to re-run ingest_design_docs without knowing to use Python.

2. decorators_json: capture all function decorators at ingest. Orphan query now
   filters out any function with a non-structural decorator. Eliminates false-positive
   orphans from @app.route, @socketio.on, etc. Grows automatically with new frameworks.

3. Re-ingested Commonplace with new code. Orphan (disconnected) view now shows 0
   nodes -- all 17 Flask route handlers correctly excluded. Gap 2 fixed.

4. GAPS sidebar now shows 25 design notes (was 0) -- Gap 1/10 confirmed fixed by
   re-ingest triggering ingest_design_docs automatically.

5. Saved memory: Ask bar is NL query only, not a tool dispatcher.

## Key correction from RM17

Gap 1 and Gap 10 were stale-DB artifacts, not tool gaps. Both confirmed fixed
after re-ingest. 25 design notes now in corpus.

## NEXT SESSION -- start here (RM18 continued)

1. Gap 1 re-check: run check_design_violations on `capture` and browse.py routes
   now that 25 design notes are populated. Zero code -- just a query. Tells us
   whether the design note extractor produces useful violations or needs tuning.
   Use the Chat/Ask bar with natural language: "check design violations for capture"
   OR use the Design button (top right) which fires check_design_violations directly.

2. Gap 3: _call_llm ranked #2 root but is dead code. Need "ready but blocked" vs
   true orphan distinction. New node role in orphan view.

3. Gap 4: capture role = INTERFACER (wrong). Should be COORDINATOR/CONTROLLER.
   Fix in infer_behavior Wirfs-Brock role patterns.

## Test count: 436 passed, 1 skipped
