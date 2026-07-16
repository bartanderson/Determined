# Determined - Decision Log

Curated log of non-obvious decisions, failed approaches, and surprising constraints.
Not a session diary -- entries are pruned when stale, promoted to memory files when durable.
Format: `DATE: fact -- why it matters`

---

## Active entries

2026-07-16: RM21 Technique 3 -- traversal pattern, not general iterative DECOMPOSE.
3 multi-hop probes run. Traversal queries failed two ways: (1) DECOMPOSE emitting
template prose ("files in Key files") when asked to plan a multi-hop chain -- model
can't hold 4-hop traversal plan in one output pass. (2) "what does each one do" heuristic
extracted "each" as a symbol name (the "what does X do" regex has no guard against English
pronouns/determiners). Blast-radius + implementation-status query (probe 3) PASSED --
DECOMPOSE was correct, impact bypass handled it. Conclusion: general iterative DECOMPOSE
loop has no evidence of being needed; gated on observing a non-traversal multi-hop failure.
Fix: (a) negative lookahead in "what does X do" heuristic; (b) walk_call_chain() BFS in
agent_tools.py; (c) trace_call_chain pattern in pattern_executor.py; (d) run_traversal()
finds HTTP route handlers via http_route col (falls back to name heuristics for older
corpora where column didn't exist at ingest time), walks chain, one LLM synthesis call.
Known limitation: start node selection is approximate for old corpora (no http_route col).
Commonplace DB needs re-ingest to populate http_route. Chain is also shallow if graph_edges
for the handler only captured library calls (Blueprint, flask.request.*) not project calls.

2026-07-16: RM21 Q5 confabulation was Determined-internal symbols leaking into corpus answers.
claim_verifier returns None when a CALLS subject has no edges ("can't refute confidently").
This let invented symbols (query_router, query_session -- real Determined modules but not in
Commonplace) escape undetected. Fix: check functions table existence before returning None.
Also: "what", "who", "where", "how", "why" were missing from _NOISE_WORDS, causing followup
suggestion text ("what calls Entry") to be parsed as CALLS claims. Q5 now passes -- no
Determined internals appear in Commonplace answers. RM21-B (prose-style scan) gated until
prose confabulation is observed in a live probe.

2026-07-15: RM62 ingester fix changes callee column from bare to qualified name post-resolution.
After the resolution post-pass, graph_edges.callee is now the full qualified FQDN (e.g.
'dungeon.generateDungeon') not the bare suffix ('generateDungeon'). Any test asserting bare
callee names on resolved JS edges will need updating. The bare-suffix fallback in
list_features/development_priorities (callee_feat_map) is now a safety net for unresolved
edges only -- resolved edges match functions.name directly. dnd-dungeon-gen must be
re-ingested to see correct EP counts.

2026-07-15: exclude_tests=True is the default for list_features and development_priorities.
Tests directories (tests/, test/, spec/, __tests__/, test_*.py) are filtered from symbol
grouping so they can't inflate EP counts. Pass exclude_tests=false to include them.
The Determined corpus had tests/regression at 236 EP topping the feature list above
determined/agent at 173 EP -- that's what triggered this.

2026-07-14: Non-Python corpora (JS/Go/Rust) must be ingested via tools/ingest_lang_corpus.py,
NOT EngineRunner.run(). EngineRunner calls scan_project_files() which only discovers .py files
and raises "Engine ingestion produced no analyses" on pure JS/Go/Rust corpora. ingest_lang_corpus.py
calls persist_all() with file_analyses=[] so the LanguageWalker step (step 5c inside persist_all)
runs discover_js_ts_files() and handles everything. The UI server's handle_ingest() also calls
EngineRunner but it only works because the corpus has Python files (dj2, Determined). For
pure-JS/Go/Rust corpora, always use the tools/ script or replicate its persist_all() call.


2026-07-13: JS call-edge resolved flag was always False before RM54 post-pass.
LanguageWalker._shared_call_edges compares raw callee name ("placeWalls") against
symbol fqdns ("gen.placeWalls") -- they never match, so resolved was always False even
for same-file calls. compute_resolved=True in LangSpec was doing nothing. Fix: post-pass
UPDATE in _persist_js_ts_files after all files processed -- compares callee against
bare suffix (SUBSTR(name, INSTR(name,'.')+1)) of every JS/TS function in the DB.
Pattern: walker sees one file at a time and can't resolve cross-file; persist layer
has full corpus and is the right place for resolution passes. Same pattern applies
if Go/Rust ever need resolved=True edges.

2026-07-13: RM39 Level 1 data_flow coverage on dj2 -- verdict.
388 total data_flow edges in dj2 after re-ingest. 57% involve builtins (list/str/int/print
wrapping function calls -- technically correct but low signal). After filtering: 168 real
app-level edges, dominated by PerlinNoise._lerp recursive math (28 edges) and stdlib wrapping.
Priority targets (process, execute, move_party, get_session, generate) show 0-1 edges each.
All high-value chains in dj2 follow `result = fn_a(); use(result)` (Level 2 pattern), not
`fn_b(fn_a())` (Level 1 pattern). Level 2 required to surface meaningful app-level data flow.
Level 2 effort: ~2 weeks. Build only when data flow tracing is actively needed for dj2 analysis.

2026-07-13: Re-ingest via UI -- how it actually works.
Re-analyze button flow (ui_server.py handle_ingest / console.html line 1388):
- If `_currentSourcePath` set (path known from a prior ingest this server session): skips
  modal, goes straight to ingest. `_currentSourcePath` is only set when an ingest runs --
  NOT when the server restarts and loads an existing DB.
- If `_currentSourcePath` empty: falls through to `socket.emit("browse", {})` which calls
  tkinter filedialog.askdirectory on the SERVER's desktop -- a native Windows folder picker
  pops up on screen. User selects the folder, result emits back, ingest runs.
Correct user flow for re-ingest on fresh server start: click Re-analyze in the real browser
-> native Windows folder picker appears on desktop -> select C:\Users\bartl\dev\dj2 -> ingest runs.
DO NOT try to automate this through the preview browser -- the native folder picker opens on
the desktop, not in the browser, so the preview tool can't see or interact with it.
If automating via claude-in-chrome or javascript_tool: emit `socket.emit("ingest", {path: "C:\\Users\\bartl\\dev\\dj2"})` directly -- bypasses the browse dialog entirely.
Permanent fix (not done): server should set `_source_path` on `init()` by reversing the
DB filename convention (`C_Users_bartl_dev_dj2.db` -> `C:\Users\bartl\dev\dj2`).

2026-07-12: RM50 inline comment extraction -- two design pivots worth remembering.
(1) Initial impl used raw line scan + content heuristics (len>5, alphanumeric filter).
Devil's advocate showed this drops legitimate short comments (TODO, ok) and filters
for edge cases that don't exist in function bodies. Replaced with tokenize.generate_tokens:
handles #-in-strings correctly, gives column position for block/inline distinction
structurally. (2) Initial marker detection used a fixed _MARKERS set (TODO/FIXME/NOTE etc).
Replaced with regex ^([A-Z][A-Z0-9_]+)\s*(?::|--?|--|  +) -- detects any ALL_CAPS label
followed by a delimiter. Captures domain-specific tags (SAFETY:, CONTRACT:) without
enumerating them. Mixed-case labels (Returns:) intentionally not tagged; consumer decides.
Key lesson: extraction layer should capture and categorize structurally, never filter by
content quality judgment. Quality decisions belong in consumers.

2026-07-11: Corpus enrichment arc (RM49-RM51) filed after devil's advocate pass on RM44-RM48.
Three failure modes identified: (1) param_types_json <1% populated in dj2 -- RM45 completion
contract would produce mostly-empty output. (2) Stubs have no docstrings -- RM46 scaffold's
embedding similarity match degrades to name-only, produces noise. (3) Design notes absent in
fresh corpus -- RM47 Tier 4 silently passes (no violations = no design notes, not "checked and
clean"). Fix: RM50 extracts inline body comments during parse (zero LLM, high-signal for
undocumented functions). RM49 infers param types + contracts from call context + LLM, stores as
kind='inferred_annotation' in knowledge_artifacts with inference_basis evidence trail. RM51
drives the pass: priority queue by caller count, propagate upward after each annotation,
converge when delta < N. Step 0 (ingest dj2 design docs) requires no code and immediately
populates RM48's requirement store. All new items include full validation specs.

2026-07-11: Design projection session -- filed RM43-RM48 and RM42 pass 2. No code written;
pure planning. The projection identified that Determined's floor (orientation, gap-finding,
design-violation detection) is solid but the transition from "found it" to "act on it" is
missing entirely. Six items close that gap in order: RM44 (topo sort stubs into work order),
RM45 (completion contract: what must the impl satisfy?), RM46 (scaffold from similar complete
fns), RM47 (readiness gate: is it safe to start?), RM48 (design-to-code delta: what does the
architecture require that doesn't exist yet?), RM42 pass 2 (persist clue board to DB across
sessions). All items written with exact entry points, reuse targets, and output shapes so they
can be implemented cold without refiguring the design. RM46 (scaffold) is the inflection point:
first tool that produces output rather than just analysis.

