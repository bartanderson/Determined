tools/analysis - DESIGN (reconciled 2026-07-10)
================================================

Architecture and intent. The why behind design decisions.
For live status and open items: TRACKER.md.
For non-obvious decisions and surprises: HISTORY.md.

Pre-reconciliation archive (2026-07-10): docs/archive/DESIGN_pre_reconciliation_2026-07-10.md
Earlier archive: docs/archive/DESIGN_archive.md

---

## 1. Core philosophy

The database snapshot is the substrate. What matters is that you can:

- Run the pipeline on any codebase to produce a `.db` snapshot
- Query that snapshot to answer structural questions deterministically
- Use those answers to decide what to keep, discard, or refactor
- Iterate on the tool with a repeatable way to measure improvement

No cross-run manifests, timestamps, or decision tables needed. The core
loop is: **snapshot → query → reason → act.** Everything else builds on this.

---

## 2. System shape (current, as of session 134)

The tool has evolved from a query oracle into an assistant. The current
system has six layers, each with a clear authority:

```
USER QUESTION
    -> AGENT (local_agent.py)
        Phase 1: DECOMPOSE  -- model lists information needs (NEED: lines)
        Phase 2: RESOLVE    -- deterministic pattern router executes tools
        Phase 3: ASSEMBLE   -- model reads facts, writes plain English answer
        Post:    VERIFY     -- claim_verifier checks structural facts, corrects if wrong
    -> TOOLS (agent_tools.py)
        30+ tools: structural queries, semantic search, LLM calls, doc extraction
    -> ORACLE (db_oracle.py)
        Deterministic queries over corpus DB
    -> CORPUS DB
        All facts: structural + semantic + knowledge artifacts
    -> LLM (llm_client.py)
        Two-tier: quality (Qwen3-8B port 8081) / fast (llama3.2-3b port 8080)
    -> UI (ui_server.py + console.html)
        Browser-based corpus explorer + Ask bar
```

**The model's job is narrow by design:** decompose questions (Phase 1) and
synthesize facts into prose (Phase 3). Everything in between is deterministic.
This is the same discipline as the original Truth Kernel: AI is a compiler
and narrator, not a source of structural facts.

---

## 3. Corpus DB -- the single store

**Everything lives in the corpus DB.** `knowledge.db` was eliminated in
session 33 (2026-06-28). There is no shared overlay DB.

Corpus DB path convention: `C_Users_<username>_dev_<project>.db`

### Tables

**Structural (populated at ingest time, fully deterministic):**
- `functions` — all functions/methods: name, file, line, class_name, docstring, is_stub, param_types_json, return_type, role
- `classes` — all classes: name, file, line, base_classes_json, is_abstract
- `class_attributes` — __init__ self.attr assignments with inferred types
- `graph_edges` — call edges: caller, callee, caller_file, line_number, resolved
- `symbol_references` — all call sites: caller, callee, file_path, line_number
- `files` — per-file metadata: path, role, size, is_hot, is_stub, mutation_count
- `imports` — import statements per file

**Derived (populated by agent tools on demand):**
- `semantic_summaries` — per-file LLM summaries + distilled one-liners
- `knowledge_artifacts` — design notes, SOTS tenets, GRASP principles, findings, reconciliation results, layer rules, waypoints
- `workflow_items` — backlog proposals, docstring fills, gap analysis results
- `bags` / `bag_items` — session context accumulation
- `contract_violations` / `contract_drift_history` — layer boundary violations
- `project_meta` — key-value store for corpus-level metadata (design doc hints, etc.)

### Corpus DB is expendable

Corpus DBs can be deleted and rebuilt by re-ingesting. The structural tables
rebuild in seconds. Semantic summaries and knowledge artifacts regenerate
on demand. There is no external persistence that can be lost.

---

## 4. Ingestion pipeline

Entry point: `determined/ingestion/` + `determined/agent/parse_ast.py`

**Full ingest:** `ui_server.py` triggers `scan_project_files` → `parse_ast`
→ `persistence_engine`. Builds all structural tables from source ASTs.
No LLM involved. Typically < 30s for 150 files.

**Incremental ingest:** `reingest_file(file_path, db_path)` in
`determined/ingestion/reingest_file.py`. FileDelta scratchpad tracks
old/new symbol state. Applies delta: insert new, update changed, delete
stale, rebuild outbound edges. Idempotent. Used by UI "Re-analyze single
file" and corpus phase injection (training mode).

**Annotation-resolved edges:** when a function parameter has a type
annotation (`def f(x: Foo)`), call edges from `x.method()` are resolved
to `Foo.method` rather than `x.method`. Stored as `graph_edges.resolved=1`.
Improves call graph accuracy without a full heap model.

---

## 5. Oracle layer

`determined/oracle/db_oracle.py` — `DBOracle`

Pure deterministic queries. No LLM. No side effects. All agent tools
go through the oracle for structural facts. Key methods:

