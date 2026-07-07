# Determined - Decision Log

Curated log of non-obvious decisions, failed approaches, and surprising constraints.
Not a session diary -- entries are pruned when stale, promoted to memory files when durable.
Format: `DATE: fact -- why it matters`

---

## Active entries

2026-07-07: find_abc_gaps blind spot: gap query uses `file_path != ?` to find concrete overrides, so same-file inheritance (ABC base + subclasses all in one file) always reports a gap even when overrides exist. EnrichmentProcessor.process/can_handle in processor.py not detected as overrides of EntryProcessor abstract methods. Fix: change query to check for any non-stub function with same name regardless of file, or use class hierarchy to confirm subclass relationship.

2026-07-06: reingest_file graph_edges wipe bug: when reingesting a stub file (zero outgoing calls), symbol_references is empty → GraphBuilder produces no edges → files_in_run is empty set → _persist_graph_edges falls through to `DELETE FROM graph_edges` full reset. Fix: explicit `DELETE FROM graph_edges WHERE caller_file = ?` before building the graph, then insert edges directly, bypassing _persist_graph_edges entirely for the reingest path.

2026-07-06: UI Re-analyze+ button does NOT trigger reingest via the CLI reingest_file path -- it runs discover_run in a background thread which may conflict with open sqlite3 connections; safer to call reingest_file directly from Python for step-by-step seed development.

2026-07-05: RM17 root cause: Flask @route decorator means route handlers have 0 corpus callers -- static analysis can't follow decorator registration; all route handlers appear as orphans unless we special-case @*.route()

2026-07-05: RM17 root cause: role inference assigned INTERFACER (95%) to capture() which is a COORDINATOR -- "calls many external collaborators" fires INTERFACER pattern, but orchestrating a use case is COORDINATOR; call diversity alone doesn't distinguish the two

2026-07-05: RM17: corpus switch picker bug -- "Switch corpus" modal sends full absolute path via load_db socket event, not just filename; clicking the row worked but the tab title didn't update until JS socket.emit('load_db', {path: full_path}) was called directly

2026-07-05: llm_client lazy-start: _ensure_server() added to generate()/chat() -- server started at UI launch but can crash or die between sessions; without lazy-start any LLM call after a crash returns None silently, error only surfaces at query layer

2026-07-05: gap-summary section folded into corpus-map-inner (renderCorpusMap now owns it) -- keeps stubs + coverage gaps visually grouped; removed standalone #gap-summary-section div from HTML

2026-07-05: Roots/Core are now a JS toggle (not two always-visible sections) -- reduces panel height, each tab has title= tooltip explaining the distinction; Roots is default

2026-07-05: 'view stubs' link now calls activateTab('frontier') directly -- previously fired LLM query 'find stubs', which silently failed when llama-server was down

2026-07-05: Corpus switch must do full page reload (switched=True flag) -- element-ID cleanup lists rot; one wrong ID crashes the corpus_ready handler silently and nothing loads (wp-body vs wp-list bug proved this)

2026-07-05: Every tab has an xxxLoad() that self-clears -- don't add cleanup logic in corpus_ready; the reload-on-switch approach means corpus_ready never needs to know individual tab state

2026-07-05: `socket` defined with `const` in console.html is not a window property -- eval()-based socket debugging is unreliable (window.socket !== socket); add console.log to template instead

2026-07-05: Python changes to ui_server.py require server restart -- HTML template changes are served fresh per request, Python changes are not

2026-07-05: Assessor takes an oracle object, not a DB path -- `Assessor(oracle)` where oracle = `DBOracle('path.db')`; wrong import path is `determined.agent.assessor` (doesn't exist), correct is `determined.assessor.assessor`

2026-07-05: llama-server is on-demand subprocess (port 8081, Qwen3-8B), NOT an NSSM Windows service -- NSSM removed session 77; started by UI on launch via background thread, stopped via atexit

2026-07-05: HISTORY.md revived as curated decision log (was deleted session 71 for being a chronological dump) -- new contract: entries pruned when stale, promoted to memory files when durable; git log is the code history
