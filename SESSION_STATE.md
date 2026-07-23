Written at commit: 2f1923f

# SESSION STATE — session 242

## Active branch: main [V]

## What happened this session

**RM71 verified end-to-end against live dj2 corpus.** [V — CLI ingest + DB query]

Ingest ran via `.venv\Scripts\python.exe -m determined.engine.run_engine C:\Users\bartl\dev\dj2`.
DB written to `C_Users_bartl_dev_dj2.db` in the repo root.

**Verification results [V]:**

`symbols_in_file('encounter.json')` — 14 rows, correct stub flags:
- 4 states (is_stub=0): initiating, awaiting_choice, resolving_fight, completed
- 5 events (is_stub=0): next, fight, flee, parley, combat_ended
- 3 actions (is_stub=1): start_combat, resolve_flee, resolve_parley
- 2 guards (is_stub=1): flee_possible, parley_possible

FSM stubs corpus-wide — 12 stubs across 3 FSMs (Barter, Encounter, Trade).
All 5 FSM files discovered: barter.json, buy.json, encounter.json, sell.json, trade.json.

`fsm_transition edges` — 5 edges for encounter.json, source_id/target_id = bare names,
caller/callee = full canonical names. edge_type='fsm_transition'. [V]

**UI ingest note:** Socket double-emit from automation caused "database is locked".
Workaround: use CLI ingest (`python -m determined.engine.run_engine <path>`) for
reliable re-ingest. UI ingest works fine when triggered once from the modal.

---

## NEXT SESSION -- start here

**RM71 is fully done and verified. Next: RM69 corpus aggregation (now unblocked).**

RM69 was gated on RM71 shipping. Read `docs/TRACKER.md` RM69 section before starting —
check if a design already exists or if design-first is still needed.

Alternative: wire context_compactor into development_priorities or walk_call_chain.
Find where text accumulates past 6K threshold and add the compress_context() call.

**To load dj2 in UI next session:**
- Start server: `.venv\Scripts\python.exe -m determined.ui.ui_server`
- Corpus already ingested at `C_Users_bartl_dev_dj2.db`
- Load without re-ingest: `socket.emit("load_db", {path: "<abs path to C_Users_bartl_dev_dj2.db>"})`

---

## Known issues [V = verified, ? = carried]

**dead artifact LIKE over-match [V prior]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Fix if noisy in real corpora.

**load_db auto-orient blocks screenshot [V prior]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V prior]:** emit `socket.emit("load_db", {path: <abs db path>})`
to load directly. Double-emitting ingest causes "database is locked."

**UI ingest automation [V this session]:** Never emit "ingest" more than once per session.
Use CLI ingest for scripted re-ingest to avoid lock collisions.

**walk_call_chain blind for async Rust [V prior]:** tokio::spawn entry points return 0 nodes.
No fix planned until Rust walker arc.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V prior]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