- `find_symbols(query)` — name/file search
- `find_files(query)` — file path search
- `get_callers(symbol)` / `get_callees(symbol)` — direct call edges
- `get_class_attribute_type(class_name, attr)` — inferred attribute types
- `get_project_root()` — from project_meta

Embedding: `determined/oracle/embedding_model.py` — lazy-loads
`all-MiniLM-L6-v2` (384-dim). `embed_text(str) -> ndarray`,
`cosine_similarity(a, b) -> float`. Used by semantic search, design note
dedup, duplicate detection, concept_search.

---

## 6. Agent layer

### 6a. Three-phase pipeline (local_agent.py)

The model's job is narrowed to what a small local model handles well:

```
Phase 1 DECOMPOSE: model outputs NEED: lines listing information needs
Phase 2 RESOLVE:   pattern router maps NEED: lines to tool calls, executes all
Phase 3 ASSEMBLE:  model reads question + all facts, writes plain English answer
```

The NEED checklist is inspectable. If an answer is wrong, you can see
exactly what was and wasn't looked up. Phase 2 is independently testable
with no model dependency.

**Grounding (Phase 0):** before DECOMPOSE, corpus is searched for symbol/file
names in the question. Results are injected so the model uses real names
in its NEED: lines, not hallucinated ones.

**Heuristic bypass:** some question patterns are answered deterministically
without Phase 1/3. These run when the question matches a known shape and
the facts are sufficient on their own (e.g. "what calls X" → list_callers).

### 6b. Pattern executor (pattern_executor.py)

Named patterns bypass the model for structured multi-step workflows.
When a question matches a pattern, the executor drives the tool sequence;
the model only interprets each step result.

Current named patterns (in `tool_registry.py` TASK_PATTERNS):
- `orient_to_codebase` — 7-step orientation walk
- `corpus_synthesis` — two-pass architectural summary
- `understand_symbol` — single call to symbol_context
- `find_callers` / `find_callees` / `find_files_by_role`

Pattern detection happens before Phase 1. If matched, executor runs instead.

### 6c. Claim verifier (claim_verifier.py) — RM21 Technique 1

After Phase 3 ASSEMBLE, the answer is scanned for verifiable structural
claims via regex:
- `CALLS` — "X calls Y", "X invokes Y"
- `NO_CALLERS` — "X has no callers", "X is not called"

Each claim is checked against `graph_edges`. Wrong claims generate a
correction block that is prepended to the facts and Phase 3 re-runs once.

**Current ceiling:** the verifier only catches CALLS/NO_CALLERS phrased
as those exact patterns. Routing failures (wrong pattern match) and
name collisions (same symbol in multiple files) are upstream of the
verifier. See RM31-34 for next steps.

---

## 7. LLM layer (llm_client.py)

Two tiers, selected per use:

**Fast tier** (llama3.2-3b, port 8080): decompose/assemble in local_agent,
distillation, stub projection, query compilation. Small, fast, good at
following instructions.

**Quality tier** (Qwen3-8B, port 8081): gap analysis synthesis,
`_synthesize_with_ollama`, design doc extraction (LLM pass). Larger,
slower, better at prose reasoning.

The UI starts llama-server automatically on launch (port 8081 for quality,
port 8080 for fast). For CLI use, start manually. `--ctx-size` change
requires full restart.

Public API in `llm_client.py`:
- `generate(prompt, timeout, quality=False) -> str | None`
- `chat(messages, timeout, quality=False) -> str | None`
- `is_available_quality() -> bool`

---

## 8. Agent tools (agent_tools.py)

30+ tools in `determined/agent/agent_tools.py`. Each tool takes
`(assessor, args: dict) -> str`. Wired into TOOLS dict and
`tool_registry.py` (REGISTRY + TASK_PATTERNS).

**PRE-CODE RULE:** before writing any new data transformation, grep
`graph_utils.py` and `agent_tools.py` first. The most common failure
mode is writing a new version of something that already exists.

Tool categories (from tool_registry.py):
- **Structural:** describe_file, symbols_in_file, list_callers, list_callees, graph_most_connected, graph_subgraph, find_files, search_symbols, stability_view
- **Frontier:** frontier_coverage, find_orphaned_impls, find_abc_gaps, score_stub
- **Semantic:** concept_search, semantic_summary, distill_corpus, find_duplicates, classify_duplicates, find_primitive_gaps
- **Knowledge:** knowledge_status, get_findings, store_finding, check_design_violations, evaluate_claim, symbol_context, infer_behavior, risk_profile
- **Design docs:** discover_docs, ingest_design_docs
- **Goal:** goal_intake, gap_analysis, docstring_health
- **Edit:** edit_file, reingest_file
- **External:** search_web (SearXNG)

### Raw helpers (internal)

Five private `_raw` variants return structured data (list of dicts) for
tool chaining: `_search_symbols_raw`, `_list_callers_raw`, `_list_callees_raw`,
`_graph_most_connected_raw`, `_graph_subgraph_raw`. External API stays
string-only (SOTS XIV: one source of truth, tools derive from raw).