2026-07-11: RM39 prerequisite -- dj2 path analysis (verified, 153 files, 1321 functions, 8199 edges).
Edge types in DB: static=8098, decorator=100, thread=1. No cross_language edges (see next entry).
Socket handlers in world_app.py: handle_connect, handle_disconnect, handle_player_register,
handle_assign_character, handle_character_move, handle_join_party, handle_request_world_state.
BFS findings (static edges, project-fn filter):
- handle_disconnect: ISOLATED - 0 project-function callees (the handler body calls no project fns).
- All other handlers: depth 3-4, 10-18 nodes. Their chains converge on the same node set:
  dnd_data.get(), bestiary.get(), _get_*_data() family, _safe_callback, _load_og_json.
  This convergence is suspicious - likely a graph accuracy issue where shared module imports
  get attributed to all handlers rather than reflecting actual per-handler call paths.
- handle_request_world_state has the most distinct callees: get_character, get_active_parties_helper,
  get_location (real game-state reads).
- handle_join_party uniquely calls create_session -> _save_player_to_db/_save_session_to_db -> DB ops.
HTTP route handlers are richer: create_character (25 nodes, depth 3), move/move_character (19-26 nodes,
depth 4), execute_mutation_phase (30 nodes, depth 5). Adjudication engine is the deepest chain.
Game state carriers (annotated params): DungeonStateNeo (4 fns, dungeon_neo + world), Character (3 fns,
ai_dungeon_master + dm_chat_handler), PlayerAction (1 fn), DungeonAI/SessionManager (__init__ only).
Return-value consumers (called by 2+ callers, non-None return): process()->Dict[str,Any] from
adjudication_engine (30 callers), execute()->Any from tool_system (46), generate()->str from LLM clients
(21 each, two separate clients in dungeon_neo/ and world/), get_session()->SessionState (21),
move_party()->dict (21), get_location()->Location (23), get_event_log()->EventLog (89).
RM39 Level 1 priority targets: process() (adjudication_engine), execute() (tool_system),
generate() (llm_client), get_session() (session_system). These are called frequently and return
typed objects that gate downstream logic. The fn_b(fn_a()) nested-call pattern (RM39 Level 1 spec)
is less common in Python than result=fn_a(); fn_b(result) - Level 1 will capture some but Level 2
(variable binding tracking) needed for full coverage. Build Level 1 anyway as a foundation.

