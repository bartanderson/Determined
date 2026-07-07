tools/analysis - TRACKER (consolidated)
=========================================

This file is the canonical open-items list and at-a-glance status for the
Determined analysis tool. Active open items only. For closed items, phase
plans, tier status, UI vision, branch methodology, and environment defects,
see docs/archive/TRACKER_history.md. For historical context, use git log.
For architecture/intent (the why behind the design), see DESIGN.md.

Per CLAUDE.md's working agreement: update this file in place as part of
finishing work (checkboxes, dated notes) so Bart can see what changed via
`git diff`, and so a future session doesn't need conversation history to
know where things stand.

---

## Dashboard - at a glance

**Last session (2026-07-05, session 82):** Clarified Commonplace work arc. COMMONPLACE_VISION.md updated with clear framing. RM15 filed as next active item.

**Session 81 (2026-07-05):** Sidebar icon-nav shipped. 4-icon rail (Corpus/Navigate/Tools/Ask) replaces flat sidebar. Corpus panel: analyze + corpus map + gaps. Navigate panel: 6 start-here shortcuts only. Collapse to rail-only on active icon click. 436 passed, 1 skipped.

**Session 67 (2026-07-04):** Item 28 confirmed already done. RM6 + RM7 benchmarked with live 8B. ABC Frontier mode verified in browser (8 classes, 35 methods). reason_about full pipeline fired end-to-end (Decompose → DB → evaluate() → Synthesize). launch.json fixed. 399 tests pass.

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

RM19. **[FILED 2026-07-07] Semantic Reconciliation Arc: duplicate detection, intent differencing, primitive discovery**

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
   Mine the call graph for repeated compositions: sequences A→B→C→D that appear across
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

   **Tractability order:** Pass 1 (one session) → Pass 2 (one session) → Pass 3 (two sessions).
   Passes 4 and 5 get their own items after the first three prove out.

   **What to build on:** `determined/oracle/embedding_model.py` (embed_text, cosine_similarity),
   `graph_edges` table, `knowledge_artifacts` (kind=reconciliation_finding),
   `workflow_items` (kind=backlog, provenance=llm-proposed).

---

RM18. **[ACTIVE] Act on RM17 gaps**

   Priority order from RM17 findings: Gap 2 → Gap 10 → Gap 1.

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

   **Next:** RM18 -- act on gaps. Priority order: Gap 2 (Flask entry-point heuristic, easy) → Gap 10 (auto-discover design docs on corpus load) → Gap 1 (structured layer-rule violations).

---

RM17_archive. **[ACTIVE text below, archived]** Two-pass cold analysis of Commonplace: find tool blind spots

   Two-pass examination of the Commonplace corpus to find what Determined gets
   right, wrong, and can't see at all. Output is a ranked list of gaps.

   **Pass 1 — cold read (tool output only):**
   Load Commonplace full corpus. Walk orient → frontier → topology → spotlight
   queries → knowledge. Write down exactly what Determined says the codebase is.
   No looking at source. Pure tool output.

   **Pass 2 — adversarial read (source truth):**
   Read the actual Commonplace source files directly. Independently form a picture
   of what the codebase is and does. Do not reference Pass 1 output while reading.

   **Compare — rub them together:**
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

RM15. **[ACTIVE] Commonplace guided journey: run it for real, fix Determined iteratively**

   The next active work arc. Full description in docs/COMMONPLACE_VISION.md.

   **Two entry paths:**
   - Easy path: start from the seed skeleton, use Determined to fill it out
   - Hardcore path: build the seed from scratch with Determined open, ingest
     as you go, write-reingest-read-frontier loop IS the workflow

   Both paths converge at seed, then continue to complete, then enhance
   (wire tagger to llama-server, add semantic search, connection inference).

   **How to work this item:**
   Start the server. Point Determined at seed (or blank dir). Walk the
   COMMONPLACE_VISION.md journey steps. When something breaks or feels rough,
   fix Determined. Continue. Iterative -- not a one-shot audit.

   **Pending housekeeping before starting:**
   - Run ingest_design_docs via the UI to repopulate dj2 design notes
     (all 268 purged session 79; DB empty for kind=design_note until re-run)

---