---

## 9. Knowledge layer

### Design notes and tenets

**SOTS (Shape of the System):** 25 tenets baked as JSON at
`determined/data/sots_tenets.json`. Loaded by `sots_loader.py`. Surfaced
automatically via `_get_design_frame()` (embed + cosine-search at threshold
0.32) when analyzing any symbol.

**GRASP (9 principles):** baked at `determined/data/grasp_principles.json`.
Loaded by `grasp_loader.py`. Wired into `check_design_violations` alongside
SOTS. Findings name the principle violated (e.g. "GRASP-9 Protected Variations").

**Design doc extraction:** `ingest_design_docs` in agent_tools.py runs two
passes over any markdown doc:
1. Deterministic regex pass — extracts explicit constraint phrases
2. LLM pass — extracts implied invariants and authority rules

Both store as `kind=design_note` in knowledge_artifacts. Semantic dedup
at store time (embed candidate, cosine-compare existing notes, skip if ≥ 0.85
similarity) prevents LLM paraphrases from duplicating deterministic extracts.

Layer rules (`kind=layer_rule`) are extracted separately and checked by
`_check_import_layer_violations`.

---

## 10. Training mode / guide layer (RM28)

A lightweight overlay that appears when the training mode toggle is on.
Off by default; dismissible permanently via localStorage.

Three components:
1. **Color grammar on the tab rail and sub-modes** — tracks visited state
   in localStorage (`det:visited:*`). No color = unvisited. Red = visited,
   < half explored. Amber = half+ explored. Green = all explored. One-action
   elements go straight to green.
2. **Guide card** — contextual card keyed to (active_tab + active_mode +
   corpus_phase). Content from `determined/data/guide_commonplace.json`.
   Updates as user navigates. Only shown for Commonplace corpus.
3. **Corpus phase picker** — skeleton / complete / enhanced. Only shown
   when Commonplace is loaded (key: `_db_path` contains "commonplace").
   Phase injection writes next implementation files and calls reingest_file.

**Completion state:** when all four rail keys are green (`guideAllGreen()`),
guide card shows "You've explored everything. The guide will step back."
Auto-dismiss fires after 4s via `guidePermanentDismiss()`.

**GUIDE_DATA sync trap:** `guide_commonplace.json` and inline `GUIDE_DATA`
in console.html are separate stores with identical content. Both must be
updated together when adding card content. No auto-sync.

---

## 11. UI layer

`determined/ui/ui_server.py` — Flask server, default port 5050.
`determined/ui/console.html` — single-page browser console.

**Sidebar:** 4-icon rail (Corpus / Navigate / Tools / Ask). Clicking active
icon collapses panel to 40px rail-only. Grid: 40px + 210px + 1fr.

**Corpus panel:** analyze + corpus map (Roots/Core with risk badges,
collapsible) + gaps at a glance + duplicate badge.

**Tab loading pattern:** each tab has `xxxLoad()` that self-clears; lazy
tabs load on click. Never add cleanup elsewhere.

**Corpus switch:** reload page on switch (`switched=True` flag). Never
maintain element-ID cleanup lists.

**Re-analyze:** clears tables in place (DELETE FROM + WAL checkpoint)
rather than deleting the file — WinError 32 on Windows holds the file open.

---

## 12. Semantic reconciliation arc

Three passes for finding and classifying duplicate implementations:

1. **find_duplicates** — embed `{name}: {docstring}` for all functions,
   pairwise cosine similarity matrix, pairs above threshold (0.85) stored
   as `kind=reconciliation_finding`.

2. **classify_duplicates** — feeds each stored pair to Qwen3-8B, classifies
   divergence from fixed taxonomy (accidental copy, historical evolution,
   performance optimization, platform-specific, security reason, genuinely
   different abstraction). Stores classification.

3. **find_primitive_gaps** — mines call graph for callee pairs appearing
   together across multiple callers. A composition appearing N times is
   evidence a missing abstraction exists.

Passes 4 (canonicalization) and 5 (architectural drift) deferred.

---

## 13. Design principles (load-bearing constraints)

These have been validated against real use and are not up for debate without
a demonstrated gap:

**One source of truth per fact (SOTS XIV):** string tools derive from `_raw`
helpers. Don't write a new version of something that exists authoritatively.

**Determinism before semantics (SOTS XI):** separate "decide" from "do."
The irreversible decision (what to call, what to store) should be separately
testable from its effect. Pure functions return plans; thin wrappers execute.

**Corpus DB is the knowledge layer:** no external persistence. Knowledge
artifacts live in the corpus DB. Rebuilding the DB is always an option.

**LLM is a narrator and compiler, not a fact source:** structural ground
truth comes from static analysis, not model output. The model connects
pieces the DB already contains; it does not invent structure.

**UI state resets on corpus switch:** reload the page. Never maintain
element cleanup lists — they always go stale.

**Ingest path field stays blank:** never pre-fill from session. Corpus
auto-loads server-side. Input is for switching only.
