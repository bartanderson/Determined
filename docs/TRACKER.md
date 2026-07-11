tools/analysis - TRACKER (consolidated)
=========================================

This file is the canonical open-items list and at-a-glance status for the
Determined analysis tool. Active open items only. Closed items are deleted â€”
for historical context use git log. For architecture/intent, see DESIGN.md.

Per CLAUDE.md's working agreement: update this file in place as part of
finishing work (checkboxes, dated notes) so Bart can see what changed via
`git diff`, and so a future session doesn't need conversation history to
know where things stand.

---

## Dashboard - at a glance

**Last session (2026-07-10, session 140):** RM21 adversarial probe follow-up against Determined corpus. Corrected prior handoff (Q1/Q4/Q5 were partial, not all-pass). Fixed Q4 (imports of <file.py> NEED pattern + list_import_deps resolver + DECOMPOSE_SYSTEM tip) -- now PASS. Fixed Q1 (orient_to_codebase regex expanded to 16 phrasings, moved before understand_symbol in detect rules to prevent false capture) -- now PASS. Fixed grounding pollution (test files/symbols filtered from phase0 suggestions). Known orient misses documented: "how does this work", "summarize the codebase", "tell me about this codebase" -- boundary, not bugs. Q5 still confabulates (model invents query_router/query_session pipeline that doesn't exist); deferred to next session. 533 passed, 1 skipped.

**Session 139 (2026-07-10):** RM28 Stage 5 done. guide_general.json (13 entries keyed by tab/tab:mode) + guideUpdateCard() branch on _isCommonplace in console.html. Non-Commonplace path uses GUIDE_GENERAL with element-only keys and hides the phase picker row. Also ran RM21 6-question probe against Determined corpus: fixed Q6 method confabulation (DECOMPOSE_SYSTEM tip), Q2 blast-radius wrong symbol (pattern_executor detect rule + heuristic past-tense verbs), Q2 blast_radius TypeError (set() cast before subtraction), Q2 OperationalError (functions table literal). 533 passed, 1 skipped.

**Session 138 (2026-07-10):** RM36 + RM37 done. RM36: `_corpus_index()` injects hot files + entry points into Phase 1 DECOMPOSE prompt when grounding is empty -- eliminates `<file.py>` placeholder NEEDs. RM37: negative lookahead on survey heuristic's `what is` branch prevents "path" from being extracted as a symbol name. Also fixed `blast_radius` OperationalError (functions table has no `symbol_type` column -- queried as real column instead of literal). RM21 probe re-run: all 6 queries pass. 533 passed, 1 skipped.

**Session 117 (2026-07-08):** RM27 done. GRASP 9 principles baked as JSON (determined/data/grasp_principles.json + grasp_loader.py), wired into _check_design_violations_core alongside SOTS tenets. check_design_violations now surfaces named GRASP violations (e.g. GRASP-9 Protected Variations on check_design_violations itself). 481 passed, 1 skipped. RM23 also done this session: Phase 3 walk completed on complete Commonplace corpus (25 files, 64 functions). DB reingested 3 Walk 4 files (linker.py, searcher.py, search.py) before walking. Actuals: 0 stubs, 0 ABC gaps, 16 anticipatory orphans, knowledge layer empty (correct fresh-corpus state). Phase 3 section of COMMONPLACE_USER_JOURNEY.md updated with tool outputs. step_queue.md corrected (session 116 claimed advancement but didn't actually write it). No engine files changed; tests not re-run.

**Session 81 (2026-07-05):** Sidebar icon-nav shipped. 4-icon rail (Corpus/Navigate/Tools/Ask) replaces flat sidebar. Corpus panel: analyze + corpus map + gaps. Navigate panel: 6 start-here shortcuts only. Collapse to rail-only on active icon click. 436 passed, 1 skipped.

**Session 67 (2026-07-04):** Item 28 confirmed already done. RM6 + RM7 benchmarked with live 8B. ABC Frontier mode verified in browser (8 classes, 35 methods). reason_about full pipeline fired end-to-end (Decompose â†’ DB â†’ evaluate() â†’ Synthesize). launch.json fixed. 399 tests pass.

**Session 60 (2026-07-03):** Item 27 executed (self-review). Item 28 filed.
infer_behavior refactored to delegate to _infer_behavior_for_symbol (70 lines removed).
classify_references crash on --reingest-file fixed (project_symbols via ctx not analysis).
Determined corpus DB migrated (param_types_json column added); 9 files reingested.
Self-review findings: role inference accurate, match_structural_pattern limited at radius=2
with 3B model, SOTS XI on evaluate() filed as item 28. 372 tests pass.

**Before that (2026-07-01, session 50):** Items 25 + 26 + 14 closed.
Item 14: two-tier LLM in llm_client.py. generate_quality()/chat_quality()/is_available_quality()
target Qwen3.6-27B-Q4_K_M on port 8081, silent fallback to 3B if not running.
_synthesize_with_ollama and gap_analysis upgraded to quality tier; distillation stays 3B.
Start quality tier: llama-server.exe -m models/gguf/Qwen3.6-27B-Q4_K_M.gguf --port 8081
Items 25+26: llama-server migration complete, Ollama uninstalled, ~50GB freed. 335 passed, 1 skipped.

**Before that (2026-07-01, session 50 earlier):** Items 25 + 26 closed.
All Ollama call sites in Determined were already migrated to llm_client.py targeting
llama-server on port 8080. Fixed one broken import (OLLAMA_MODEL) in claude_eval.py
that would have crashed on import. Ollama uninstalled; ~50GB freed. No open numbered
items remain. 335 passed, 1 skipped.

**Before that (2026-06-30, session 43):** Items 23 + 24 done.
docstring_health tool: missing detection (SQL), staleness detection (cosine similarity vs
distilled summary, threshold 0.55), proposal storage in workflow queue. gap_analysis tool:
on-demand LLM brainstorm of typed fills (extend/bridge/mirror/consolidate) for a scoped
area, stores as backlog item, framed as generative/idea-mode. _gap_summary_block() fast
DB-only helper now embedded in knowledge_status as GAPS AT A GLANCE section. Both wired
into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern. 323 pass, 1 pre-existing flake, 1 skip.

**Before that (2026-06-30, session 42):** Items 21 + 22 done.
symbol_context tool: unified single-call view of everything known about a symbol
(declaration, docstring, risk, find-references, callers/callees, class attrs, design
frame, findings). concept_search tool: semantic + keyword search across all text
surfaces ranked by cosine similarity. Both wired into TOOLS, REGISTRY, TASK_PATTERNS,
detect_pattern. understand_symbol pattern now single step. 321 tests pass.

**Before that (2026-06-29, session 36):** Items 25/26 filed (llama-server migration).
llama-server b9842 downloaded to C:\Users\bartl\models\llama-server\llama-server.exe.
llama3.2-3b.gguf copied to C:\Users\bartl\models\gguf\. Health check passing.
Items 21-24 designed and filed (assistant arc). Items 1/2/3 closed.

**Before that (2026-06-29, session 36 earlier):** Items 1, 2, 3 closed. Items 21-24 designed and filed (assistant arc).
Items 2 and 3 superseded by 22 and 23 respectively. No code written for 21-24 yet.

**Before that (2026-06-29, session 36 earlier):** Items 1, 2, 3 closed.
Item 1: _classify_role() in parse_ast.py (test/entry_point/init/config/module heuristics).
Migration guards removed from persistence_engine; param_types_json moved into CREATE TABLE.
Items 2 and 3: explicitly deferred - no active need. No open numbered items remain.
323 pass, 1 pre-existing Windows file-handle flake.

**Before that (2026-06-29, session 35):** Items 6 and 20 done.
Item 6: reingest_file() incremental re-ingest, FileDelta scratchpad, INSERT OR IGNORE fix.
Item 20: param annotation capture (param_types_json), class attribute tracking
(class_attributes table), annotation-resolved call edges (SymbolReference.resolved,
GraphEdge.resolved, graph_edges.resolved), list_callers/callees tag, describe_file %
stat, DBOracle.get_class_attribute_type(). 19 new tests total. 296 pass.

**Before that (2026-06-29, session 35 earlier):** Item 6 done: incremental per-file re-ingest.
reingest_file() in determined/ingestion/reingest_file.py. FileDelta in-memory scratchpad
(old/new symbol state, added/updated/removed sets). apply_file_delta: insert new symbols
first, then persist_file_analysis, then delete stale old symbols, then rebuild outbound
edges. Inbound edges to removed symbols become honest dangling references. Fixed
_insert_symbol to INSERT OR IGNORE (was plain INSERT - latent re-ingest bug). Wired as
agent tool, CLI --reingest-file, REGISTRY. 6 new tests; 283 pass.

**Before that (2026-06-29, session 34):** Contracts fully reconciled and wired (item 7).
PyAnalyzer (ICSE 2024) reviewed; annotation-based call graph accuracy improvement
planned as item 20. SESSION_STATE updated.

**Before that (2026-06-28, session 33):** knowledge.db eliminated.
All tables (knowledge_artifacts, workflow_items, bags, bag_items) now live in corpus
DB. KnowledgeOracle deleted. Assessor._knowledge_conn returns oracle.conn. SOTS baked
as JSON (sots_tenets.json + sots_loader.py). semantic_summaries moved to corpus DB.
DB naming fixed (C_Users_bartl_dev_harrow.db). 304 regression tests pass.

**Before that (2026-06-28, session 32):** Items 9, 10, 19 done.
Item 9: distillation pass - distill_corpus() tool, distilled kind in knowledge_artifacts,
wired into symbol_brief (preamble) and goal_intake step 1 (enriched embedding). 301 tests.
Item 10: _raw helpers layer - 5 private raw helpers (_search_symbols_raw, _list_callers_raw,
_list_callees_raw, _graph_most_connected_raw, _graph_subgraph_raw), string tools now derive
from raw (XIV: one source of truth), goal_intake step 1 uses _search_symbols_raw. 303 tests.
Item 19: check_design_violations tool - semantic cosine-search against design_notes, constraint
language filter, wired into risk_profile, pure analysis only (SOTS XI). Self-audit ran against
Determined's own corpus (168 design_notes, 5 WARM symbols) - produced real findings, validated.

**Before that (2026-06-28, session 30):** Mentor arc complete. Items 23/24/25 closed.
Item 23 rebuilt on embeddings (all-MiniLM-L6-v2, docstring-enriched queries, threshold 0.32).
SOTS (shapeofthesystem.com, 25 tenets) ingested into knowledge.db as design_notes -- surfaces
automatically via frame comparison. Item 24: goal_intake tool -- natural language goal ->
navigation plan (relevant symbols + risk badges + design rules + ordered approach). Item 25:
corpus map branch merged and deleted. Determined .claude/ added (same as dj2). 320/322 passing.

**Before that (2026-06-25/26, session 19):** Multiple bug fixes + corpus scoping + dj2 design docs.
Items 16/17/18 all fixed and closed. run_engine.py repo_root hardcoded to "." - fixed. scan_project_files.py:
3.10/3.11/3.12 venv dirs now excluded. knowledge.db corpus scoping complete (corpus column on knowledge_artifacts
+ semantic_summaries, scoped across all read/write paths: intent, oracle, assessor, agent layers). UI corpus
switch tab refresh fixed (_startupFiredFor tracks DB path). DB lock on re-analysis fixed (close oracle before
unlink). ingest_done now triggers corpus_status -> corpus_ready -> tab refresh. Regression fix: stale
test_list_callees_no_callees assertion. 298/298 passing. dj2 design docs written: 00E AI_LAYER_OPPORTUNITIES,
00F ASPIRATIONAL_DESIGN_INTENT (section H links back to item 19). Item 14 (validate small-model) is now
unblocked - all blockers resolved, harrow corpus clean and scoped.

**Before that (2026-06-24, session 17, continued):** Tool registry. New file:
determined/agent/tool_registry.py - REGISTRY (28 tools, full metadata: purpose/args/output/feeds/use_when/category),
TASK_PATTERNS (7 named workflows), describe_tool (callable from agent). agent_prompt.py now generates
TOOL_DESCRIPTIONS from the registry (all 28 tools, grouped by category). describe_tool wired into TOOLS.
2 new tests. 276/276 passing.

**Before that (2026-06-24, session 17, continued):** Knowledge layer additions.
extract_design_facts() - no-LLM structural extraction (entry points, dead code, hot symbols, stub files).
knowledge_status tool, get_findings expanded to semantic_summaries. 274/274 passing.

**Before that (2026-06-24, session 17):** Ran tool against dj2 corpus, found and fixed 5 real bugs.
is_hot was hardcoded False (now bool(mutations)); is_stub column missing from old DBs (migration added);
graph_most_connected returned builtins/externals (now project-only); find_todos only scanned docstrings
(now scans file content); task_generator had tools/analysis branding. Also fixed 2 stale regression tests.
274/274 passing. dj2 corpus re-ingested: 150 files, 132 hot, 47 stubs detected.

**Previously (2026-06-24, session 16):** Migration complete.
tools/analysis/ deleted from dj2. Engine now lives exclusively in Determined.
28 regression test files (279 tests) passing. knowledge.db intact (77KB).
dj2 is game code only. Both repos committed and pushed.

**Item 14 done (2026-06-27):** llama3.2:3b validated cold against harrow corpus.
All 7 orient_to_codebase steps fired in order. Model did not hallucinate tool names or skip steps.
Final synthesis correctly identified the key symbols. Pattern executor works. Item 14 closed.

**Item 15 done (session 18):** Pattern executor built and wired in. Model no longer picks
tools when a named pattern matches - executor drives the sequence, model only interprets
each step result. 293/293 tests passing.

**Full history:** `git log` (HISTORY.md is a decision log, not a session diary).

---

## Open items

---

RM39. **[OPEN] Data flow tracking: parameter-passing and return-value edges**

   **The gap:** The graph tracks control flow (which function calls which) but not data
   flow (what values move between functions). We can say "handler A calls validate_move
   calls apply_move" but not "the player_action dict from the socket message reaches
   validate_move, and validate_move's bool return gates whether apply_move runs."
   For UI-to-output chain reasoning this is the missing half.

   **Design constraint (SOTS XXI):** Build Level 1 only after the prerequisite analysis
   identifies the specific patterns that matter in the real corpus. Do not build speculatively.

   ---

   **Prerequisite -- dj2 path analysis [DONE 2026-07-11]:**
   Re-ingested dj2 corpus (153 files, 1321 fns, 8199 edges). Full BFS from all socket handlers
   and HTTP route handlers. Findings in HISTORY.md 2026-07-11 entry. Key scoping results:
   - Level 1 priority targets: process()->Dict (adjudication_engine, 30 callers),
     execute()->Any (tool_system, 46 callers), generate()->str (llm_client, 21 callers),
     get_session()->SessionState (21 callers), move_party()->dict (21 callers).
   - fn_b(fn_a()) nested-call pattern is less common than result=fn(); use(result). Level 1
     captures some cases; Level 2 (variable binding) needed for full coverage.
   - State carriers: DungeonStateNeo, Character, PlayerAction (annotated params, 11 fns total).

   ---

   **Level 1 -- parameter-passing edges (~2 days after prerequisite):**
   In `parse_ast.py` `Visitor.visit_Call`, when a call argument is itself a call
   (`fn_b(fn_a())`), emit a `data_flow` edge: `fn_a -> fn_b`, via='return_value'.
   Also: when a param is annotated and the annotation matches a known function's
   return annotation, emit a typed data edge.

   Storage: extend `graph_edges` with `edge_type='data_flow'` (Option B -- traversal
   functions already handle all edge types; existing tools get data flow edges for free).
   Alternative Option A (new `data_edges` table) is cleaner for queries but splits the
   graph. Decide at implementation time based on query patterns needed.

   **Level 2 -- variable binding tracking (~2 weeks, defer):**
   Track `result = fn_a()` then `fn_b(result)` across statements within a function body.
   Requires per-function variable binding map in the AST visitor. Higher accuracy, much
   more complex. Build only after Level 1 proves insufficient on real queries.

   ---

   **Tooling to investigate before building:**
   - `libCST` (Meta): concrete syntax tree with better assignment tracking than stdlib ast
   - `astroid` (pylint's AST): has inference support, may give type-propagation for free
   - `pyright` type inference API: typed parameter->return chains without writing inference
   Grep existing Determined code first: `determined/ingestion/parse_ast.py` and
   `determined/agent/graph_utils.py` are the entry points.

   **Entry points for implementation:**
   - `determined/ingestion/parse_ast.py` -- `Visitor.visit_Call` (add data_flow emission)
     and new `visit_Assign` (for Level 2 variable tracking)
   - `determined/persistence/persistence_engine.py` -- store data_flow edges in graph_edges
     (extend `_persist_graph_edges` or add to `_persist_cross_boundary_edges`)

   **Estimated effort:** prerequisite 1 session; Level 1 2 days; Level 2 2 weeks (defer).

---

RM38. **[OPEN, SCOPE REVISED 2026-07-11] JS/HTML event chain analysis: map DOM controls to HTTP routes**

   **Scope revision (2026-07-11):** dj2 has no client-side socket.emit calls. The socket.io
   connection is server-to-client push only. The @socketio.on handlers in world_app.py are
   unreachable from the current browser client. RM38's original framing (DOM controls ->
   socket.emit -> Python handler) has no current instances in dj2.
   The real gap is: DOM controls -> fetch()/HTMX -> HTTP route -> business logic.
   world.html and static/js/*.js use addEventListener + fetch() and HTMX hx-post/hx-get
   attributes. These chains are invisible to the static analyzer.
   Defer RM38 until: (a) dj2 adds client-side socket.emit, OR (b) we want to map HTTP
   route chains (fetch POST -> flask @route -> service call). File (b) as RM38b if needed.

   **Original gap (still valid for other corpora):** detect `socket.emit("event")` in
   HTML/JS and map to Python `@socketio.on("event")` handler via `cross_language` edges.
   This works correctly in Determined; dj2 just has no emit calls to detect.

   **Goal (revised):** map {DOM control -> event_type -> JS handler -> fetch(url, method)}
   and store as `js_event_binding` virtual edges. Then match fetch URL to Flask @route.
   This closes the actual chain in dj2: button_click -> fetchHandler -> HTTP route.

   ---

   **First: investigate existing JS analysis tools (0.5 days):**
   Before writing custom extraction, evaluate:
   - `js-callgraph` (npm): builds JS call graphs from source; may give handler->emit chains
   - `acorn` or `esprima` with Python subprocess: JS AST parsers, can find addEventListener
     and onclick patterns; subprocess call from Python is fine (no Python binding needed)
   - `CodeQL` for JS: GitHub semantic analysis, free for open source, queries for
     addEventListener patterns; overkill if the JS is simple but worth a look
   - `pyjsparser` / `calmjs.parse`: pure-Python JS parsers (no Node.js dependency)
   Decision criterion: if a tool can be called from Python and returns structured event
   binding data in under 1 day of integration work, use it. Otherwise write targeted
   regex/AST extraction -- the JS in dj2 is not complex.

   ---

   **What to extract (priority order):**
   1. HTML inline handlers: `<button onclick="fn()">`, `<form onsubmit="fn()">`
      -> extract element type, id/class, event_type, handler_name
   2. JS `addEventListener('click', fn)` and jQuery `.on('click', fn)` patterns
      -> extract selector, event_type, handler_name
   3. Within each JS handler function: trace calls until `socket.emit("event")` found
      -> gives handler_name -> emitted_event_name
   4. Combine: control -> event_type -> js_handler -> socket_event -> python_handler

   **Output schema** (extend `_persist_cross_boundary_edges` in persistence_engine.py):
   - Edge 1: `source_id = "<element_type>_<id_or_class>"`, `target_id = "js_handler_name"`,
     `edge_type = 'js_event_binding'`, `caller = element description`, `callee = handler`
   - Edge 2 (existing, improve): intermediate `js_handler_name -> socket_event_name` node
     so the full chain is traversable without special-casing `__js_client__`

   **Entry points:**
   - `determined/ingestion/dynamic_edges.py`: add `extract_js_event_bindings(html_src)` and
     `extract_js_call_chain(js_src, handler_name) -> socket_event` alongside existing
     `extract_socketio_handler_map` and `extract_cross_language_edges`
   - `determined/persistence/persistence_engine.py`: `_persist_cross_boundary_edges`,
     the Gap 7 block (~line 787) -- extend to also call the new extractor

   **What already exists to build on:**
   - `extract_socketio_handler_map(src)` in dynamic_edges.py: finds Python @socketio.on handlers
   - `extract_cross_language_edges(html_src, py_handler_map)`: finds socket.emit in HTML/JS
   - Both use regex over source text. Same approach works for addEventListener and onclick.

   **Estimated effort:**
   - Tool investigation: 0.5 days
   - Implementation (good external tool found): 1-2 days
   - Implementation (custom regex/AST): 2-3 days
   - New regression tests: 0.5 days

---

RM37. **[DONE 2026-07-10] Traversal heuristic false-fires on "path" as symbol name**

   Discovered in RM21 probe re-run. Q5: "what is the path from the web route to the
   database for a new entry?" matches the traversal heuristic, but the heuristic
   extracts "path" as the symbol name and runs symbol/file/findings searches for "path".
   Nothing found, answer is empty.

   The RM31 traversal fix registered a heuristic for "path from X to Y" but the word
   "path" in other phrasings (route path, code path) also fires it, extracting the
   wrong noun.

   **Fix:** tighten the traversal regex so it requires "from <A> to <B>" structure and
   extracts A and B as the subject/target. If A and B aren't extractable, fall through
   to LLM decompose instead of running dead symbol searches.

   Entry point: `determined/agent/agent_resolver.py` -- traversal heuristic in
   `_HEURISTICS`.

---

RM36. **[DONE 2026-07-10] Orient/overview questions produce `<file.py>` placeholder NEEDs**

   Discovered in RM21 probe re-run. Q1: "give me a quick overview of what this codebase
   does" -- Phase 1 LLM emits `NEED: what does <file.py> do` with a literal angle-bracket
   placeholder. The resolver finds no match, zero facts retrieved, answer is empty.

   The model doesn't know which files to ask about, so it emits a template instead of
   real filenames. The grounding step doesn't fire for this question shape (no symbol or
   file name to extract).

   **Fix:** add a named heuristic for orient/overview questions that deterministically
   builds a NEED list from the corpus: top N files by call-edge count (hottest files),
   plus entry points. No LLM needed for decompose -- the corpus map IS the answer.

   Entry point: `determined/agent/agent_resolver.py` -- add to `_HEURISTICS`.
   Reference: `graph_most_connected` and `find_entry_points` tools already exist.

---

RM28. **[STAGES 1-4 DONE 2026-07-10] Training mode: adaptive guided exploration**
   Replaces the three-mode UX concept (Tour/Discovery/Workbench) with a lighter,
   more elegant design that emerged from a full design discussion session 130.

   ---

   **Core concept: Training mode toggle**

   A small toggle in the header bar. Off by default for experienced users; on for
   new users discovering the tool. When off: today's UI, unchanged. When on: three
   things appear -- a corpus phase picker, a contextual guide card, and exploration
   color indicators on UI elements.

   **Permanent dismissal:** an X on the toggle stores `det_guide_dismissed=true` in
   localStorage. Toggle disappears permanently. A tiny "Guide" link in the footer
   restores it (no manual localStorage deletion required).

   ---

   **Adaptive guide -- no mode choice, no explicit steps**

   The guide watches what the user does and surfaces a contextual card for wherever
   they are. If they follow a logical order it feels like a tour. If they explore
   freely it still helps. No "next" button, no scripted sequence, no friction.

   The card is keyed to (active_tab + active_mode + corpus_phase). One card, always
   relevant, updates as the user moves. Card is visually neutral -- color lives on
   UI elements, not the card.

   **Content storage:** `determined/data/guide_commonplace.json`
   Shape: `{ "tab:frontier:orphan:skeleton": { "headline": "...", "body": "...",
   "what_to_notice": "..." }, ... }`

   General-layer guide (tool concepts independent of Commonplace) is deferred --
   RM16 one-liners already cover that floor. Build general layer as a second pass
   after Commonplace proves the pattern.

   ---

   **Exploration color grammar**

   Color indicators on the tab rail, sub-modes, corpus phases, and key tools.
   Tracks visited state in localStorage (`det:visited:tab:frontier` etc.).

   Rules:
   - **No color** -- unvisited. Not asking for attention.
   - **Red** -- visited, less than half the sub-elements explored.
   - **Amber** -- half or more explored, at least one remaining.
   - **Green** -- all sub-elements explored.
   - **One-action elements** -- skip red entirely, go straight to green on first visit.
     (A tab with no sub-modes, a tool with one action -- red would lie about there
     being more to do.)

   Color is a reward/progress indicator, not a to-do list. The game: find everything
   red and amber and turn it green. When everything is green, training mode has
   nothing left to offer.

   **Completion state:** all elements green â†’ guide card shows "You've explored
   everything. The guide will step back." â†’ toggle permanently auto-dismisses.

   ---

   **Corpus phase picker + code injection**

   Appears in training mode. Three phases: skeleton / complete / enhanced.
   Phase picker shows current phase and lets user jump between them.

   Implementation: start from skeleton (the existing seed/ files + seed DB).
   Injection is live -- "Add next piece" button writes the next implementation
   file to the corpus directory and calls reingest_file. The corpus panel updates
   in real time. The user watches metrics shift as code is added -- orphan count
   drops, hot symbols appear, stubs resolve. That IS the lesson.

   To jump ahead: inject all remaining pieces for a phase at once.
   Pre-built DBs for complete and enhanced are a fallback if injection proves
   fragile, but live injection is the preferred experience.

   Commonplace detection: key off `_db_path` containing "commonplace" (case-insensitive).
   Phase picker only appears when Commonplace is the loaded corpus.

   ---

   **Colorable element inventory (to finalize at build time)**

   Tab rail: Corpus, Navigate, Tools, Ask
   Frontier sub-modes: Direct, Orphan, ABC
   Corpus panel elements: Roots/Core toggle, corpus map expand, duplicate badge
   Corpus phases: skeleton, complete, enhanced (only when Commonplace loaded)
   Tools panel: each tool individually
   Ask bar: first query run

   Exact list locked in during Stage 1 build when the localStorage keys are defined.

   ---

   **Build order (each stage independently useful)**

   Stage 1: Toggle in header + permanent dismissal + localStorage scaffold +
            color indicators on tab rail (no content yet). Verify color grammar
            in browser before wiring anything else.

   Stage 2: Guide card panel + guide_commonplace.json content for all tab/mode
            combinations. Card updates as user navigates.

   Stage 3: Corpus phase picker + code injection. Skeleton â†’ complete â†’ enhanced
            live in the browser.

   Stage 4: Completion state. All green â†’ auto-dismiss message.

   Stage 5 **[DONE 2026-07-10]**: General guide layer for non-Commonplace corpora.
            guide_general.json keyed to element only (no corpus phase).

   ---

   **What already exists (build on, don't replace)**

   - COMMONPLACE_USER_JOURNEY.md -- content source for guide_commonplace.json
   - seed/ directory -- the skeleton state, 17 files, ready to inject from
   - reingest_file -- already works; injection calls this
   - RM16 one-liners -- the general-guide floor, already in place

---

RM23. **[DONE 2026-07-08] Commonplace Phase 3 extras arc: walk with Determined**

   Walk completed session 117. Phase 3 section of COMMONPLACE_USER_JOURNEY.md
   updated with actual tool outputs. All 3 extras were already implemented (Walk 4,
   session 115); this session was the documentation pass.

   **Actuals (complete corpus, 25 files, 64 functions):**
   - knowledge_status: 0 distilled, 42/64 missing docstrings, 0 design notes
   - find_abc_gaps: "All ABC stub methods have at least one non-stub override"
   - frontier_coverage: 0 stubs, 16 orphans (all anticipatory), LOW pressure
   - find_orphaned_impls: create_app possibly-stranded; 15 others anticipatory
   - check_design_violations: requires design notes first (0 in DB -- correct for fresh corpus)

   **DB reingested** 3 Walk 4 files before walking (linker.py, search.py, searcher.py
   were newer than DB). 1 updated in linker.py, 2 updated in searcher.py.

---

RM22. **[DONE 2026-07-08] Phase 0 bootstrap: new corpus from blank directory**

   UI guidance shipped (committed 0aaa111). Walk documented in
   COMMONPLACE_USER_JOURNEY.md Phase 0 section (committed this session).

   **What was built:**
   - 0-file scan: modal shows 3-step bootstrap guide (write first file, Analyze, then reingest_file)
   - Non-zero scan: modal shows "Analyze this project? N files Â· M MB Â· ~Xs" + confirm
   - Phase 0 walk: 17 seed files written to blank dir, Analyze produced DB in ~30s
   - Actuals: 17 files, 1 hot (storage/db.py), 0 stubs, 31 functions, 137 edges
   - Walk directory: C:\Users\bartl\dev\commonplace-walk (not in repo)

   **Key finding from walk:** 0 stubs in current seed (Walk 4 extras implemented
   extractor + processor functions). Phase 1 journey doc (which shows 2 stubs) was
   from an earlier seed state. Phase 0 â†’ seed shows a clean 0-stub codebase as
   starting point. ABC class hierarchy (EntryProcessor) surfaces immediately.

---

RM20. **[DONE 2026-07-10] design_note deduplication: LLM pass re-extracts rules the deterministic pass already stored**

   Done 2026-07-10 (session 134, commit 89bc6d5). Embed-at-store-time dedup wired into
   doc_extractor.py: each candidate rule embedded, cosine-compared against existing
   design_notes (threshold 0.85), skipped if duplicate. Also tracks within-run embeddings
   to catch back-to-back similar rules in one ingest pass.

   ~~Original description below (preserved for context):~~

   Discovered during RM15 Walk 2 Step 4 (Commonplace DESIGN.md ingest).

   **The problem:** `ingest_design_docs` runs two passes over a design doc:
   (1) a deterministic regex/keyword pass that extracts explicit constraint phrases, and
   (2) an LLM pass that extracts named invariants and authority rules.
   Both passes store their findings as `kind=design_note` artifacts. When the LLM
   rephrases a rule the deterministic pass already found, deduplication fails.

   **Current dedup:** compares the first 60 chars of the rule body at store time.
   Insufficient when LLM paraphrases: "PERMISSION: X must not Y" (deterministic) vs.
   "Only X is permitted to Y" (LLM) are the same rule but won't match.

   **Effect:** `check_design_violations` output shows the same rule 2-3x at nearly
   identical scores, inflating apparent violation count and obscuring signal.
   Observed: PERMISSION-prefixed duplicates appearing at 0.41 and 0.30 for a single
   query against a 10-rule corpus.

   **Fix options (in order of confidence):**
   1. Embed each candidate rule at store time; skip if cosine similarity to any
      existing design_note in the corpus exceeds 0.85. Reuses existing embedding
      infrastructure (`embed_text` from `determined/oracle/embedding_model.py`).
   2. Run dedup as a post-pass after all extraction: cluster all stored design_notes
      by embedding similarity, keep one canonical form per cluster.
   3. Skip the LLM extraction pass for rule types the deterministic pass already
      covers (PERMISSION, LAYER, MUST-NOT phrases). LLM pass restricted to rules
      the deterministic pass cannot find (e.g. implicit authority rules, named invariants
      phrased as prose without trigger words).

   **Recommended:** Option 1. One embedding call per candidate at ingest time.
   If similarity >= 0.85 to any stored rule, skip storage. Fast, local, uses
   existing infrastructure. No schema change needed.

   **Where to implement:** `determined/agent/doc_extractor.py` â€” the store step
   inside `ingest_design_docs`. Check before INSERT.

   **Estimated effort:** ~1 hour. Small, self-contained.

---

RM19. **[DONE 2026-07-07] Semantic Reconciliation Arc: duplicate detection, intent differencing, primitive discovery**

   All three passes implemented (confirmed session 118 â€” was marked FILED but code already exists):
   - Pass 1: `find_duplicates` â€” embed "{name}: {docstring}", pairwise cosine similarity matrix, pairs above threshold stored as `reconciliation_finding` artifacts.
   - Pass 2: `classify_duplicates` â€” feeds each stored pair to Qwen3-8B, classifies divergence from fixed taxonomy (accidental copy, historical evolution, performance optimization, platform-specific behavior, security reason, genuinely different abstraction). Stores classification as `reconciliation_finding`.
   - Pass 3: `find_primitive_gaps` â€” mines call graph for callee pairs that appear together across multiple callers; surfaces as `primitive_gap` artifacts.
   All three wired into TOOLS, tool_registry.py, and `list_reconciliation_findings`.

   Passes 4 (canonicalization) and 5 (architectural drift) deferred â€” require evidence from 1-3 first.



   Determined has shifted from static analyzer toward semantic maintenance system. This arc
   adds three reconciliation passes grounded in the call graph and embedding infrastructure
   that already exists.

   **Core design constraint:** every finding carries a reason classification, not just a
   similarity score. Goal is "explained differences" not "eliminated differences." The ideal
   output is not "these were merged" but "these differ by 7% due to platform-specific
   requirements -- divergence is intentional and documented."

   **Pass 1 -- Duplicate Detection (easy, do first)**
   Embed all function docstrings + names via existing all-MiniLM-L6-v2 infrastructure.
   Cluster by cosine similarity above threshold (0.85+). Surface groups of near-identical
   symbols. Output: candidate pairs with similarity score. No LLM needed.

   **Pass 2 -- Intent Differencing (medium, depends on Pass 1)**
   For each candidate pair from Pass 1: feed both docstrings + call graphs + file context
   to Qwen3-8B. Classify divergence reason from a fixed taxonomy:
   - accidental copy
   - historical evolution
   - performance optimization
   - platform-specific behavior
   - security reason
   - genuinely different abstraction
   Store classification as knowledge_artifact (kind=reconciliation_finding).

   **Pass 3 -- Primitive Discovery (novel, highest value)**
   Mine the call graph for repeated compositions: sequences Aâ†’Bâ†’Câ†’D that appear across
   multiple independent call chains. A composition appearing N times is evidence that a
   missing abstraction exists. Surface: "this 4-step pattern appears 12 times -- no shared
   primitive exists." Store as gap proposal in workflow_items.

   **Pass 4 -- Canonicalization (defer)**
   Propose structural consolidation (BaseParser hierarchy etc.). Downstream of 1+2+3
   being proven useful. High noise risk if run before evidence is established.

   **Pass 5 -- Architectural Drift (needs infrastructure)**
   Compare current dependency graph against a point-in-time snapshot to detect drift
   from intended architecture. Requires DB snapshot mechanism -- file as separate item
   when 1-3 are shipped.

   **Tractability order:** Pass 1 (one session) â†’ Pass 2 (one session) â†’ Pass 3 (two sessions).
   Passes 4 and 5 get their own items after the first three prove out.

   **What to build on:** `determined/oracle/embedding_model.py` (embed_text, cosine_similarity),
   `graph_edges` table, `knowledge_artifacts` (kind=reconciliation_finding),
   `workflow_items` (kind=backlog, provenance=llm-proposed).

---

RM18. **[DONE 2026-07-07] Act on RM17 gaps**

   Priority order from RM17 findings: Gap 2 â†’ Gap 10 â†’ Gap 1.

   **Gap 2 [DONE 2026-07-07]:** Flask @route decorator = entry point heuristic.
   `parse_ast._classify_role` now detects `@<name>.route(` pattern, classifies
   file as `entry_point`. Note: orphan count/list filtering via `_has_framework_decorator`
   was already in place. 9 regression tests added. Committed 0d9e0cc.

   **Gap 10 [DONE 2026-07-07]:** Auto-discover design docs on corpus load.
   `_check_design_doc_hint()` runs on `load_db`, scans for markdown with
   constraint_score >= 0.3 not yet ingested as design_notes, writes count+paths
   to `project_meta`. `_design_doc_hint()` reads it; `_emit_corpus_ready` includes
   it in payload. Frontend shows orange notice in header with dismiss button.

   **Gap 1 [DONE 2026-07-07]:** Structured layer-rule violation detection.
   `layer_rule` kind added to knowledge_artifacts (content = JSON {from_layer, to_layer,
   direction, source}). `_extract_layer_rules()` in doc_extractor.py parses design docs
   deterministically. `ingest_design_docs` stores layer_rule artifacts and writes
   LAYER_RULES.md seed doc with human-readable message if none found.
   `_check_import_layer_violations` now queries layer_rule artifacts directly; returns
   hint message when no rules defined. 15 new regression tests. 464 passed.

---

RM17. **[DONE 2026-07-05] Two-pass cold analysis of Commonplace: find tool blind spots**

   Findings filed in `docs/RM17_findings.md`. 10 gaps ranked. Top findings:
   - Gap 1 (HIGH): Layer-import violations invisible without design doc ingest + structured layer rules
   - Gap 2 (HIGH): Flask route handlers = 17 of 18 "orphans" are false positives; @route decorator = entry point
   - Gap 3 (MEDIUM): `_call_llm` ranked #2 root but is dead code; "ready but blocked" vs orphan distinction missing
   - Gap 4 (MEDIUM): `capture` role = INTERFACER (wrong, 95% confidence); should be COORDINATOR/CONTROLLER
   - Gap 10 (MEDIUM): DESIGN.md auto-discovery -- corpus has design constraints written for Determined, but no prompt to ingest them

   Root causes: (1) no auto-discovery/ingest of design docs; (2) Flask decorator pattern invisible to static analysis.

   **Next:** RM18 -- act on gaps. Priority order: Gap 2 (Flask entry-point heuristic, easy) â†’ Gap 10 (auto-discover design docs on corpus load) â†’ Gap 1 (structured layer-rule violations).

---

RM17_archive. **[ACTIVE text below, archived]** Two-pass cold analysis of Commonplace: find tool blind spots

   Two-pass examination of the Commonplace corpus to find what Determined gets
   right, wrong, and can't see at all. Output is a ranked list of gaps.

   **Pass 1 â€” cold read (tool output only):**
   Load Commonplace full corpus. Walk orient â†’ frontier â†’ topology â†’ spotlight
   queries â†’ knowledge. Write down exactly what Determined says the codebase is.
   No looking at source. Pure tool output.

   **Pass 2 â€” adversarial read (source truth):**
   Read the actual Commonplace source files directly. Independently form a picture
   of what the codebase is and does. Do not reference Pass 1 output while reading.

   **Compare â€” rub them together:**
   - False positives: tool reported X, X isn't real or isn't important
   - False negatives: code clearly does Y, tool never surfaced it
   - Blind spots: whole categories the tool has no way to see (design-level gaps)

   Blind spots are the highest-value output -- they point to missing tool
   capabilities, not just missed instances.

   **Rule:** complete Pass 1 and write it down before starting Pass 2.
   Once source is read, independence is lost.

   **Output:** ranked gap list. Each gap: what's missing, why the tool can't
   see it, how fixable it is (schema/query/LLM/structural limit).

   **Corpus:** Commonplace full (not seed) -- more signal.

---

RM16. **[DONE 2026-07-05] UI concept documentation: explain what each panel/mode/concept is and when to use it**

   Every panel, mode, and concept in Determined should have a one-line explanation
   visible in the UI at all times -- not triggered by emptiness or error, just
   always present as context. The goal is that a user who lands on any state
   (empty or populated, correct mode or wrong mode) still understands what they
   are looking at and why it exists.

   **The failure mode this addresses:**
   Reactive fixes (empty-state hints, error messages) unstick the user but don't
   build understanding. A user who hits Frontier in Direct mode with results never
   learns what Orphan mode is or when they'd want it. They got lucky, not informed.

   **What this means concretely:**
   - Frontier tab: one sentence on what Direct vs Orphan vs ABC means and when
     each applies. Not in a help doc -- in the tab itself, near the mode selector.
   - Corpus panel: one sentence on what "hot", "stubs", "design notes" mean.
   - Topology tab: one sentence on what the action queue is telling you.
   - REPL: startup message explains coverage and why low coverage = empty answers.
   - Each tool in the Tools panel: one line on what it does and when to reach for it.

   **Scope:** apply systematically across all journey steps in COMMONPLACE_JOURNEY.md.
   Walk each step, identify what a new user would not understand without prior
   knowledge, add the minimum text that closes that gap.

   **What this is not:** a tutorial, a help system, or a walkthrough. One sentence
   per concept, always visible, never modal. Experienced users ignore it; new users
   learn from it without having to ask.

   **When to work this:** after F1 and F3 are fixed. Walk the journey again with
   fresh eyes and file the missing explanations as a single pass.

---

RM21. **[ACTIVE] Small-model reasoning enhancement: push Qwen3-8B beyond its natural ceiling**

   **Technique 1 DONE (2026-07-08 + extended 2026-07-10):** Verification loop wired into
   `_answer()` in `local_agent.py`. After ASSEMBLE, `claim_verifier.py` extracts structural
   claims (CALLS, NO_CALLERS, HAS_METHOD) via regex, checks each against `graph_edges` /
   `classes.methods_json`, and builds a correction block if any are wrong. One re-assembly
   pass with corrections prepended to facts. RM31-34 also done as part of this arc:
   blast-radius and traversal routing fixed (RM31), name-collision tagging in facts (RM32),
   comparative synthesis hint in ASSEMBLE (RM33), method confabulation detection (RM34).

   **RM21 probe re-run 2026-07-10 (after RM31-34):**
   - Q3 (name collision/search centrality): PASS -- RM32 tagging works, model answered correctly
   - Q4 (comparative boolean): PASS -- RM33 YES/NO hint fired, answer correct
   - Q6 (Entry class methods): PASS -- RM34 prompt hardening + verifier, no invented methods
   - Q1 (orient/overview): FAIL -- model emits `<file.py>` placeholder NEED, zero facts. Filed RM36.
   - Q2 (blast-radius linker.py): PASS -- blast_radius OperationalError fixed (symbol_type literal not column); answer now traces actual callers.
   - Q5 (traversal web-to-db): FAIL -- "path" word triggers traversal heuristic but extracts
     "path" as symbol name, runs dead searches. Filed RM37.

   **Remaining techniques (2-6):** Constrained decoding, prompt chaining, MCTS,
   speculative verification, large-model fallback. Build only after Technique 1
   proves insufficient on real multi-hop queries.



   The long-term goal: make Determined's local model reason reliably over multi-hop
   questions without requiring a larger model. Not a single feature -- a layered
   architecture built incrementally.

   **Why this matters:** Qwen3-8B can call one tool fine but degrades on multi-step
   reasoning chains (Aâ†’Bâ†’Câ†’D). Each technique below attacks a different part of that
   failure mode. Determined's deterministic fact layer is the key enabler -- the model
   doesn't need to *know* facts, it needs to *accept corrections* from the DB.

   **Technique 1 -- Verification loops (highest leverage, do first)**
   Model generates a claim â†’ Determined checks it against the DB â†’ if wrong, feed
   the correction back â†’ model revises. Pure tool-call pattern, no new infrastructure.
   Qwen3-8B is already good enough at accepting corrections. Start here.

   **Technique 2 -- Constrained decoding**
   Force model output to match a grammar or schema (e.g. `outlines` library).
   Model fills slots, can't hallucinate outside the schema. Dramatically reduces
   noise on structured queries. Pair with Technique 1.

   **Technique 3 -- Prompt chaining / decomposition**
   Break one hard question into N easy questions each within model capability.
   Determined answers each hop deterministically; model only plans the chain.
   This is the "lightly reasoned over" pattern already partially in place.

   **Technique 4 -- MCTS over reasoning (already in notes as future item)**
   Tree-search over evaluate() -- explore multiple reasoning paths, score them,
   pick the best. Expensive but effective for unfamiliar domains. Build after
   Techniques 1-3 prove insufficient for a real query.

   **Technique 5 -- Speculative verification**
   Model proposes, Determined's DB scores. No LLM judge needed -- the corpus IS
   the judge. Requires Technique 1 infrastructure to already exist.

   **Technique 6 -- Large-model fallback via browser bridge (already built)**
   When all local techniques fail, package the relevant context and send it to a
   large model (ChatGPT, Claude.ai, DeepSeek) via CDP browser automation. No API
   key required -- attaches to your running Chrome profile via CDP port 9222.
   Existing code: `C:\Users\bartl\dev\dj2\tools.old\bridge\`
   - `unified_core.py` -- BridgeCore: CDP attach, send, extract response (Selenium)
   - `deepseek_lib.py` -- DeepSeek-specific selectors and IOC context injection
   - `diagnostics/` -- test harness (test_full_consult.py, test_send.py, etc.)
   Determined already selects relevant context; bridge just needs a target URL and
   the packaged context string. Copy bridge/ into Determined when ready to wire.

   **Tractability order:** 1 â†’ 3 â†’ 2 â†’ 5 â†’ 4 â†’ 6. Each depends on the prior being
   proven on a real RM15-style query before adding the next layer. Technique 6 is
   the escape hatch -- available now, use only when local techniques are exhausted.

   **When to work this:** after RM15 Commonplace journey is complete and we have
   a baseline of what the model gets wrong on real multi-hop queries. The failures
   will tell us which technique to reach for first.

   **Note -- stealth browser option:** `https://github.com/tiliondev/fortress` is a
   Chromium fork patched at C++ level (V8/Blink/BoringSSL) that defeats bot detection.
   Not needed for the CDP-attach-to-real-profile approach above, but useful if a target
   site blocks even real Chrome profiles or if the bridge needs a fully headless setup
   (e.g. running on a server without a display).

---

RM15. **[DONE 2026-07-08] Commonplace guided journey: run it for real, fix Determined iteratively**

   The next active work arc. Full description in docs/COMMONPLACE_VISION.md.
   Synthesized user-facing journey (actuals from all walks): docs/COMMONPLACE_USER_JOURNEY.md

   **Four phases (0=scratch, 1=seed, 2=complete, 3=extras):**

   - Phase 0 (Scratch): DONE 2026-07-08 (RM22 resolved, walk recorded).
   - Phase 1 (Seed): DONE 2026-07-08 (session 119, clean user walk).
     Seed is now 17 files, 0 stubs (Walk 4 extras implemented). Journey doc updated.
     Key findings: 0 stubs in seed = no stub implementation story; 2 orphaned-impl
     (create_app false positive, validate_entry actionable); 0 design notes on clean start.
     COMMONPLACE_USER_JOURNEY.md Phase 1 section rewritten with actual current outputs.
   - Phase 2 (Complete): DONE (Walk 3). 0 broken stubs. Actuals recorded.
   - Phase 3 (Extras): DONE 2026-07-08 (RM23). Walk recorded in COMMONPLACE_USER_JOURNEY.md.

   **All four phases complete. RM15 DONE.**

   **Known issues (for future reference):**
   - ingest_design_docs path mismatch: DESIGN.md lives outside seed/ project root.
     Must call with explicit path, not auto-discovery.
   - Seed DB accumulates developer walk artifacts (design notes, distillation) across
     sessions. For a truly clean user demo, delete knowledge_artifacts (design_note,
     distilled) and semantic_summaries before loading the seed DB.

---

RM14. **[DONE 2026-07-05] Sidebar icon-nav**

   4-icon vertical rail (ðŸ—„ Corpus / ðŸ§­ Navigate / ðŸ”§ Tools / ðŸ’¬ Ask) replaces
   the flat 6-section sidebar. Corpus panel: analyze/switch + corpus map + gaps
   at a glance. Navigate panel: 6 start-here shortcuts only. Tools panel: query
   shortcuts. Ask icon toggles query bar independently. Clicking active icon
   collapses panel to 40px rail-only for max editor space. Shell grid updated
   to 40px + 210px + 1fr (was 210px + 1fr). Commit: 380814c.

---

RM13. **[DONE 2026-07-05] UI redesign pass: close remaining delta, fold DISCOVERY_MODEL**

   All sub-items completed across sessions 75-79:
   - A4: Universal symbol context popover (session 75)
   - F7: Frontier tab orphan/disconnected mode selector (session 75)
   - #1: Chat/ask bar hidden by default (session 76)
   - A3: Collapse duplicate Cytoscape edges with count badge (session 76)
   - W4-W5: Trail breadcrumb + export as session summary (session 78)
   - #7: Context mode switching (Design/Trace/Review) + call tree race fix (session 79)
   DISCOVERY_MODEL closed as tracking category.

---

29. **[DONE 2026-07-03] Frontier graph: ABC/unimplemented-interface shape**

   The current frontier graph query (functional caller -> stub callee, suffix-match join)
   finds direct call edges to unimplemented functions. It does NOT detect the ABC pattern:
   abstract methods defined on a base class that have no concrete override anywhere in the
   corpus.

   dj2's `engine/phases.py` is the canonical example: 47 `@abstractmethod` stubs on ABC
   classes (`InputPhase`, `IntentPhase`, etc.) that are completely disconnected from game
   code -- no class inherits from them yet. The call graph has no edges to these stubs
   because nothing calls an ABC method directly.

   **What a query for this shape needs:**
   - Detect which functions are abstract methods (body is stub AND decorated with
     `@abstractmethod`, OR parent class inherits ABC).
   - Find all classes in the corpus that inherit from the ABC (via class_attributes or
     a new class_hierarchy table).
   - For each abstract method, check whether any subclass overrides it.
   - Surface: abstract methods with zero overrides = true unimplemented frontier.

   **Implementation (session 66):** `find_abc_gaps()` in agent_tools.py â€” queries classes
   with base_classes_json containing 'ABC'/'Abstract', joins to functions to find stub methods,
   checks for non-stub overrides elsewhere. No new schema needed: existing `classes.base_classes_json`
   + `functions.is_stub` + `functions.file_path` are sufficient. Proxy heuristic (stub on ABC class
   = abstract) works well in practice. On dj2: 35 unimplemented abstract methods across 8 classes.
   Wired as agent tool `find_abc_gaps`, registry entry, test file (5 tests). Frontier tab gains
   "ABC (interface gaps)" mode â€” purple diamond nodes for abstract classes, red stubs for methods.
   Multi-level inheritance not handled (deferred â€” not needed for current corpora).

---

27. **[DONE 2026-07-08] Standards-grounded self-review: GRASP vocabulary wired into check_design_violations**

   As the tool matures, it should be capable of analyzing its own codebase and comparing
   its design decisions against documented, authoritative software design standards rather
   than ad-hoc patterns invented for the project.

   **The trigger for this item:** `infer_behavior`'s original 6 role patterns were invented
   from dj2's architecture rather than grounded in a published taxonomy. Wirfs-Brock RDD
   roles replaced them (session 56, 2026-07-02). This revealed a broader principle: any
   time Determined uses a classification scheme or taxonomy, that scheme should trace to
   a documented, general-purpose source rather than being project-specific.

   **What this item covers:**
   - When Determined is capable enough to analyze a moderately complex Python codebase,
     point it at `C:\Users\bartl\dev\Determined` itself as a corpus.
   - Ask it to identify places where design choices (tool names, category sets, scoring
     heuristics, pattern libraries) appear to be project-specific rather than grounded
     in general software engineering literature.
   - Compare findings against what the tool claims to support (general-purpose analysis
     of any repository) vs. what its internals assume.

   **Two standards with clear roles here (session 56 analysis):**

   Wirfs-Brock RDD -- already adopted for `infer_behavior`. Describes what a component
   IS (its role/character). Right for classification: "what is this function?"

   GRASP (Larman, "Applying UML and Patterns") -- describes WHERE to put responsibility.
   Not a classification taxonomy but a decision framework: "should this go here or there?"
   Two distinct uses:

   1. Determined violation detection (near-term): give findings design vocabulary.
      Current findings say "this symbol calls across a boundary." GRASP lets Determined
      say WHY that's wrong:
      - "Reaches across to get data it doesn't own -- violates Information Expert"
      - "Creates objects it has no business creating -- violates Creator"
      - "Boundary is reached around rather than through -- violates Protected Variations"
      This makes findings actionable, not just structural.

   2. dj2 design validation (longer term): dj2's Architectural Constitution already
      embodies GRASP without naming it. The mapping is near-perfect:
      - Protected Variations -> the AI boundary (LLM never touches game state directly)
      - Controller -> the adjudication engine (handles player action events)
      - Information Expert -> the authority hierarchy (only the owner mutates its data)
      - Indirection -> the Intent layer (input passes through classification before state)
      - Pure Fabrication -> ai_boundary.py itself (fabricated service, not a domain concept)
      Once Determined can reference GRASP explicitly, it can validate dj2's architecture
      with named principles rather than structural heuristics alone.

   **Other references to consider at review time:**
   - GoF design patterns -- structural/behavioral/creational
   - Clean Architecture layers (Martin) -- for layer-boundary detection
   - Any taxonomy currently hardcoded in Determined should cite its source or be replaced

   **Prerequisite:** Determined must be able to run corpus synthesis on a moderately
   large Python repo (itself) and have enough orientation capability to surface
   design decisions from its own knowledge_artifacts. Probably ready after phase 4
   (data flow tracing) is working.

   **Self-review run 2026-07-03 (session 60):** Item 27 executed. Determined's own corpus
   was ingested and the agent modules were analyzed. Key findings:
   - Role inference (infer_behavior_batch): COORDINATORs and CONTROLLERs correctly identified
     across agent_tools.py; INTERFACER for evaluate() accurate (thin LLM boundary).
   - match_structural_pattern: evaluator primitives return UNCERTAIN/STRUCTURER at radius=2;
     subgraphs too sparse for 3B model to reason about. agent_tools symbols had 1-node
     subgraphs due to stale inbound edges -- fixed by reingesting caller files.
   - check_design_violations: SOTS XI flagged on evaluate() (score 0.30) -- filed as item 28.
     SOTS XXIV on collect_symbol_context (reproducibility), XVI on check_design_violations
     (least privilege), XVIII on infer_behavior (observability) -- all borderline, low priority.

---

28. **[DONE â€” already implemented, confirmed session 67] SOTS XI: separate "decide to call LLM" from "call LLM" in evaluate()**

   **Source:** Self-review 2026-07-03. check_design_violations flagged SOTS XI on
   `determined.agent.evaluator.evaluate` (score 0.30).

   **What SOTS XI says:** "Separate the irreversible decision from its effect -- make
   'should we / which ones' a pure, exhaustively-testable function that returns a plan;
   make the doing a thin wrapper that only executes the plan."

   **The issue:** `evaluate()` currently does both: it builds the prompt, decides on
   the LLM call shape (question + evidence), and executes the LLM call in one step.
   The "decide" part (what to send, which evidence to include) is not separately testable
   without triggering an actual LLM call.

   **What to change:**
   - Extract a pure `build_eval_request(context, evidence, question) -> EvalRequest` that
     returns the prompt and parameters as a data structure (no LLM call).
   - `evaluate()` becomes: `build_eval_request(...)` then `_call_llm(request)` then
     `_parse_judgment(response)`.
   - Tests can exercise `build_eval_request` directly and verify prompt shape without
     mocking the LLM.

   **Priority:** Low. The current code is correct; this is a testability improvement.
   Worth doing before evaluate() grows more complexity.

---

19. **[DONE 2026-06-28] Design intent layer: check_design_violations + self-audit**

   The tool analyzes code structure but has no awareness of what the code is *supposed*
   to do. Design docs (architectural constitutions, subsystem specs, authority boundaries)
   are the authoritative intent for a project -- currently they live entirely outside
   the tool's knowledge layer.

   **The gap:** The tool can find that dm_chat_handler.py bypasses the authority layer,
   but cannot tell you *why* that's wrong or what the correct boundary is. Design intent
   has no representation in knowledge.db.

   **What this enables:**
   - Ingest design docs (markdown) as a separate artifact class alongside code
   - Extract aspirational constraints: authority boundaries, layer rules, forbidden patterns,
     named invariants, "must not" / "only X may" rules
   - Cross-reference code findings against design intent:
     "This symbol violates a documented boundary" not just "this symbol calls that one"
   - Surface drift: "ContextBuilder re-resolves entities -- constitution says it must not"
   - Inform every "where does this go" coding decision without dictating order

   **Nature of this item:** Living, aspirational, off-and-on. Not a one-time feature --
   a capability that deepens as the tool matures. Early stab: extract key constraints
   from design docs into knowledge_artifacts (kind=design_note, provenance=human-confirmed).
   Later: automated cross-reference against structural findings.

   **First concrete step:** Write a doc extractor that reads markdown design docs,
   pulls out named invariants and authority rules, and stores them as human-confirmed
   design_note artifacts scoped to the corpus. Then wire findings to check against them.

   **Primary target docs (dj2 corpus, all committed 2026-06-26):**
   - `docs/design/00A ARCHITECTURAL_CONSTITUTION.md` - the authority hierarchy and invariants
   - `docs/design/00B SYSTEM_CONSTRAINTS.md` - hard constraints
   - `docs/design/00F ASPIRATIONAL_DESIGN_INTENT.md` - authority boundaries (section B), AI DM
     vision (section C), world architecture (section D); section H explicitly describes what
     Determined should eventually extract and cross-reference from these docs
   - `docs/design/00E AI_LAYER_OPPORTUNITIES.md` - AI layer constraints and patterns

   When dj2 is the active corpus, these docs are the authoritative intent surface.
   The extractor should prioritize "must not", "only X may", "never", "must" phrases
   in these docs as the highest-signal invariants to store as design_note artifacts.

   **Why HIGH:** Without this, the tool cannot help maintain design integrity as code
   grows. It finds structural facts but misses the most important class of bugs:
   architectural violations.

1. **[DONE 2026-06-29] `files.role` classification** - `_classify_role()` added to
   `parse_ast.py`. Assigns "test", "entry_point", "init", "config", or "module"
   based on path/content heuristics. `find_files(role=...)` now works.
   Migration guards removed from persistence_engine (no persistent DBs - schema
   is the only authority; `param_types_json` moved into CREATE TABLE).

2. **[SUPERSEDED by item 22] `search_symbols` scope** - addressed by wide concept
   search design (item 22). Name-only match stays as the locator; concept search
   is a separate tool.

3. **[SUPERSEDED by item 23] `missing_docstrings` limit** - addressed by docstring
   health campaign design (item 23). Full coverage reporting + staleness detection
   + editor write-back replaces the capped list.

6. **[DONE 2026-06-29] Live sync loop: incremental per-file re-ingest** -
   reingest_file() in determined/ingestion/reingest_file.py. FileDelta scratchpad
   (in-memory), INSERT OR IGNORE fix in _insert_symbol, agent tool + CLI wired.
   6 regression tests.

7. **[DONE 2026-06-29] Contracts reconciliation and wiring** -
   Fixed "domains" vs "modules" key mismatch in scan_contract.py/parse_contract.py.
   Wired ContractRuntimeValidator (JSON stage invariants) into ingest post-pass.
   Completed drift pipeline: DriftClassifier -> HealthAggregator -> LifecycleController.
   violations -> contract_violations table; signals -> contract_drift_history on every
   ingest. stability_view now returns lifecycle states (ACTIVE/STABLE/DEGRADING/etc).

8. **[DONE 2026-06-28] Auto-populate semantic summaries at ingestion**

   `--summarize` flag added to `local_agent --source`. After ingestion and
   structural fact extraction, iterates all corpus files and calls
   semantic_summary() for each. Skips already-cached. Aborts gracefully on
   Ollama connection failure with count of summaries written. 297/297 passing.

9. **[DONE 2026-06-28] Distillation pass** -
   `semantic_summaries` and `file_purpose` artifacts store 3-4 paragraph LLM
   responses verbatim. Add a distillation step: pass each verbose blob back to
   Ollama with a compression prompt ("one sentence: what does this file/symbol
   do?") and store the result as a separate `distilled` kind in
   `knowledge_artifacts`. The distilled form is what `symbol_brief` and the
   agent resolver use as a quick-scan; the verbose form stays for full context.
   Subject naming convention: `distilled::<subject>`.

10. **[DONE 2026-06-28] Tool chaining: structured output mode** - every tool returns a
    string (right for LLM consumption). When one tool's output drives another
    programmatically (e.g. `list_callers` -> `risk_profile` for each caller,
    or `graph_subgraph` nodes -> `symbol_intent` for each node), the agent has
    to re-parse its own text. Add an internal `_raw` variant for key tools that
    returns structured data (list of dicts), used by agent_resolver's auto-
    expansion phase (phase 2b) instead of text-parsing. External API stays
    string-only. Affected tools: `list_callers`, `list_callees`,
    `graph_most_connected`, `graph_subgraph`, `search_symbols`.

20. **[DONE 2026-06-29] Call graph accuracy: type annotation exploitation + __init__ attribute tracking**

   Motivated by PyAnalyzer (ICSE 2024, Jin et al.) which achieves +24.7% F1 over
   comparable static analysis tools by modeling functions/classes/modules as heap
   objects. A full heap model is ~6-10 weeks and unnecessary given Determined's LLM
   reasoning layer. Two targeted improvements give 60-70% of the gain at ~5% cost.

   **Phase 1 -- Capture annotation data at parse time (schema + ingestion):**
   - `parse_ast.py` `_extract_functions`: capture `arg.annotation` for each parameter
     alongside `arg.arg`. Store as `param_types_json TEXT` column on `functions` table
     (JSON dict `{"param": "TypeStr"}`). Already captures `return_type`; this adds
     param types.
   - New `_extract_class_attributes` pass: for each `ClassDef`, find `__init__`,
     walk its body for `ast.Assign`/`ast.AnnAssign` where target is `self.x`.
     Extract inferred type from `Foo()` constructor calls or explicit annotations.
     Store in new `class_attributes` table:
     `(id, file_path, class_name, attribute, inferred_type)`
   - `persistence_engine.initialize_database`: add `class_attributes` table,
     ALTER TABLE guard for `functions.param_types_json`.

   **Phase 2 -- Use annotations in call edge resolution:**
   - In `parse_ast.py` `_extract_symbol_references` `Visitor.visit_Call`:
     when receiver is `obj.method()`, look up `obj` in current function's
     param annotation map. If `obj: Foo` is annotated, emit callee as `Foo.method`
     instead of bare `obj.method`.
   - If receiver is `self.attr`, look up `attr` in `class_attributes` for the
     current class. Emit `InferredType.method`.
   - Add `resolved INTEGER DEFAULT 0` to `graph_edges` (1 = annotation-derived,
     0 = heuristic name match).

   **Phase 3 -- Surface confidence in agent tools:**
   - `list_callers`/`list_callees`: tag edges with `(resolved)` vs `(inferred)`.
   - `describe_file`: report % of outbound edges that are annotation-resolved.
   - New DBOracle helper: `get_class_attribute_type(class_name, attr)`.

   **Why MEDIUM not HIGH:** LLM layer compensates for some graph inaccuracy.
   Highest value on dynamic-dispatch-heavy codebases; dj2/harrow are well-structured.
   Do after item 6 (live sync) since re-ingest is needed to populate new columns.

   **Estimated effort:** ~2 days. Order: schema (1c) -> param annotations (1a) ->
   __init__ attributes (1b) -> call resolution (2) -> agent tools (3).

11. **[FUTURE] Trace-weighted ranking** - replace heuristic scoring with
    trace-weighted ranking from expansion provenance. After real usage patterns
    are clear.

---

RM11. **[DONE 2026-07-05] edit_file agent tool: close the readâ†’reasonâ†’write loop**

   `edit_file(assessor, args)` in `agent_tools.py`. Three ops: `read_file`,
   `write_file`, `replace_in_file`. Path-boundary guard against project root.
   Wired into TOOLS dict and tool_registry.py. 12 regression tests pass.
   Full agentic loop now closed: goal_intake â†’ evaluate â†’ propose â†’ edit_file â†’
   reingest_file â†’ check_design_violations.

---

RM12. **[DONE 2026-07-05] Web search: SearXNG integration**

   `search_web(assessor, args)` in `agent_tools.py`. Hits SearXNG `/search?format=json`,
   returns top-N results as formatted title/URL/snippet text (snippet truncated at 200 chars).
   `SEARXNG_URL` config in `llm_client.py` (default `http://localhost:8888`; None = disabled).
   Graceful degradation on unreachable server. Wired into TOOLS and tool_registry.py
   (category: external). 10 regression tests pass. SearXNG is user-run (Docker or standalone);
   Determined just consumes the JSON API.

---

RM10. **[FUTURE] DeRe-CoT recomposition pass in goal_intake**

   `goal_intake` currently decomposes a natural-language goal into sub-queries
   and retrieves relevant symbols for each. It has no recomposition or coherence
   verification step -- it cannot confirm that the sub-queries together actually
   cover the original goal.

   **Source:** "Automatic prompt generation via semantic decomposition-and-recomposition
   for multi-hop question answering" (Seungyeon Lee & Dong-Gyu Lee, Engineering
   Applications of Artificial Intelligence, Vol. 181, Part 3, October 2026).

   **The DeRe-CoT mechanism:**
   1. Decompose the goal into N candidate single-hop sub-questions (currently done)
   2. Recompose pairs of candidates into new composite questions
   3. Compute semantic similarity between each recomposed question and the original goal
   4. Select the sub-question pair with highest alignment as the canonical decomposition
   5. Proceed with that pair -- not the original arbitrary decomposition

   **Why this matters for Determined:** goal_intake's decomposition is currently
   unchecked. A goal like "find where the AI boundary is violated" could decompose
   into sub-queries that individually make sense but miss the core constraint. The
   recompose-then-select step verifies coherence before committing to a reasoning path.

   **Related frameworks also shared by Bart (for context, not separate items):**
   - 4-phase decomposition: Goal Formulation -> Semantic Factoring -> Sequential
     Planning -> Unit Execution. Strategies: CoT, DECOMP, ToT.
   - Deterministic + semantic decomposition: deterministic skeleton (constraint
     satisfaction, idempotent subtasks) + semantic brain (meaning-based chunking,
     hierarchical parsing).
   - ACONIC: models tasks as constraint problems using formal complexity measures
     (graph size, tree-width) to guide decomposition granularity.

   **Prerequisite:** flat goal_intake must be proving insufficient in practice
   before adding this complexity. Do not implement speculatively.

   **Effort:** Medium. Recomposition is a second LLM pass (3B model, fast).
   Semantic similarity uses the existing embedding infrastructure.
   See [[project-analysis-workflow]] for full paper details.

14. **[DONE 2026-07-01] Semantic speculative decoding** - once item 10 (structured output)
    is in place, explore using the 3B model as a reasoning-step predictor: 3B
    predicts which tools/symbols/docs are needed, Oracle fetches them, 8B reasons
    only over the pre-assembled result. Analogous to token-level speculative
    decoding but at the semantic level. Revisit after item 10 is shipped and
    real usage patterns show where the 8B is spending time unnecessarily.

13. **[FUTURE] Self-Harness pattern** - the corpus DB (knowledge_artifacts) is the
    natural store for harvested failure patterns. After ADVERSARIAL traces accumulate,
    mine them into `known_issue` artifacts keyed by failure category, then use those
    artifacts to tune agent_resolver heuristics. Loop: ADVERSARIAL run ->
    extract failure patterns -> store as known_issue -> harness reads on next
    run -> better routing. Closes the improvement loop without touching Ollama.

---

### LLAMA-SERVER MIGRATION (session 36, 2026-06-29)

Ollama is ethically compromised (early exploiter of llama.cpp open source project).
Replacing it with llama-server â€” the OpenAI-compatible server built directly into
llama.cpp itself. No wrapper, no company, pure llama.cpp output.

**Infrastructure already in place:**
- `llama-server.exe` (b9842, CPU): `C:\Users\bartl\models\llama-server\llama-server.exe`
- Model: `C:\Users\bartl\models\gguf\llama3.2-3b.gguf` (2.02 GB, extracted from Ollama blob,
  same GGUF format â€” no conversion needed)
- Start: `llama-server.exe -m C:\Users\bartl\models\gguf\llama3.2-3b.gguf --port 8080 --ctx-size 2048`
- Health: `http://localhost:8080/health` â†’ `{"status":"ok"}` (verified)
- API: `/v1/chat/completions` and `/v1/completions` (OpenAI-compatible)

**After item 25 is done and tested:** uninstall Ollama, delete `~/.ollama/models/blobs/` (~50GB).

---

25. **[DONE 2026-07-01] LLM backend: replace Ollama call sites with llama-server shim**

    All Ollama HTTP calls in Determined use one of two request shapes against
    `http://localhost:11434`. Replace with a thin `llm_client.py` module that
    targets `http://localhost:8080` (llama-server) and normalizes the response
    shape. Six call-site files updated to import from the shim instead.

    **Two Ollama API shapes in use (with their llama-server equivalents):**

    Shape 1 â€” `/api/generate` â†’ `/v1/completions`:
    ```python
    # OLD
    requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.json()["response"]
    # NEW
    requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.json()["choices"][0]["text"]
    ```

    Shape 2 â€” `/api/chat` â†’ `/v1/chat/completions`:
    ```python
    # OLD
    requests.post(OLLAMA_URL, json={"model": MODEL, "messages": [...], "stream": False})
    resp.json()["message"]["content"]
    # NEW
    requests.post(url, json={"model": MODEL, "messages": [...], "stream": False})
    resp.json()["choices"][0]["message"]["content"]
    ```

    **New file: `determined/agent/llm_client.py`**
    Two public functions, everything else stays the same:
    ```python
    LLM_URL   = "http://localhost:8080"
    LLM_MODEL = "llama3.2-3b"      # filename stem, no .gguf
    LLM_TIMEOUT = 60

    def generate(prompt: str, timeout: int = LLM_TIMEOUT) -> str | None:
        """Shape 1 â€” single prompt, returns text or None on failure."""

    def chat(messages: list[dict], timeout: int = LLM_TIMEOUT) -> str | None:
        """Shape 2 â€” message list, returns content string or None on failure."""
    ```

    **Six files to update (search-replace OLLAMA_URL/OLLAMA_MODEL/OLLAMA_TIMEOUT
    imports and response parsing):**
    - `determined/intent/semantic_summary.py` â€” Shape 1, `_generate()`
    - `determined/agent/agent_tools.py` â€” Shape 1, `_distill_one()` (line 372) and
      `_synthesize_with_ollama()` (line 1787)
    - `determined/agent/stub_projector.py` â€” Shape 1, `_call_ollama()` (line 179)
    - `determined/agent/doc_extractor.py` â€” Shape 2, line 370
    - `determined/agent/local_agent.py` â€” Shape 2, `_call_ollama()` (line 327);
      also update `PatternExecutor` init at line 371 and health/warmup refs
    - `determined/ui/ui_server.py` â€” Shape 2 (line 232), `_check_ollama()`,
      `_warmup_ollama()` â€” rename to `_check_llm()`, `_warmup_llm()`

    **Also update:** `determined/assessor/query_compiler.py` â€” Shape 1,
    `_compile_via_ollama()` (line 251) â†’ `_compile_via_llm()`.
    `determined/agent/pattern_executor.py` â€” remove `ollama_url/model/timeout`
    constructor args; import from `llm_client` instead.

    **Health check update in `ui_server.py`:** replace Ollama model-list check
    (`/api/tags`) with llama-server health check (`GET /health` â†’ `{"status":"ok"}`).

    **Test:** run full regression suite after swap. All 323 tests should still pass
    (most don't hit the LLM; the ones that mock it stay mocked). Manual smoke test:
    start llama-server, run `local_agent.py --ui`, ask a question.

---

26. **[DONE 2026-07-01] Model file management: document and maintain GGUF library**

    Ollama managed model downloads and storage. With llama-server we own the files
    directly. This item covers the transition and ongoing model management.

    **Immediate:** after item 25 verified working end-to-end â€” uninstall Ollama,
    delete `C:\Users\bartl\.ollama\` (reclaims ~50GB of blob storage).

    **Current GGUF library:** `C:\Users\bartl\models\gguf\`
    - `llama3.2-3b.gguf` â€” primary inference model (item 25)

    **Other models from Ollama library** (blobs exist, not yet extracted):
    Extract same way â€” read manifest, copy blob, rename `.gguf`.
    Manifests at `~/.ollama/models/manifests/registry.ollama.ai/library/`:
    - `llama3.2/latest` â€” same as 3b
    - `llama3.1/latest` â€” 8B model (~4.7GB blob)
    - `codellama/7b`, `codellama/13b`
    - `mistral/7b`
    - `qwen2.5/7b`, `qwen2.5-coder/1.5b`, `qwen2.5-coder/latest`
    - `qwen3.5/35b` â€” large model
    - `gemma3/4b`

    **Model management going forward:** download GGUF files directly from
    HuggingFace (TheBloke / bartowski quantizations are standard sources).
    No model manager needed â€” files are just files.

    **llm_client.py config:** `LLM_MODEL` should match the GGUF filename stem
    OR be ignored entirely (llama-server serves whichever model it was started
    with â€” the model param in the request is advisory, not a selector).
    Simplest: remove model name from request payload since llama-server ignores it.

---

### ASSISTANT ARC (session 36, 2026-06-29)

The tool has matured from an oracle (answer queries) to an assistant (surface gaps,
propose changes, support review). These four items build the assistant capability
layer on top of the existing structural knowledge foundation.

**What these build on (concrete infrastructure â€” read before building any of 21-24):**

Embedding: `determined/oracle/embedding_model.py` â€” `embed_text(str) -> np.ndarray`,
`cosine_similarity(a, b) -> float`. Lazy-loads `all-MiniLM-L6-v2` on first call.
In agent_tools.py the model is cached as `_get_embed_model()`; batch encode via
`model.encode([...], normalize_embeddings=True)`, dot product gives cosine similarity.

Design frame pattern: `_get_design_frame(assessor, symbol, file_path)` at
agent_tools.py:394 â€” builds query string from symbol+file stem+docstring, calls
`search_tenets(query, threshold=0.32, top_n=3)` from `determined/data/sots_loader.py`.
This is the reusable pattern for "embed context, cosine-search a knowledge surface."

Design violations pattern: `_check_design_violations_core(assessor, symbol, file_path)`
at agent_tools.py:504 â€” same embed+cosine-search pattern but richer query
(symbol+docstring+callee names+file stem) and searches `design_notes` at threshold 0.30.

Distilled summaries: stored in `semantic_summaries` table, `distilled` column.
Query: `SELECT distilled FROM semantic_summaries WHERE subject LIKE ? AND distilled IS NOT NULL`.
Subject is the file path. Also stored as `kind='distilled'` in `knowledge_artifacts`
with subject `distilled::<name>`. Both stores exist; `semantic_summaries.distilled`
is the primary one used by `symbol_brief` and `goal_intake`.

Goal intake semantic search pattern (agent_tools.py:1454-1484): loads all symbols
with docstrings via `_search_symbols_raw(oracle, "", limit=600)`, enriches each
with distilled file summary, batch-encodes all + the goal query together, ranks by
dot product. Threshold 0.28. This is the reusable pattern for conceptâ†’symbol matching.

Review queue: `determined/intent/workflow_store.py` â€” `add_item(conn, kind, subject,
content, provenance="human")`. Use `provenance="llm-proposed"` for machine-generated
proposals. `kind="next_up"` for actionable items. `update_item(conn, id, status="done")`
to accept. `status="deferred"` to dismiss. Table is `workflow_items` in the corpus DB.

Symbol references: `symbols` table has `symbol_type` values `function`/`class`
(declarations) and `caller`/`callee` (call-graph participants). `graph_edges` has
`caller`, `callee`, `caller_file`, `line_number`, `resolved`. `symbol_references`
table has `caller`, `callee`, `file_path`, `line_number`. All three needed for
find-references (item 21): declarations from `symbols`, usages from `symbol_references`.

Class attributes: `class_attributes` table â€” `(file_path, class_name, attribute,
inferred_type)`. Added in item 20. Used in item 21 for class attribute listing.

Risk scoring: `determined/agent/risk_annotator.py` â€” `score_risk(oracle, symbol)`
returns dict with `level` (HOT/WARM/SAFE), `reasons` list. Already used in `goal_intake`
and `risk_profile`. Import: `from determined.agent.risk_annotator import score_risk`.

---

21. **[DONE 2026-06-30] Symbol context view** â€” `symbol_context(assessor, args)` in agent_tools.py.
    Single call returns declaration, docstring, risk badge, find-references, callers/callees,
    class attributes, design frame, and stored findings. understand_symbol task pattern
    updated to single step. Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern.

---

22. **[DONE 2026-06-30] Wide concept search** â€” `concept_search(assessor, args)` in agent_tools.py.
    Searches symbol names, docstrings, behavioral contracts, design notes, distilled summaries.
    Semantic re-ranking via all-MiniLM-L6-v2 at threshold 0.25. Grouped output by surface.
    Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern.

---

23. **[DONE 2026-06-30] Docstring health â€” campaign tool** â€” surfaces missing and stale docstrings,
    proposes fills, supports editor write-back. New function `docstring_health(assessor, args)`
    in agent_tools.py. Optional args: `file` (scope to one file), `module` (scope to
    path prefix), `propose` (bool, default True â€” generate proposals and store in queue).

    **Missing detection:**
    ```sql
    SELECT name, file_path, line_number FROM functions
    WHERE (docstring IS NULL OR docstring = '')
    [AND file_path LIKE ? if scoped]
    ORDER BY file_path, line_number
    ```
    Same for `classes`. No limit. Always show total count.

    **Staleness detection:** for symbols WITH docstrings, retrieve `distilled` from
    `semantic_summaries` for their file. Embed both the existing docstring and the
    distilled summary using `embed_text()` from `determined/oracle/embedding_model.py`.
    `cosine_similarity(embed_text(docstring), embed_text(distilled))` â€” low score
    (< 0.55, tune empirically) = potentially stale. Report score alongside each flagged
    symbol so developer can judge. High distance = docstring and code diverged.

    **Proposal generation:** for each missing or stale symbol, look up distilled text:
    `SELECT distilled FROM semantic_summaries WHERE subject = ? AND distilled IS NOT NULL`
    (subject is file_path). If found, call `workflow_store.add_item(conn, kind="next_up",
    subject=f"docstring::{file_path}::{name}", content=distilled_text,
    provenance="llm-proposed")`. Store file_path and line_number in content as JSON
    so write-back knows where to go.

    **Editor-launch (UI layer):** `ui_server.py` â€” when user clicks a proposed docstring
    item in the work queue, open an inline editor pre-filled with the proposed text.
    On accept: write the text as a docstring to the source file at the stored line_number,
    call `workflow_store.update_item(conn, id, status="done")`. On reject: status="deferred".

    **Confidence display:** show cosine distance score alongside each stale flag.
    Score >= 0.80: likely fine. 0.55-0.80: review. < 0.55: flag as stale.
    Missing symbols get no score (N/A â€” no existing docstring to compare).

    **UI tab:** add `"docstring_health"` to `_TAB_TOOLS` in `ui_server.py` alongside
    the existing `"docstrings"` tab (which can be retired or repurposed as a summary).

---

24. **[DONE 2026-06-30] On-demand gap analysis with standing summary** â€” two-tier capability:
    a fast standing summary always available, and a deep on-demand analysis.

    **Gap summary (fast, DB-only, no LLM):** new section in `knowledge_status` output
    (agent_tools.py ~line 1023). Runs these heuristics via SQL:
    - Docstring coverage: `SELECT COUNT(*) FROM functions WHERE docstring IS NULL` /
      total. Per-module breakdown (group by first path segment).
    - Distillation coverage: `SELECT COUNT(*) FROM semantic_summaries WHERE distilled IS NOT NULL`
      / total files.
    - Design note coverage: count `knowledge_artifacts` where `kind='design_note'` per module.
      Modules with 0 design notes flagged as undocumented.
    - Pattern gaps (hardcoded heuristics for now): e.g. check if `files` table has any
      non-NULL `role` values (item 1 just landed â€” verify it's populating).
    Output: short text block "GAPS AT A GLANCE" with module-level counts and flags.
    No LLM. Fast enough to include in session startup output.

    **Full gap analysis (on-demand, LLM via Ollama):** new tool `gap_analysis(assessor, args)`
    in agent_tools.py. Optional args: `file`, `module`, `symbol` to scope. No args = uses
    gap summary to pick highest-signal area automatically.

    Scoped analysis steps:
    1. Collect what exists in the scoped area: symbols, their types, docstrings, design notes,
       behavioral contracts, risk scores.
    2. Collect what exists in analogous areas (same module pattern elsewhere in the corpus).
    3. Prompt Ollama (3B model via `assessor._ollama_generate()` or equivalent) with:
       "Here is what exists in [area]. Here is the pattern in analogous areas. What is
       missing, incomplete, or could bridge these areas? Propose typed fills: extend,
       bridge, mirror, consolidate."
    4. Parse response into a list of proposals. Store each as `workflow_store.add_item(
       conn, kind="backlog", subject=f"gap::{area}", content=proposal_text,
       provenance="llm-proposed")`.

    **Key constraints:**
    - NOT automatic. User-initiated. Menu option in UI sidebar or agent command.
    - Output is idea-mode â€” explicitly framed as possibilities, not prescriptions.
      Prefix output: "GAP ANALYSIS (generative â€” proposals may be off target):"
    - Ollama call uses 3B model (fast), not 8B. This is brainstorming, not reasoning.
    - Gap summary is the navigation layer: read it first to know where to focus the
      full analysis. Full analysis on a well-covered area will produce noise.

---

### MENTOR CAPABILITY ARC (session 26, 2026-06-27)

The goal of Determined is to approximate what Claude does when a developer brings
it an unfamiliar codebase: orient quickly, identify what is dangerous vs safe,
surface mismatches between design intent and code reality, and guide the developer
toward the right approach for their goal. Not answer queries - navigate.

This requires three capabilities that do not yet exist, plus one prerequisite.
All four build on existing infrastructure rather than replacing it.

**What the tool already has that these build on:**
- knowledge_artifacts (design_note kind) - foundation for design intent storage
- pattern_executor + orient_to_codebase - structured orientation, extendable
- risk_annotator - already scores hot/warm/safe per symbol
- stub detection - already knows what scaffolding exists but is unimplemented
- bag_store - already accumulates session context across queries
- mine_design_docs.py - hand-authored design notes in the right shape, wrong source

**The 3B model's role:** connector of pieces, not memory. DB holds structured
knowledge; the model reasons over what it is given. Architecture is: assemble
the right context for each step, let the model connect it.

---

22. **[DONE 2026-06-28] Design doc extraction: auto-mine markdown into design_note artifacts**

   Shipped as `ingest_design_docs` tool and `discover_docs` tool in agent_tools.py.
   discover_docs scans project for markdown with constraint density scoring.
   ingest_design_docs uses the 3B model (Ollama) to extract named invariants, authority
   rules, forbidden patterns from those docs and stores as design_note artifacts
   (provenance=llm-extracted). Re-running is idempotent. Wired into TOOLS and REGISTRY.

---

23. **[DONE 2026-06-28] Frame comparison: surface design intent automatically when code touches documented areas**

   Rebuilt session 30 on semantic embeddings (all-MiniLM-L6-v2). _get_design_frame()
   embeds symbol+docstring context, cosine-searches all design_notes in knowledge.db
   (threshold 0.32). Query enriched with docstring so abstract principle text (SOTS)
   surfaces alongside project-specific constraints. Replaces fragile string matching.
   320/322 passing (2 pre-existing failures, unrelated).

---

24. **[DONE 2026-06-28] Goal intake: developer states intent, tool assembles goal-directed context**

   goal_intake(goal) in agent_tools.py. Takes natural language goal, returns navigation plan:
   - Semantic search over symbol docstrings -> top 5 relevant symbols
   - HOT/WARM/SAFE risk badge for each
   - Design rules from knowledge.db (SOTS + project notes) semantically matched to goal
   - Uncalled functions near relevant files as safe insertion candidates
   - Ordered approach: READ (hot boundaries) -> REVIEW (warm) -> EXTEND (stubs) -> MODIFY (safe)

   Trigger phrase: "I want to add/build/implement/create/extend X"
   Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern. 320/322 passing.

---

25. **[DONE 2026-06-28] Corpus map: merged and shipped**

   Branch ui/corpus-map merged to main and branch deleted. Corpus map panel
   (Roots/Core with risk badges, collapsible) is live in the UI.

---

## Chronological session log

See `git log` for full session history. HISTORY.md (docs/HISTORY.md) is a curated
decision log -- non-obvious choices, failed approaches, surprises still live.