RM14. **[DONE 2026-07-05] Sidebar icon-nav**

   4-icon vertical rail (🗄 Corpus / 🧭 Navigate / 🔧 Tools / 💬 Ask) replaces
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

   **Implementation (session 66):** `find_abc_gaps()` in agent_tools.py — queries classes
   with base_classes_json containing 'ABC'/'Abstract', joins to functions to find stub methods,
   checks for non-stub overrides elsewhere. No new schema needed: existing `classes.base_classes_json`
   + `functions.is_stub` + `functions.file_path` are sufficient. Proxy heuristic (stub on ABC class
   = abstract) works well in practice. On dj2: 35 unimplemented abstract methods across 8 classes.
   Wired as agent tool `find_abc_gaps`, registry entry, test file (5 tests). Frontier tab gains
   "ABC (interface gaps)" mode — purple diamond nodes for abstract classes, red stubs for methods.
   Multi-level inheritance not handled (deferred — not needed for current corpora).

---

27. **[FUTURE] Standards-grounded self-review: audit Determined's own design against established patterns**

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

28. **[DONE — already implemented, confirmed session 67] SOTS XI: separate "decide to call LLM" from "call LLM" in evaluate()**

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

RM11. **[DONE 2026-07-05] edit_file agent tool: close the read→reason→write loop**

   `edit_file(assessor, args)` in `agent_tools.py`. Three ops: `read_file`,
   `write_file`, `replace_in_file`. Path-boundary guard against project root.
   Wired into TOOLS dict and tool_registry.py. 12 regression tests pass.
   Full agentic loop now closed: goal_intake → evaluate → propose → edit_file →
   reingest_file → check_design_violations.

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
Replacing it with llama-server — the OpenAI-compatible server built directly into
llama.cpp itself. No wrapper, no company, pure llama.cpp output.

**Infrastructure already in place:**
- `llama-server.exe` (b9842, CPU): `C:\Users\bartl\models\llama-server\llama-server.exe`
- Model: `C:\Users\bartl\models\gguf\llama3.2-3b.gguf` (2.02 GB, extracted from Ollama blob,
  same GGUF format — no conversion needed)
- Start: `llama-server.exe -m C:\Users\bartl\models\gguf\llama3.2-3b.gguf --port 8080 --ctx-size 2048`
- Health: `http://localhost:8080/health` → `{"status":"ok"}` (verified)
- API: `/v1/chat/completions` and `/v1/completions` (OpenAI-compatible)

**After item 25 is done and tested:** uninstall Ollama, delete `~/.ollama/models/blobs/` (~50GB).

---