2026-07-11: RM38 scope revision -- dj2 has NO client-side socket.emit calls. The socket.io connection
is server-to-client push only (world.js calls socket.on only, never socket.emit). Client communicates
via HTMX attributes and fetch() calls to HTTP routes, not WebSocket events. The 7 @socketio.on
handlers in world_app.py are unreachable from the current browser client. RM38 premise (DOM controls
-> socket.emit -> Python handler) has no current instances to analyze. Reframe RM38 as: map
DOM controls -> fetch/HTMX POST -> HTTP route handler. Or defer until multiplayer socket events
are added to the game client. cross_language edges are 0 because dynamic_edges.py's regex finds
no socket.emit in the HTML/JS source -- not a bug in the extractor, a gap in the corpus.

2026-07-10: RM21 probe finding: Technique 1 (claim verifier) never fired across 6 multi-hop queries against Commonplace. The ceiling isn't wrong CALLS claims -- it's upstream: wrong pattern routing (Q2 blast-radius → corpus_synthesis, Q5 traversal → symbol search), name collision collapsing same-named symbols from different files, synthesis gap (model summarizes facts instead of answering), and method confabulation. Filed as RM31-34. Techniques 2-6 (constrained decoding, MCTS, etc.) are not the right next move.

2026-07-10: RM20 done: design_note semantic dedup at store time. Embeds candidate rule, cosine-compares against all existing design_notes (threshold 0.85), skips if duplicate. Catches LLM paraphrases the old 60-char prefix check missed. Also tracks within-run embeddings to catch back-to-back similar rules in one ingest pass.

2026-07-10: RM28 Stage 2/3: GUIDE_DATA JS object in console.html and guide_commonplace.json are separate stores with identical content. JSON file is the source of truth for docs/future tooling; inline JS object is what the browser actually uses. Both must be updated together when adding new card content. No auto-sync mechanism.

2026-07-10: RM28 Stage 3: phase detection uses "_seed" in DB filename to identify skeleton phase; "_phaseDbs" companion lookup strips/appends "_seed" from the path. Works for the current two-DB setup; will need revision if more phases or different naming conventions are introduced.

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
