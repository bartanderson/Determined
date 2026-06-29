# SESSION STATE - session 35 handoff
_Overwrite completely each session. Not authoritative - see Determined/docs/TRACKER.md for truth._

## What happened this session (session 35)

**Item 6 done: incremental per-file re-ingest.**

- New file: `determined/ingestion/reingest_file.py`
  - `FileDelta` dataclass: in-memory scratchpad holding old/new symbol state and
    computed added/updated/removed/unchanged sets
  - `compute_file_delta()`: loads old symbols from DB, parses new state, diffs them
  - `apply_file_delta()`: inserts new symbol rows first, then runs persist_file_analysis,
    then deletes stale old symbol rows, then rebuilds outbound graph edges
  - `reingest_file()`: top-level entry; derives global_symbols from DB + fresh file scan
  - Inbound edges from other files that referenced removed symbols remain as honest
    dangling references until those callers are re-ingested
- Fixed `_insert_symbol` in persistence_engine.py: changed plain INSERT to INSERT OR IGNORE
  on canonical_id UNIQUE -- was a latent bug that would have failed on any re-ingest attempt
- Wired as agent tool `reingest_file(file_path)`, CLI `--reingest-file FILE`, and REGISTRY entry
- CLAUDE.md updated: stale knowledge.db section and work-arc section corrected
- 6 new regression tests; 283 pass, 1 pre-existing Windows flake

## FIRST THING NEXT SESSION

Pick from TRACKER.md open items. Recommended order:
- Item 20 (call graph accuracy - annotation exploitation) -- now unblocked (item 6 done)
- Item 1 (files.role) -- small, low risk

Per CLAUDE.md: read docs/sots.md before planning.

## Current state

Branch: main (Determined), committed (not pushed - Bart pushes)
Tests: 283 pass (+ 1 pre-existing Windows file-handle flake in test_intent_layer_ab.py)
Items done: 22, 23, 24, 25, 8, 14, 15, 9, 10, 19, knowledge.db elimination, 7, 6
Item 20 planned and in TRACKER, not started

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, separate venv
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Use PowerShell tool (not Bash) for all server/Python commands.
Active branch: main (Determined)
