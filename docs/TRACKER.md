tools/analysis - TRACKER (consolidated)
=========================================

This file is the canonical open-items list and at-a-glance status for the
Determined analysis tool. Active open items only. For closed items, phase
plans, tier status, UI vision, branch methodology, and environment defects,
see docs/archive/TRACKER_history.md. For architecture/intent (the why
behind the design), see DESIGN.md.

Per CLAUDE.md's working agreement: update this file in place as part of
finishing work (checkboxes, dated notes) so Bart can see what changed via
`git diff`, and so a future session doesn't need conversation history to
know where things stand.

---

## Dashboard - at a glance

**Last session (2026-07-01, session 50):** Items 25 + 26 closed.
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

**Full history:** HISTORY.md.

---

## Open items

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

14. **[FUTURE] Semantic speculative decoding** - once item 10 (structured output)
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

Moved to HISTORY.md (section B) as part of the 2026-06-18 TRACKER/HISTORY
split - full dated session-by-session record, verbatim, nothing dropped.
