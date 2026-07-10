# Determined - Decision Log

Curated log of non-obvious decisions, failed approaches, and surprising constraints.
Not a session diary -- entries are pruned when stale, promoted to memory files when durable.
Format: `DATE: fact -- why it matters`

---

## Active entries

2026-07-09: RM28 Stage 1 CSS color debugging trap: `.guide-on .rail-dot[data-state="green"]` CSS attribute-selector approach was correct in markup but `getComputedStyle` returned `rgba(0,0,0,0)` in eval even with inline `!important`. Root cause unclear (eval context oddity or override). Fix: set `dot.style.background` directly in `guideUpdateDots()` JS. Avoids the ambiguity entirely; CSS data-state attr kept for potential future use.

2026-07-09: Overriding a function declaration with another function declaration in the same script causes hoisting conflict: both get hoisted, the later one replaces the earlier, and `const _orig = fn` captures the overrider not the original. Fix: add a second `addEventListener` on the rail icon buttons for the visit-tracking side effect instead of wrapping `railShowSection`.

2026-07-09: LLM discovery removed from ingest path. semantic_summary (LLM per file) was blocking UI for minutes after every re-analyze. All main UI views (Frontier, Topology, Call tree, corpus panel) are pure graph queries -- no LLM needed. Discovery loop stripped from handle_reingest; "discover more" in Ask bar still available for manual run. LLM fires on-demand via symbol spotlight.

2026-07-09: WinError 32 on Re-analyze: Windows holds DB file open (Search indexer / Defender) even after server closes its connection. Fix: clear tables in place (DELETE FROM each table + WAL checkpoint) instead of deleting the file. Retry loop on unlink is insufficient -- external processes hold longer than 3s.

2026-07-09: Re-analyze modal confusion: clicking Re-analyze showed a "Previous analysis found -- Load or Re-analyze?" modal, causing users to click Load (which just reloads old DB). Fix: track `_reanalyzeIntent` flag in JS; when set, scan_result handler skips the modal and calls startIngest directly.

2026-07-09: Determined finds stubs, not missing symbols. If a route calls `queries.get_entry()` and that function was never written, Direct mode shows nothing -- there's no stub to find. A type checker (mypy) catches missing symbols. This is a real boundary to explain in docs and a real limitation to know when analyzing unknown code.

2026-07-09: Duplicate symbol detection is a genuine gap. Two functions with the same name in different files appear as two graph nodes -- no existing mode surfaces the collision. The one that's uncalled appears as an orphan, but nothing says WHY or that a same-named function exists elsewhere. Filed as RM29.

2026-07-09: GETTING_STARTED.md voice lesson: don't narrate tool output, explain why the numbers mean what they mean and how the tool thinks. "Roots now include Entry" is weak; "the call graph is built from imports and calls, not intent -- Entry is a root because nothing imports it yet, not because it's an entry point" teaches the model.

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
