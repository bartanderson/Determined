Written at commit: 5df648b

# SESSION STATE — session 241

## Active branch: main [V]

## What happened this session

**RM71 FSM ingestor — fully implemented and committed.** [V]

**Drift found at session start [V]:**
- Two commits had landed since session 239's handoff (96158ae):
  - `9bcd7f7` — `knowledge_for_file` already shipped (option 1 from prior handoff)
  - `afe0b97` — RM71 design already written and committed (option 3)
- Both options from the prior "decide next" list were done before this session started.

**This session (single commit `5df648b`):**
- `determined/ingestion/fsm_walker.py` — new, 110 LOC [V]
  - `discover_fsm_files(root)` — `rglob("*.json")` filtered to paths with `"fsms"` in parts
  - `_parse_fsm(path)` — returns (fsm_name, symbols, transitions); raises ValueError on bad input
  - `ingest_fsm_file(path, conn, project_root)` — idempotent; deletes then re-inserts
  - `ingest_fsm_pass(conn, root)` — discovery wrapper; skips bad files with print
- `determined/engine/run_engine.py` — 3 lines added after `persist_all()` [V]
  - `from determined.ingestion.fsm_walker import ingest_fsm_pass; ingest_fsm_pass(connection, Path(corpus.root_path))`
- `tests/regression/test_fsm_walker.py` — 16 offline tests, all pass (0.14s) [V]
- `docs/TEST_MAP.md` — fsm_walker.py row added [V]
- `docs/TRACKER.md` — RM71 marked DONE 2026-07-22 [V]

**Schema used [V]:**
- States/events → `functions(is_stub=0)`, name = `FsmName::state::statename`
- Actions/guards → `functions(is_stub=1)`, name = `FsmName::action::actionname`
- Transitions → `graph_edges(edge_type='fsm_transition')`, source_id/target_id = bare names via normalize_symbol
- file_path = `normalize_file_path(path)` (absolute, forward slashes)

**What RM71 unlocks (not yet verified against live dj2 ingest):**
- `list_stubs` returns FSM actions/guards alongside Python stubs [?]
- `symbols_in_file('encounter.json')` lists all 14 FSM nodes [?]
- `blast_radius(start_combat)` sees FSM node + Python callers [?]

---

## NEXT SESSION -- start here

**Verify RM71 against live dj2 corpus.** Re-ingest dj2 and confirm:
1. `symbols_in_file('encounter.json')` returns 14 rows
2. `list_stubs` includes FSM actions/guards
3. `blast_radius(start_combat)` surfaces both FSM and Python sides

Server start: `.venv\Scripts\python.exe -m determined.ui.ui_server` from `C:\Users\bartl\dev\Determined`
Load dj2 corpus via UI or `socket.emit("load_db", {path: <abs db path>})` — must re-ingest for FSM rows to appear.

**After verification, next candidates from TRACKER:**
- RM69 corpus aggregation (gated: needed RM71 first — now unblocked)
- Wire context_compactor into a tool (development_priorities or walk_call_chain)

---

## Known issues [V = verified, ? = carried]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Fix if noisy in real corpora.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V prior]:** emit `socket.emit("load_db", {path: <abs db path>})`
to load directly. Double-emitting ingest causes "database is locked."

**walk_call_chain blind for async Rust [V prior]:** tokio::spawn entry points return 0 nodes.
Documented in RM67 slater row. No fix planned until Rust walker arc.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