25. **[DONE 2026-07-01] LLM backend: replace Ollama call sites with llama-server shim**

    All Ollama HTTP calls in Determined use one of two request shapes against
    `http://localhost:11434`. Replace with a thin `llm_client.py` module that
    targets `http://localhost:8080` (llama-server) and normalizes the response
    shape. Six call-site files updated to import from the shim instead.

    **Two Ollama API shapes in use (with their llama-server equivalents):**

    Shape 1 — `/api/generate` → `/v1/completions`:
    ```python
    # OLD
    requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.json()["response"]
    # NEW
    requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.json()["choices"][0]["text"]
    ```

    Shape 2 — `/api/chat` → `/v1/chat/completions`:
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
        """Shape 1 — single prompt, returns text or None on failure."""

    def chat(messages: list[dict], timeout: int = LLM_TIMEOUT) -> str | None:
        """Shape 2 — message list, returns content string or None on failure."""
    ```

    **Six files to update (search-replace OLLAMA_URL/OLLAMA_MODEL/OLLAMA_TIMEOUT
    imports and response parsing):**
    - `determined/intent/semantic_summary.py` — Shape 1, `_generate()`
    - `determined/agent/agent_tools.py` — Shape 1, `_distill_one()` (line 372) and
      `_synthesize_with_ollama()` (line 1787)
    - `determined/agent/stub_projector.py` — Shape 1, `_call_ollama()` (line 179)
    - `determined/agent/doc_extractor.py` — Shape 2, line 370
    - `determined/agent/local_agent.py` — Shape 2, `_call_ollama()` (line 327);
      also update `PatternExecutor` init at line 371 and health/warmup refs
    - `determined/ui/ui_server.py` — Shape 2 (line 232), `_check_ollama()`,
      `_warmup_ollama()` — rename to `_check_llm()`, `_warmup_llm()`

    **Also update:** `determined/assessor/query_compiler.py` — Shape 1,
    `_compile_via_ollama()` (line 251) → `_compile_via_llm()`.
    `determined/agent/pattern_executor.py` — remove `ollama_url/model/timeout`
    constructor args; import from `llm_client` instead.

    **Health check update in `ui_server.py`:** replace Ollama model-list check
    (`/api/tags`) with llama-server health check (`GET /health` → `{"status":"ok"}`).

    **Test:** run full regression suite after swap. All 323 tests should still pass
    (most don't hit the LLM; the ones that mock it stay mocked). Manual smoke test:
    start llama-server, run `local_agent.py --ui`, ask a question.

---

26. **[DONE 2026-07-01] Model file management: document and maintain GGUF library**

    Ollama managed model downloads and storage. With llama-server we own the files
    directly. This item covers the transition and ongoing model management.

    **Immediate:** after item 25 verified working end-to-end — uninstall Ollama,
    delete `C:\Users\bartl\.ollama\` (reclaims ~50GB of blob storage).

    **Current GGUF library:** `C:\Users\bartl\models\gguf\`
    - `llama3.2-3b.gguf` — primary inference model (item 25)

    **Other models from Ollama library** (blobs exist, not yet extracted):
    Extract same way — read manifest, copy blob, rename `.gguf`.
    Manifests at `~/.ollama/models/manifests/registry.ollama.ai/library/`:
    - `llama3.2/latest` — same as 3b
    - `llama3.1/latest` — 8B model (~4.7GB blob)
    - `codellama/7b`, `codellama/13b`
    - `mistral/7b`
    - `qwen2.5/7b`, `qwen2.5-coder/1.5b`, `qwen2.5-coder/latest`
    - `qwen3.5/35b` — large model
    - `gemma3/4b`

    **Model management going forward:** download GGUF files directly from
    HuggingFace (TheBloke / bartowski quantizations are standard sources).
    No model manager needed — files are just files.

    **llm_client.py config:** `LLM_MODEL` should match the GGUF filename stem
    OR be ignored entirely (llama-server serves whichever model it was started
    with — the model param in the request is advisory, not a selector).
    Simplest: remove model name from request payload since llama-server ignores it.

---

### ASSISTANT ARC (session 36, 2026-06-29)

The tool has matured from an oracle (answer queries) to an assistant (surface gaps,
propose changes, support review). These four items build the assistant capability
layer on top of the existing structural knowledge foundation.

**What these build on (concrete infrastructure — read before building any of 21-24):**

Embedding: `determined/oracle/embedding_model.py` — `embed_text(str) -> np.ndarray`,
`cosine_similarity(a, b) -> float`. Lazy-loads `all-MiniLM-L6-v2` on first call.
In agent_tools.py the model is cached as `_get_embed_model()`; batch encode via
`model.encode([...], normalize_embeddings=True)`, dot product gives cosine similarity.

Design frame pattern: `_get_design_frame(assessor, symbol, file_path)` at
agent_tools.py:394 — builds query string from symbol+file stem+docstring, calls
`search_tenets(query, threshold=0.32, top_n=3)` from `determined/data/sots_loader.py`.
This is the reusable pattern for "embed context, cosine-search a knowledge surface."

Design violations pattern: `_check_design_violations_core(assessor, symbol, file_path)`
at agent_tools.py:504 — same embed+cosine-search pattern but richer query
(symbol+docstring+callee names+file stem) and searches `design_notes` at threshold 0.30.

Distilled summaries: stored in `semantic_summaries` table, `distilled` column.
Query: `SELECT distilled FROM semantic_summaries WHERE subject LIKE ? AND distilled IS NOT NULL`.
Subject is the file path. Also stored as `kind='distilled'` in `knowledge_artifacts`
with subject `distilled::<name>`. Both stores exist; `semantic_summaries.distilled`
is the primary one used by `symbol_brief` and `goal_intake`.

Goal intake semantic search pattern (agent_tools.py:1454-1484): loads all symbols
with docstrings via `_search_symbols_raw(oracle, "", limit=600)`, enriches each
with distilled file summary, batch-encodes all + the goal query together, ranks by
dot product. Threshold 0.28. This is the reusable pattern for concept→symbol matching.

Review queue: `determined/intent/workflow_store.py` — `add_item(conn, kind, subject,
content, provenance="human")`. Use `provenance="llm-proposed"` for machine-generated
proposals. `kind="next_up"` for actionable items. `update_item(conn, id, status="done")`
to accept. `status="deferred"` to dismiss. Table is `workflow_items` in the corpus DB.

Symbol references: `symbols` table has `symbol_type` values `function`/`class`
(declarations) and `caller`/`callee` (call-graph participants). `graph_edges` has
`caller`, `callee`, `caller_file`, `line_number`, `resolved`. `symbol_references`
table has `caller`, `callee`, `file_path`, `line_number`. All three needed for
find-references (item 21): declarations from `symbols`, usages from `symbol_references`.

Class attributes: `class_attributes` table — `(file_path, class_name, attribute,
inferred_type)`. Added in item 20. Used in item 21 for class attribute listing.

Risk scoring: `determined/agent/risk_annotator.py` — `score_risk(oracle, symbol)`
returns dict with `level` (HOT/WARM/SAFE), `reasons` list. Already used in `goal_intake`
and `risk_profile`. Import: `from determined.agent.risk_annotator import score_risk`.

---

21. **[DONE 2026-06-30] Symbol context view** — `symbol_context(assessor, args)` in agent_tools.py.
    Single call returns declaration, docstring, risk badge, find-references, callers/callees,
    class attributes, design frame, and stored findings. understand_symbol task pattern
    updated to single step. Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern.

---

22. **[DONE 2026-06-30] Wide concept search** — `concept_search(assessor, args)` in agent_tools.py.
    Searches symbol names, docstrings, behavioral contracts, design notes, distilled summaries.
    Semantic re-ranking via all-MiniLM-L6-v2 at threshold 0.25. Grouped output by surface.
    Wired into TOOLS, REGISTRY, TASK_PATTERNS, detect_pattern.

---

23. **[DONE 2026-06-30] Docstring health — campaign tool** — surfaces missing and stale docstrings,
    proposes fills, supports editor write-back. New function `docstring_health(assessor, args)`
    in agent_tools.py. Optional args: `file` (scope to one file), `module` (scope to
    path prefix), `propose` (bool, default True — generate proposals and store in queue).

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
    `cosine_similarity(embed_text(docstring), embed_text(distilled))` — low score
    (< 0.55, tune empirically) = potentially stale. Report score alongside each flagged
    symbol so developer can judge. High distance = docstring and code diverged.

    **Proposal generation:** for each missing or stale symbol, look up distilled text:
    `SELECT distilled FROM semantic_summaries WHERE subject = ? AND distilled IS NOT NULL`
    (subject is file_path). If found, call `workflow_store.add_item(conn, kind="next_up",
    subject=f"docstring::{file_path}::{name}", content=distilled_text,
    provenance="llm-proposed")`. Store file_path and line_number in content as JSON
    so write-back knows where to go.

    **Editor-launch (UI layer):** `ui_server.py` — when user clicks a proposed docstring
    item in the work queue, open an inline editor pre-filled with the proposed text.
    On accept: write the text as a docstring to the source file at the stored line_number,
    call `workflow_store.update_item(conn, id, status="done")`. On reject: status="deferred".

    **Confidence display:** show cosine distance score alongside each stale flag.
    Score >= 0.80: likely fine. 0.55-0.80: review. < 0.55: flag as stale.
    Missing symbols get no score (N/A — no existing docstring to compare).

    **UI tab:** add `"docstring_health"` to `_TAB_TOOLS` in `ui_server.py` alongside
    the existing `"docstrings"` tab (which can be retired or repurposed as a summary).

---

24. **[DONE 2026-06-30] On-demand gap analysis with standing summary** — two-tier capability:
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
      non-NULL `role` values (item 1 just landed — verify it's populating).
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
    - Output is idea-mode — explicitly framed as possibilities, not prescriptions.
      Prefix output: "GAP ANALYSIS (generative — proposals may be off target):"
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
