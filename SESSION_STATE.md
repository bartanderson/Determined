# SESSION STATE - session 33 handoff
_Overwrite completely each session. Not authoritative - see Determined/docs/TRACKER.md for truth._

## What happened this session (session 33)

**knowledge.db eliminated. One corpus DB owns everything.**

**Commits this session (6 total, all on main):**

**SOTS baked as JSON (earlier work carried in):**
- sots_tenets.json: all 25 SOTS tenets bundled in determined/data/
- sots_loader.py: load_tenets(), search_tenets() with embedding cosine search
- design_frame, check_design_violations, goal_intake, project_status arch flags
  all wired to sots_loader -- no longer need knowledge.db

**semantic_summaries to corpus DB (earlier work):**
- distilled column added to semantic_summaries in corpus DB
- assessor.semantic_summary() always uses oracle.conn (never knowledge_conn)
- project_status warns when semantic_summaries absent (SOTS XVIII)
- distill_corpus() rewrites to use corpus_conn directly

**DB naming fix (earlier work):**
- local_agent._ingest_source: C_Users_bartl_dev_harrow.db (not harrow_corpus.db)

**knowledge.db complete removal (b63b2b6 -- this session):**
- persistence_engine.initialize_database: adds knowledge_artifacts, workflow_items,
  bags, bag_items to every new corpus DB
- Assessor.__init__: removed KnowledgeOracle auto-init; _knowledge_conn now
  returns oracle.conn; bags wired to oracle.conn
- corpus_key derived from os.path.basename(oracle.db_path) not KnowledgeOracle
- knowledge_oracle.py deleted
- knowledge.db deleted from disk
- ui_server.py: stale "knowledge.db" comment updated
- agent_tools.py: stale "into knowledge.db" message updated; knowledge_status
  no longer needs knowledge_conn check
- 304 regression tests pass (1 pre-existing Windows file-handle cleanup failure
  in test_intent_layer_ab, unrelated)

## FIRST THING NEXT SESSION

Pick from TRACKER.md open items. Candidates in priority order:
- Item 6 (live sync loop - incremental re-ingest)
- Item 1 (files.role not populated)
- Item 7 (contracts decision: wire or delete)
- Item 2 (search_symbols only finds 2 results for 'game_state')

Per CLAUDE.md: read docs/sots.md before planning.

## Current state

Branch: main (Determined), 6 commits ahead of origin (NOT pushed this session)
Tests: 304 pass, 1 pre-existing Windows cleanup failure
Items done: 22, 23, 24, 25, 8, 14, 15, 9, 10, 19, knowledge.db elimination
No active in-progress work
knowledge.db: GONE. Corpus DBs own everything.
Corpus DBs: C_Users_bartl_dev_Determined.db, C_Users_bartl_dev_dj2.db,
            C_Users_bartl_dev_harrow.db (re-ingest required to get new tables)

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, separate venv
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Use PowerShell tool (not Bash) for all server/Python commands.
Active branch: main (Determined)
