tools/analysis - TRACKER (consolidated)
=========================================

This file consolidates the status/tracker docs that used to live as
separate files in tools/analysis/docs/. The originals are preserved in
docs/del/, not deleted:

- REFACTOR OPS BOARD.md
- Truth Kernel Board.md
- Truth.md
- todo-done.md

This file is "what's true right now and how we got there" - status
snapshots, open items, a single canonical writeup of recurring environment
defects, and the chronological session log. For architecture/intent (the
why behind the design), see DESIGN.md (also in this folder, consolidated
from AGENT CAPABILITY LAYER v1.md / TRUTH KERNEL v1.md / truth query
algebra.md / contracts + visibility.md / Symbol Classification
Stabilization Plan.md / work flow.md).

Per CLAUDE.md's working agreement: update this file in place as part of
finishing work (checkboxes, dated notes) so Bart can see what changed via
`git diff`, and so a future session doesn't need conversation history to
know where things stand.

Consolidated 2026-06-17. The four original files had substantial overlap
(the same incidents described from different angles - an engine-refactor
angle in REFACTOR OPS BOARD.md, a tier-status angle in Truth Kernel
Board.md, a verification-phase angle in Truth.md, and a flat done-list
angle in todo-done.md). This consolidation keeps one canonical version of
each event, cross-referencing rather than repeating where the originals
repeated each other.

---

## Dashboard - at a glance

**Recently done (2026-06-23 session 15):** Items 17+18 done - intent routing profiles + risk annotation.
Item 17: debug_query/mutation_query intents in query_router.py + agent_resolver.py heuristics.
Item 18: risk_annotator.py (HOT/WARM/SAFE scoring), wired into symbol_brief output, risk_profile tool.

**Previously done (session 15 earlier):** Item 17 done - debug_query and mutation_query intents.
Added to `query_router.py` (`_detect_intent`, `intent_budget`, `_select_primitives`) and matching
heuristics in `agent_resolver.py`. Debug queries get reverse-heavy traversal + findings/todos/callers.
Mutation queries get balanced traversal + callers/callees. 279/279 tests passing.
Also earlier this session: stub detection (is_stub field), stub projector (Ollama-driven), explainability
on graph_subgraph (reason_included per node), auto-discovery to completion (loop until stalled/done).

**Recently done (2026-06-22 session 9, continued):** game_corpus.db merge DONE.
Added `caller_file` column to `graph_edges` (schema + idempotent migration in `ensure_schema`).
`GraphEdge` + `add_reference` carry caller_file; `run_engine.py` populates it from `analysis.file_path`.
`_persist_graph_edges` now does scoped delete (by caller_file) instead of full-table reset, so multiple
corpora can coexist in one DB. `game_corpus.db` created: world/ (2100 edges, 65 files) + dungeon_neo/
(384 edges, 13 files) = 2484 edges, 78 files, 874 functions - exact additive match vs split DBs.
9 cross-corpus edges (world->dungeon_neo) now visible and traceable. Old split DBs kept for validation.
279/279 regression tests passing.

**Recently done (2026-06-22 session 9):** Adversarial validation layer + prioritize_work tool (3 commits).
prioritize_work tool: signal-based inference (in-progress > rank hint > kind order) replaces hand-ranked list;
deterministic bypass like PICK/survey. Hygiene: marked 4 stale workflow items done. ADVERSARIAL command in
claude_eval.py: 10 suites / 49 variants, compares needs (actual tool calls fired) not heuristic name labels.
Suite found 9 real routing gaps; all fixed (callers synonyms, impact synonyms, git_history synonyms,
pattern_similar synonyms, prioritize synonyms, docstrings synonyms, dev_plan synonyms, describe X).
Also fixed broken CamelCase lookahead in explain_symbol (re.I defeated it). Result: 32/49 variants pass;
remaining 9 needs-breaks are legitimate ambiguity or Ollama variance, not routing bugs. 287/287 tests passing.

**Previously done (2026-06-21 session 8, final):** Determinism work from PICK validation + git design (5 commits).
PICK validation run on 8 questions surfaced two real failures (git_history: Ollama ignored the log fact;
impact: Ollama degraded the symbol_brief). Both fixed with deterministic bypasses (return git log /
symbol_brief directly, like survey/workflow already do); PICK now skips the second run for both.
Assembly hints (_assembly_hint) added for genuine synthesis cases (pattern_similar, workflow-multi) -
per-heuristic Phase 3 focus instruction; pattern_similar now consistent on substance. PRIMARY fact
labeling skipped as redundant (bypasses absorbed its use case). DESIGN.md section 11 added: git is
local-read-only today, credential boundary documented for future remote access. Finding: 'what should
I work on' varies because workflow items lack explicit ranks (data fix, not prompt). 279/279 tests passing.

**Previously done (2026-06-21 session 8, continued):** Phase A complete + Phase B items 4-5 (6 more commits).
Phase A: pattern_similar heuristic ('find similar to X', 'how was X implemented' - uses _similar_needs()
helper with same-suffix class search), impact heuristic ('if I change X what breaks', 'blast radius of X'
- reuses existing task_generator ripple query via symbol_brief). Phase B item 4: git_log_for tool
(resolves bare filenames via corpus, infers repo root via get_project_root(), shells to git log);
git_history heuristic ('what changed recently in X'). Phase B item 5: missing_docstrings tool (corpus
DB query for NULL docstrings), find_todos tool (TODO/FIXME in docstrings); quality heuristics wired.
24 tools total. 279/279 regression tests passing throughout.

**Previously done (2026-06-21 session 8, start):** Vision capture + Phase A heuristics + cleanup (7 commits).
Design: Added DESIGN.md sections 9 (developer intelligence interface - standalone tool, code-agnostic,
UI interaction model with answer-as-navigation, answer-typed rendering, proactive badges, breadcrumb)
and 10 (code editing/refactoring - suggest->diff->approve->apply->verify safety model, corpus-backed
caller enumeration before rename, ast.parse hard stop). Hard boundary captured: tool is permanently
separate from the game app. Code-agnostic constraint: heuristics use structural terms only, domain
knowledge enters only via knowledge.db findings layer.
Phase A: Added list_findings_by_kind tool + 'findings of kind X' NEED pattern. 'What should I work on'
heuristic now pulls workflow_status + future_plan + known_issue findings together.
Bug fixes: superlative queries ('what is the most X') no longer false-positive on survey heuristic.
'How many files are in X' added to modules_in heuristic. snake_case->CamelCase lookup in
_trace_needs/_explain_needs ('what does world_controller do' now finds WorldController class).
Open item 15 added to TRACKER: token-aware symbol search (current workaround noted as tech debt).
Cleanup: deleted all untracked scratch files (_store_batch*, _test_*, _check_*, _show_*, _list_*).
279/279 regression tests passing throughout.

**Previously done (2026-06-21 session 7):** Systematic query-shape probing + heuristic expansion (9 commits).
Bug fixes: article-skip before directory name (modules_in), 'files in X.py' redirect to describe_file,
workflow_status bypass (Ollama sometimes mangled output), 'how do I X' captured 'I' as symbol name.
New heuristics: compare/diff two symbols ('compare X and Y', 'difference between X and Y'),
relationship ('relationship between X and Y'), imports_from ('what files import from X'),
files_that_use ('files that use X'), show_me_how ('show me how X is used'),
where_is_defined ('where is X defined/located'), modules_in extended ('what is in the X folder'),
survey extended (architecture/design/structure of X, 'what is X', 'tell me about X').
279/279 regression tests passing throughout.

**Previously done (2026-06-21 session 6):** Heuristic coverage major expansion + PICK command DONE.
(1) Added 9 new heuristic patterns: symbols_in_file, callers (who calls/where is X used/triggered),
survey (state/status/show-me/what-is-responsible), entry_points, find_files, modules_in, how_is_handled,
what_happens, how_do. (2) Fixed article-skip bug in trace/describe-file heuristics ('how does the X'
was capturing 'the' not 'X'). (3) Fixed survey bypass false positive on dev_plan queries (entry points
presence now excludes survey detector). (4) Added PICK subcommand to claude_eval.py: run question twice,
surface only disagreements (agreed=confident, disagreed=needs human review). (5) Verified 100% file coverage
(auto --mode unknown returns no uncovered files). 51/51 regression tests passing throughout.

**Previously done (2026-06-20 session 5):** Game corpus depth audit DONE. Depth-2 is sufficient
for world_corpus.db - max real chain depth is 3 (utility function, not architectural).
DM->world->dungeon_neo concern is a per-corpus-DB split limitation, not a depth budget problem.
Fix is merged game_corpus.db (item 3 prerequisite). No code change needed.

**Previously done (2026-06-20 session 4):** ASSEMBLE fact-omission fixed + survey cross-file intelligence DONE.
(1) Survey heuristic gets deterministic structured answer (bypass Ollama) - before: "The PartySystem class exists." (13 facts ignored),
after: structured inventory of files, symbols, call relationships, stored findings.
(2) General ASSEMBLE gets required-elements hint injected into prompt (files found, callers found).
(3) Phase 2b expansion now fetches get_findings per file found by search_files - survey answers now include
file_purpose and design_note artifacts from discovery pass. "what exists for the narrative system"
now returns both narrative_engine.py and narrative_system.py with full design notes and symbol inventory.
Survey heuristic article-skip fix also DONE (session 3): skips a/an/the before key term.

**Previously done (2026-06-20 session 2):** Full world corpus discovery pass COMPLETE.
65/65 files covered in world_corpus.db. 4 tool bugs found and fixed during the pass:
(1) symbol_intent disambiguation - file_path hint added, Phase 2b expansion threads it through;
(2) describe_file basename match - prefers exact match over substring (fixes utils->ai_utils, resolver->entity_resolver);
(3) ASSEMBLE fact-omission - stronger system prompt + postprocess guard injecting caller list;
(4) 4 new known_issues stored (party overlap, PerlinNoise duplication, travel_system unconnected, world_session superseded).
New future_plans stored: Cloudflare adversarial validation, PICK distinguishing-example pattern, Cope-and-Drag layout.
interpretation_pipeline design note added. terrain_generation_history design note added (JS port round-trip explains duplication).
tool_system_boundary design note added (AI tool-use contract layer identified).
settings.json updated: Bash(*) + PowerShell(*) allow all commands without prompting.

**Previously done (2026-06-20 session 1):** Design doc mining + codebase progress assessment DONE 2026-06-20.
`mine_design_docs.py` created; 31 `design_note` / `human-confirmed` artifacts stored in knowledge.db
for all major game systems (EventLog, EscalationEngine, ContextBuilder, EntityResolution, DialogSystem,
QuestSystem, CombatSystem, NarrativeEngine, GameEngine phase cycle, WorldController, etc.).
Design notes now surface in Phase 0 grounding - agent answers use design intent before code analysis.
Codebase status stored as `development_progress` artifact: core truth layer complete;
GameEngine phase cycle partial (movement done, buy/sell/teleport TODO); WorldController (2354L) is
primary architectural debt; all major game systems exist with varying maturity.

Before that: Named heuristics + workflow system + claude_eval.py - DONE 2026-06-20.
`detect_heuristic()` with 9 named patterns skips Ollama decompose for common queries.
`workflow_items` table (next_up/backlog/future_plan/session_decision), full CRUD, `rerank_items`.
`claude_eval.py` with ask/batch/auto/store subcommands - Claude's non-interactive pipeline access.
Bug fixes: `describe_file` bare filename resolution, file-level grounding, regex ordering.

Before that: Full discovery + Q&A system DONE 2026-06-20. All 7 core pieces built:
graph_utils, graph_viz, graph tools in resolver, Phase 2c LINK, extended Phase 0 grounding,
discovery loop (finite batch/resume-safe), Phase 4 SUGGEST + knowledge_status. Items 8-12
deferred to post-evaluation. Before that: Expansion noise + glob fixes - DONE 2026-06-20. `_symbols_from_result`
now filters dunder methods and common boilerplate (`to_dict`, `from_dict`, etc.) before
expanding. `resolve_need` strips glob chars (`*`, `?`) from `search_files`/`search_symbols`
queries so `encounter_*` becomes a valid substring search. 5 new tests. Agent suite: 57/57.
Before that: Phase 0 GROUND - DONE 2026-06-20. `ground_question()` extracts keywords
from the question, runs `search_symbols` + `search_files` on each, injects real corpus names
into the Phase 1 prompt so the model selects from actual names instead of inventing them.
7 new tests. Suite: 293/293. Before that: Phase 2b auto-expansion - DONE 2026-06-20. `expand_facts()` follows
leads from Phase 2 results: symbols -> callers+intent, files -> symbols_in_file. 7 new tests.
Suite: 287/287. Before that: Three-phase agent pipeline - DONE 2026-06-20. `agent_resolver.py` written
(pattern router: NEED: lines -> tool calls, dedup, pure Python, 33 tests). `local_agent.py`
rebuilt around DECOMPOSE/RESOLVE/ASSEMBLE phases (5 new smoke tests, old ReAct tests replaced).
Full suite: 280/280. Before that: Builtin noise filter extended - DONE 2026-06-20. `symbol_noise.py`
now checks Python's `builtins` module as a secondary filter, removing bare Python
builtin names (e.g. `all`, `len`, `range`) from impact zones even when they appear
in mixed DB buckets. Bare method names like `get` (dict.get()) are a separate class
of noise - accepted for now, covered by the impact zone's "cross-check" note.
Before that: knowledge.db shared overlay - DONE 2026-06-20. `KnowledgeOracle`
wraps `knowledge.db` (separate from corpus DBs); `knowledge_artifacts` + `semantic_summaries`
moved there. `Assessor` auto-opens it alongside corpus DB. `generate_task_md` reads from
knowledge conn, shows `[STALE]` prefix when `needs_review=1`. Template bug fixed. Artifact
migrated from self-corpus DB. `generate_task_md('generate_location_from_potential')` against
`world_corpus.db` now shows the Known findings section end-to-end. Suite: 148/148.
Before that: Test suite hygiene (item 8) - CLOSED 2026-06-20. Deleted legacy
`tests/core/` and `tests/debug/`. Before that: Knowledge artifacts wired into generate_task_md() - DONE 2026-06-19.
`_known_findings()` fetches artifacts for the symbol; `_render()` adds "Known findings"
section (provenance-ranked) when any exist. 2 new tests in `test_task_generator.py`. Suite: 148/148.
Before that: Test suite hygiene (item 8, partial) - DONE 2026-06-19. Oracle CLI smoke test
(`test_oracle_cli_smoke.py`, 4 tests). Suite: 146/146. Before that: Engine refactor Phase 5 (item 4) - DONE 2026-06-19.
`route_query` moved to `assessor/query_router.py` (Assessor-owned). Query path
now uses `DBOracle.get_edge_maps()` - no `GraphBundle`/engine dependency. `task_generator`
and `task_rereferencer` take `oracle` directly. `api/oracle_router.py` is now a thin
re-export. Suite: 142/142. Before that: Intent Layer sub-layers A+B (item 12b) - DONE 2026-06-19.
`semantic_summaries` + `knowledge_artifacts` tables, full Assessor wiring,
27 regression tests. Suite: 142/142. Before that: Game-code corpora ingestion
(Dashboard item 1) - DONE 2026-06-19. Ingested all four game corpus dirs (`world/` 65 files,
`engine/` 2, `resolver/` 1, `dungeon_neo/` 13) via the standard
`EngineRunner().run(...)` headless pattern. All pass. Regression proof
added: `tests/regression/test_game_corpus_ingestion.py` (5 tests: one
per-corpus completion check + one known real cross-file call anchor:
`_generate_via_ai` -> `world.ai_utils.get_ai_response` at line 41 in
`world/name_generator.py`). Note confirmed during probe: `self.method()`
intra-class calls are not captured as graph edges by the engine (known
behavior, not a test bug - anchored on a cross-file call instead). Full
suite still passing. Item 1 fully closed.

Before that: Orphaned-module disposition review (section 3 item 12)
- investigated and reported 2026-06-19, no integrate/dispose/delete action
taken (per the item's own gate: report findings to Bart before any
disposal). Checked actual wiring (import/call-site grep across the whole
tree), not just file contents in isolation, for all 9 originally-listed
candidates plus the empty `orchestration/` directory and the
`specification/tool_system_contract.json` spec file. Full per-item findings
and disposition recommendations: section 3 item 12 below. Headline results:
most candidates are confirmed genuinely dead (zero callers anywhere); one
(`inspection/explain_file.py`) is a complete, ready-to-use capability that
nothing currently calls - a real "hole," not dead weight; one
(`api/get_llm_context.py`) isn't orphaned at all despite zero in-repo
callers, since it's the documented external integration point for a
consumer (the future agent) that doesn't exist yet; and `contract_types.py`
+ `specification/tool_system_contract.json` + the empty `orchestration/`
directory turn out to be three pieces of one coherent, unfinished feature
rather than independent dead files. Also surfaced one finding outside the
original list, same directory: `contracts/load_contract.py`'s consumers
load a *different* `tool_system_contract.json` (the one physically in
`contracts/`, schema_version 3) and would `KeyError` immediately if ever
called, since that file has no `domains` key - dormant, not yet broken in
practice, only because nothing calls it.

Before that: Ingestion run 2026-06-19 against all three candidate
corpora from section 3 item 1: `tools.old/` (73 files, 2764 graph_edges),
`external_corpora/flask/src` (24 files, 800 graph_edges),
`external_corpora/sqlalchemy/lib` (255 files, 20769 graph_edges) - row
counts confirmed by direct query against each resulting DB. Permanent
regression proof added:
`tests/regression/test_external_corpus_ingestion.py` (2 new tests,
asserting a known real symbol from `tools.old/` appears correctly in
`graph_edges`); full suite now 82/82. New standing environment defect found
and worked around during this run - see section 2d. Before that:
`external_corpora/flask` and `external_corpora/sqlalchemy`
.git directories repaired 2026-06-19 - both had silently kept the empty
clone-skeleton `.git` (no objects, no config) instead of the real one after
last session's manual Windows rename/move/delete cleanup, root-caused to
PowerShell wildcard moves skipping hidden dot-folders; real `.git` (with
full pack + history) recovered from the still-present sandbox-local clones
at `/tmp/ext_clone/` and swapped in - see section 2c and section 3 item 1.
Before that: Embedding-fallback crash risk in seed discovery (old
item 22) and dead `runtime_bindings` wiring (old item 23) - both DONE
2026-06-18, fixed and regression-tested (6 new tests; 80/80 full suite
after); see section 3 items 13-14 for proof. Section 3 reordered/merged
same date: items 3+4+7, 9+13 step 2, and 6+8 consolidated to remove
duplication while preserving each source's nuance; closed items 1/15-20
removed from the open numbered list (nothing deleted - full writeups
remain in HISTORY.md section B). Before that: code-quality/weak-spot
audit of the live, wired code (old item 20) - DONE 2026-06-18, found the
two gaps just closed above; SystemSelfModel documented + tested (old item
19); SUBSYSTEM builtin-noise filter (old item 18); INTEGRITY view gap
closed (old item 17); SUBSYSTEM path-pollution fix (old item 16). Full
history: HISTORY.md.

**Direction and impact (opinionated - read before picking a task):**

The stated end-goal is a local conversational agent (DESIGN.md section 8)
that Bart can run against any corpus DB to answer plain-English questions
about his game codebase without needing Claude. Design locked 2026-06-20.
Build order: agent_tools.py -> agent_prompt.py -> local_agent.py ->
evaluation sessions. See DESIGN.md section 8 for full spec.

Previous open items below are still valid but subordinate to this goal.
Every open item falls into one of three buckets:

- **Capability work** - unlocks something the agent cannot do today. High
  impact, do these first. Currently one item: item 2 (Truth Row 1 + Row 5,
  intent/description capture at ingestion time). This is the only open item
  that takes the tool from "answers structural questions" to "answers why
  questions." Nothing else on the list does that.

- **Make-work / hygiene** - cleans up the codebase or removes debt without
  unlocking any new capability. Items 3 (Engine/Assessor boundary,
  architecture split), 4 (Phase 5 trace API formalization), 5
  (trace-weighted ranking), 8 (test suite hygiene), 9 (Tier 3/4 system
  replacement), 11 (Tier 0 stale spec update) all fall here. These are real
  work and should eventually be folded in, but they produce a cleaner
  codebase, not a more capable agent. The right time is after item 2
  completes and after item 6's query-expansion validation confirms what the
  boundary actually needs to do - doing the architecture split first risks
  optimizing for a use case that shifts once intent-capture is real.
  Tolerate this debt until item 2 and item 6 are done. Fold in as a batch
  then, not piecemeal.

- **Low-effort unlocks** - small, already-built work that fills a real gap.
  Do these alongside capability work, not instead of it. Two here: (a)
  wire `inspection/explain_file.py` (item 12 finding - complete, DB-backed,
  zero callers, fills the per-file explainability gap the Role view already
  wants); (b) delete the 7 confirmed-dead orphans from item 12 (zero
  callers confirmed by whole-tree grep, no judgment call needed on any of
  them). Both are 30-minute tasks that reduce confusion without risk.

**Now / next, in priority order:**
1. [DONE 2026-06-19] Game-code corpora ingestion - see "Recently done" above.
2. Truth.md Phase 1 Row 1 remainder + Row 5 (section 3 item 2) - the next
   and highest-leverage task. Unblocked as of item 1 above. Do this before
   any architecture/hygiene work.
   - Alongside this: [DONE 2026-06-19] wired `inspection/explain_file.py`
     into `Assessor.explain_file()` and deleted 5 confirmed-dead orphans
     from item 12. 18/18 regression tests passing.
3. Query-expansion validation / impact_query semantics audit (section 3 item
   6) - validates whether the query layer actually produces useful zones
   against real data, and audits impact_query semantics before the agent
   capability layer is built on top of it. Do this before the Agent
   Capability Layer (item 10), not after.
4. [DONE 2026-06-19] Agent Capability Layer (item 10) - COMPLETE.
   Step 1: `Assessor.generate_task_md(symbol, out_path)`. Two-tier output.
   Step 2: `Assessor.rereference_task_md(path, diff_out_path)`. Reads
   existing task.md, diffs against current DB, renders change report.
   114/114 passing.
5. Architecture hygiene batch (section 3 items 3, 4, 5, 8, 9, 11) - fold in
   as a group after items 2-4 above. These are make-work relative to items
   2-4 and should not be let in front of them.

**Standing defects to remember every session** (section 2): stale `.pyc`
caching is a confirmed tooling defect on this environment - if runtime
behavior contradicts visible source, suspect a stale cache before assuming
the source is wrong.

---

## 1. Current status snapshot

### 1a. Engine refactor phase plan (from REFACTOR OPS BOARD.md)

Goal of Phase 1: make oracle_router deterministic under ontology
constraints. Status as of 2026-06-17:

**PHASE 1 - ENGINE STABILIZATION**
- [x] remove implementation-level symbols from expansion results - DONE
  2026-06-16, builtin + accessor-chain noise filtering unified into
  `oracle/symbol_noise.py`, used at both discovery time and expansion time.
- [x] seed discipline enforcement (seeds only from discovery API) - DONE
  2026-06-17, production seeding confirmed already 100% DB-backed; dead
  `_seed_symbols()` decoy wrapper removed from `api/oracle_router.py`.
- [x] oracle_router expansion boundaries (intent -> traversal budget
  enforcement, forward vs reverse weighting) - DONE 2026-06-17 (later
  session), see ROUTING LAYER below for the calibration detail.

**PHASE 2 - QUERY DISCOVERY SYSTEM**
- [x] DB-backed symbol discovery API - DONE 2026-06-17:
  `list_symbols`/`find_symbols`/`find_files`/`find_modules`/
  `symbol_module_map` implemented in `oracle/db_oracle.py`, all
  DBReader-only (single SELECT against `symbols`/`files`, no
  engine/in-memory fallback).

**PHASE 3 - ASSESSOR AS ORACLE CORE**
- [x] introduce QuerySession (first true oracle object) - implemented in
  `assessor/query_session.py`; history persisted to a `query_sessions`
  table via `oracle/persist_query_session.py` (best-effort, never breaks
  the query contract).
- [x] move query execution fully into Assessor - DONE 2026-06-19.
  `route_query` moved to `assessor/query_router.py`, takes `oracle` not
  `(graph, find_symbols_fn)`. `api/oracle_router.py` is now a thin
  re-export wrapper. `task_generator` and `task_rereferencer` also take
  `oracle` directly. `DBOracle` is pure data access (get_edge_maps,
  discover_seed_symbols, builtin_symbols) - no semantic interpretation.
  All 21 regression test files pass.

**PHASE 4 - ORACLE HARNESS STABILIZATION**
- [x] DB-only execution mode - DONE 2026-06-19 (same change as Phase 3).
  `QuerySession.run_query()` no longer calls `get_snapshot_graph()` (which
  returned a `GraphBundle` engine object). Expansion runs via
  `DBOracle.get_edge_maps()` which returns plain `(forward, reverse)` dicts
  directly from `graph_edges` - no `GraphBundle`/`GraphEdge` import in the
  query path. `_bind_snapshot()` kept as a legacy stub for non-query
  callers; the query path itself is engine-free.

**PHASE 5 - REASONING TRACE EXPOSURE**
- Partially active already: seed_paths, expansion trace, and node
  inclusion reasons all exist in `execution_plan["trace"]`.
- [ ] formalize as first-class API: `expansion_explanation()`,
  `seed_explanation()`, `intent_mapping_trace()` - still open.

**PHASE 6 - WEIGHTED SEMANTIC SCORING**
- [ ] replace heuristic scoring with trace-weighted ranking - still open,
  explicitly "later."

**Detailed layer checklist (TRUTHS LOCKED: SymbolIdentity owns identity;
graph is DB-derived truth, no heuristic writes; invariants are
post-construction only; routing is logically split - symbol_router does
intent + seed discovery, oracle_router does expansion + pruning +
planning, with physical separation complete but some coupling remaining
in expansion strategy; query layer operates only on graph truth.)

IDENTITY LAYER: SymbolIdentity active/stable [x], identity authority
consolidated [x], identity migration complete [x], unify identity factory
entrypoint (single creation path) [ ].

CLASSIFICATION LAYER: routing separated via symbol_router [x],
classification operates on routed domain only [x], unify classification
imports (single source path) [ ], eliminate residual dual routing paths
in tests [ ].

INGESTION: AST extraction stable [x], alias_map normalization consistency
under observation [-], finalize dotted-name policy (canonical identity
preserved in graph, tokenization only for discovery layer, never used as
identity mutation) [ ].

GRAPH: edge persistence schema stable [x], graph deterministic (DB
aligned) [x], invariant validation stable (post-build only) [x], verify
all query consumers are DB-backed only / no in-memory fallback paths
remain anywhere [ ].

ARCHITECTURE SPLIT (all still open): create contracts layer [ ], create
assessor layer [ ], move query stack into assessor [ ], enforce DB-only
boundary [ ], remove engine/query coupling [ ].

QUERY LAYER: context/surface/impact stable [x], cross-run deterministic
behavior confirmed [x], oracle query surface integrated [x]. Remaining
items below were written before the discovery API landed and are now
superseded by Phase 2's completion above, kept here for traceability:
remove engine-owned/caller-supplied seed selection [x, see Phase 1], add
symbol discovery API as unified bootstrap layer [x, see Phase 2], add
ranking refinement layer (heuristic -> trace-informed scoring) [ ], define
query surface API as first-class entrypoint [x, see Phase 2].

ROUTING LAYER: intent detection stable (symbol_router) [x], seed
generation stable [x], oracle_router functional [x]. "CURRENT ISSUE" -
RESOLVED 2026-06-17: depth limits calibrated (`surface_query` forward_depth
1->2; `reverse_query` reverse_depth 2->1, now distinguishable from
`impact_query`'s transitive reverse_depth=2; `general_query` 1/1 balanced
and `impact_query` reverse-only depth 2 were already correct and left
unchanged) - locked in by
`tests/regression/test_intent_budget_calibration.py` (5 tests). Dead
`two_hop` key removed from every `intent_budget` entry. Still open:
[ ] validate intent-specific expansion quality against real usage (this is
the "is it actually useful" evaluation, separate from "is it calibrated
correctly" which is now done).

REASONING LAYER: expansion trace capture implemented [x], expose
expansion reasoning view (node_reasons -> API surface, `_route_expand()`
returns seed_paths/expansion trace/node inclusion reasons in
`execution_plan["trace"]`) [x]. Deterministic reasoning primitives exposed
as named callables on `QuerySessionResult` [x]: `seed_explanation()`,
`expansion_explanation()`, `intent_mapping_trace()`, `node_reasons()`,
`seed_paths()`, `expansion_edges()` - all backed by live trace data
(verified 2026-06-19, Phase 5 DONE). Still open: [ ] answer architectural
questions from graph truth, [ ] identify structural
influence and dependency zones, [ ] support oracle-style interrogation
queries, [ ] oracle execution feedback loop (query -> refinement signal).

CONTRACTION LAYER: [x] deferred until query fragmentation observed in
real usage (decision, not a gap).

TEST SUITE: invariant regression resolved [x], engine snapshot stable [x],
regression suite added 2026-06-16 (`test_oracle_router_persistence_lock.py`)
[x]. Still open: [ ] project symbol ordering must be DB-deterministic (no
insertion-order reliance anywhere), [ ] minimal oracle CLI smoke test
harness needed, [-] some regressions classified as expected stabilization
noise.

**Notes (clean-state summary, still accurate):** instrumentation is
structurally sufficient; DB remains authoritative truth source; invariants
are post-build validation only; routing split is complete structurally,
still evolving behaviorally; next architectural evolution is expansion
trace -> weighted influence model (Phase 6).

### 1b. Truth Kernel tier status (from Truth Kernel Board.md)

Purpose: deterministic introspection governance layer. Nothing enters
until it's testable, deterministic, and grounded in existing system truth
- the Truth Kernel is not allowed to invent information.

**TIER 0 - query interface hypotheses (AI compiler surface).** Defines how
natural language maps into the query algebra; TRUTH KERNEL v1.md
(DESIGN.md section 2) is the authoritative spec. Promotion rule: must have
executable tests.

**TIER 1 - VERIFIED (fact).** All proven correct via execution:
- [x] Query AST, Query Planner, Query Executor.
- [x] Structure View - wired to real DB data, builtin-filtered.
- [x] Stability View - wired to real contract reports. `drift_signals`
  populated 2026-06-17 (was hardcoded `[]` - the "most dangerous gap
  shape," see chronological log).
- [x] Integrity View - wired to real validation data.
- [x] Summary View, Subsystem View - both re-upgraded 2026-06-16 to real
  DB-backed data with direct test coverage (not the earlier stub-only
  coverage). Subsystem grouping quality fixed 2026-06-17 (was fragmenting
  into ~355 near-singletons on bare/undotted symbol names).
- [x] Role View - added 2026-06-17, wraps `Assessor.responsibility_map()`.
  Single-file filter scoping added same date (later session) after a real
  Windows bug where a one-file question returned the unfiltered full view.
- [x] QueryResult shape contract - closed 2026-06-17: full Select/Combine
  shape audited and locked across all 6 views / ~15 metrics after a real
  Windows-only AttributeError; `get_field()` added as the one correct way
  to read a QueryResult regardless of which valid metric was selected.
- [x] Determinism test invariant - closed 2026-06-17 (later): fixed to
  compare answer content via `get_field()` rather than raw AST text, since
  an LLM compiler at temperature=0.0 can validly pick between more than
  one registry-correct AST for the same question.

Criteria: passes the real regression suite (not the deleted print-only
`truth/test_harness.py`), no structural contradictions, deterministic
outputs.

**TIER 2 - USEFUL (signal quality).** Correct but evaluated for practical
value:
- [x] Hotspot ranking quality - resolved, builtins excluded from the
  degree-count ranking via the DB-authoritative builtin set.
- [x] Stability signal usefulness - EVALUATED 2026-06-17: verdict NOT YET
  USEFUL. Real signal, but its only contract source (null caller/callee in
  persisted symbol_references) is a raw-ingestion-corruption check, not an
  architectural stability check - trivially clean (142 stable / 0 unstable
  / 0 drift_signals) against the real 157-file project DB. Full findings in
  chronological log.
- [x] Integrity signal usefulness - EVALUATED 2026-06-17: verdict NOT YET
  USEFUL, and narrower than it should be - `Assessor.validation_summary()`
  bypasses the already-built `SystemValidator` class entirely (reimplements
  2 of its 4 checks inline, skips its `_validate_contracts` escalation
  path), and `IntegrityView.db_mismatches` is a permanently hardcoded `[]`
  ("no DB comparison anymore") - same orphaned-looks-like-a-signal shape as
  the old drift_signals bug, just never flagged. Full findings in
  chronological log; see also new open items 16-18 below.
- [x] Subsystem interpretability - EVALUATED 2026-06-17: verdict MIXED. The
  Row 4 fix holds - grouping now tracks real top-level package directories,
  not near-singletons. But (a) `_file_path_to_module()` (db_oracle.py)
  doesn't trim to a project-relative path the way the codebase's two
  existing `module_name_from_file_path()` utilities do, so subsystem
  identity strings are polluted with the full absolute filesystem path,
  and (b) the per-subsystem dependency list isn't builtin/stdlib-filtered
  the way hotspot ranking explicitly is, diluting the "what does this
  depend on" signal with noise (`len`, `str`, `RuntimeError`, ...). Full
  findings in chronological log.
- [x] Role classification interpretability - EVALUATED 2026-06-17: verdict
  NOT YET RELIABLE. The keyword-substring-on-callee-name heuristic produces
  false positives whenever a file merely calls/references another
  subsystem's function or type by name - confirmed against real data:
  `db_oracle.py` (a persistence/query file) gets flagged "graph"/
  "classification"/"reporting" because it references `GraphBundle`/
  `GraphEdge`, `embed_symbol`, and `print`. Orchestrator files (e.g.
  `run_engine.py`) correctly get every role, which is true but
  undifferentiating. Full findings in chronological log.

**TIER 3 - AUTHORITATIVE (system replacement).** All open: [ ] Assessor
fully uses Truth Layer exclusively, [ ] Oracle fully routed through Truth
Layer, [ ] Engine introspection migrated, [ ] legacy dual-path removed.

**TIER 4 - KERNEL (closed world complete).** Future state, all open: [ ]
all introspection flows through the Truth Query Algebra, [ ] no alternate
query systems exist, [ ] no ad-hoc graph inspection paths remain, [ ]
query language is frozen (no expansion allowed).

**Core principle (unchanged):** AI interprets the request, maps it to the
query algebra (only allowed primitives), executes deterministically via
the executor, then narrates the result (no invention) based on intent -
either a summarized human response or direct AI context. The Truth Kernel
itself stays deterministic throughout.

### 1c. Truth verification phase status (from Truth.md)

Truth.md's own Phase 0-6 plan for proving the Truth Layer is real, distinct
from the engine-refactor Phase 1-6 in section 1a above (same number range,
different track - don't conflate them).

- **Phase 0 (Freeze - verification only, no architecture/router/oracle/
  assessor changes): COMPLETE.**
- **Phase 1 (prove the Truth Layer is a real subsystem, not dead code):
  COMPLETE, verdict MET** as of 2026-06-16. All 5 (now 6) views produce
  real output from real DB-backed data; the assembled pipeline (NL ->
  router -> compiler -> AST -> executor -> views) has run end-to-end
  against both a seeded test DB and the real project DB, with permanent
  regression coverage. Full findings in the chronological log below.
- **Phase 2 (compare router path vs Truth Layer path for signal quality/
  noise/determinism/explainability): not started.** Can start whenever
  prioritized - nothing blocks it.
- **Phase 3 (identify missing truths via evidence, not guesses): done as
  a one-time audit, 2026-06-16/17.** Found 5 concrete gaps ("Rows 1-5"),
  see chronological log for the full evidence-based writeup. Pattern: two
  failure shapes, not five unrelated ones - "never captured" (Rows 1, 5)
  needing new ingestion, vs. "captured/computable but not wired or wired
  wrong" (Rows 2, 3, 4) needing only connection work.
- **Phase 4 (add one truth at a time, per missing capability): 3 of 4
  wired-but-broken rows closed.** Row 2 (role/purpose questions) closed
  2026-06-17 via the ROLE view. Row 3 (drift_signals hardcoded `[]`)
  closed 2026-06-17 (later session). Row 4 (subsystem fragmentation)
  closed 2026-06-17 (later still). Row 1's non-Row-2 remainder and Row 5
  (no intent/description field on `MutationEvent`) remain open - both are
  "never captured" and need new ingestion, not just wiring.
- **Phase 5 (determine if the query algebra needs expansion, based on
  repeated question patterns): not started**, implicitly answered "no
  expansion needed yet" by Phase 4's experience so far - every gap closed
  was a wiring fix within the existing AST shape, not a new primitive.
- **Phase 6 (AI compiler, only after Views/Planner/Executor are stable and
  questions are understood): live, earlier than the original plan
  expected.** The Ollama-backed compiler (`truth/query_compiler.py`) was
  wired in during the 2026-06-16 morning session (see chronological log)
  and is in active use, with the rule-based table as fallback.

---

## 2. Standing environment defects (canonical reference)

These were originally documented as Cowork sandbox defects (FUSE/virtiofs
file-bridge issues). The file-write truncation bugs (2a) and delete-path
permission bugs (2c) were confirmed to be Cowork-specific and are no longer
applicable when running Claude Code directly on Windows. Full incident
history: HISTORY.md section A.

### 2a. Stale/locked `.pyc` cache bug

Three confirmed variants: a locked/undeletable stale `.pyc` whose
mtime+size happens to match an intermediate source save and so passes
Python's normal cache-validity check; the same thing but where even
`rm -rf __pycache__` reports clean success while the file silently
remains; and a case where deletion succeeds but trusting it without
re-verification still misses the window. All three look the same at
runtime: `inspect.getsource()` shows correct code but the live function
object's actual behavior (or `dis.dis()` output) reflects the old version.

**Takeaway:** if `inspect.getsource()` and `dis.dis()` on the same live
function object ever disagree, or runtime behavior contradicts visibly-
correct source, suspect a stale `.pyc` before assuming the source is
wrong - `touch <source.py>` to force a recompile, since a `__pycache__`
deletion isn't always trustworthy on this mount even when it reports
success. Full variant detail: HISTORY.md section A.

### 2b. `sqlite3.OperationalError: disk I/O error` on new DB writes

New 2026-06-19, found while ingesting the three corpora in section 3 item
1. Any **new** sqlite DB file written to the dj2 mount hits
`disk I/O error` on the first write (table creation), even though reads
and writes against an *existing* DB on the same mount work fine.

**Confirmed fix:** run `PRAGMA journal_mode=MEMORY` immediately after
`sqlite3.connect()`, before any other statement. Sqlite's default
rollback-journal mode needs to create a `-journal` sidecar file
alongside the main `.db` on first write; the mount's I/O layer chokes on
that specific operation. Forcing the journal to live in memory instead
avoids it entirely.

**Caveat:** a stale `-journal`/`-wal`/`-shm` sidecar left over from an
earlier failed attempt (i.e. before this fix was applied) can re-trigger
the same error on a fresh connect, because sqlite attempts rollback
recovery against the orphaned journal before your `PRAGMA` call ever
runs. If this error recurs even with the pragma in place, check for and
clear sidecar files for that exact DB path first.

---

## 3. Open items / next steps

Closed/no-action items previously numbered 1 and 15-20 have been removed
from this list (2026-06-18 cleanup) - nothing deleted, see the Dashboard
above for the at-a-glance "recently done" line and HISTORY.md section B
for full writeups. Items 3+4+7, 9+13 (step 2), and 6+8 below have been
merged from the prior numbering to remove duplication while preserving
every source document's nuance - see each merged item's body for the
distinct angles folded in.

1. **[LOW, 2026-06-23] Triage broken test files** — `tests/test_ai_dungeon_master.py`
   and `tests/test_character_creation.py` have genuine syntax errors (stray closing
   braces, truncated `with` blocks) and are silently skipped by the Determined
   ingestion pipeline. Determine whether they have value, then fix or delete.

2. **[DONE, 2026-06-23] Run stub projector against game corpus** — ingested
   `world/` + `dungeon_neo/` into `game_corpus.db`, ran projector against 6 stubs.
   Found and fixed caller resolution bug (qualified vs bare callee names in graph_edges).
   Results: stub with resolved caller (semantic_match_subrace) produced best output;
   others got plausible-but-generic results from sibling context. Pattern confirmed:
   more caller context = better projections. Temp DB cleaned up.

3. **[READY, 2026-06-23] Cut over tools/analysis/ui -> Determined, then prune** —
   `local_agent.py --ui` (line 569) is the last live wire to `tools/analysis/ui/`.
   Cutover: redirect that import to `determined.ui.ui_server` (or remove the flag
   if Determined is the canonical entry point now). Then delete `tools/analysis/ui/`
   (4 source files: ui_server.py, console.html, style.css, preview.html, __init__.py).
   Determined UI has full feature parity + more. Gate: smoke test --ui flag works
   after redirect before deleting old files.

3. **[MEDIUM, 2026-06-23] Collaborative editor surface** — minimal editing panel
   in the Determined UI where AI projection and human edits meet. Projection is
   the opening move; both parties edit within the visible constraints (contracts,
   callers, callees shown alongside). Key property: edits committed here feed
   back into truth via re-ingestion of the changed file — not a scratchpad, a
   commit surface. Lives as a panel in the existing Determined UI next to query area.

4. **[MEDIUM, 2026-06-23] Wire stub projector into Determined UI** — "fill stub"
   button or sidebar shortcut that picks the highest-priority stub (by neighbor
   complexity from stub_density chart) and shows projection in the collab editor
   surface (item 3 above). Prerequisite for item 3 to be useful.

5. **[MEDIUM, 2026-06-23] Live sync loop: edit -> re-analyze -> update truth** —
   When a file is edited and applied (via collab editor or directly), re-ingest
   only that file, propagate changes through the truth kernel, and update all
   downstream projections (YAML, stubs, docs). Before application: speculative
   "what-if" mode. After application: authoritative — truth changes and all
   recordings of it must match. Stale projections show red. This is what makes
   the system live rather than a one-shot analysis snapshot.
   Requires: file watching or explicit "apply" trigger, incremental re-ingestion
   (single file, not full corpus), propagation through graph edges to find
   downstream affected symbols.

6. **[LOW/MAC-ONLY, 2026-06-23] treedocs integration** — dandylyons/treedocs
   (https://dandylyons.github.io/treedocs/) is a Swift CLI that maintains a
   `treedocs.yaml` mapping the repo file tree with human-readable descriptions,
   version-controlled, with staleness detection (descriptions that no longer match
   files show red). Complementary to the truth kernel: treedocs projects truth
   outward into document design space; the kernel projects inward from code.
   Mac-only (Swift). Lower priority. Explore after sync loop (item 5) is solid.

8. **[FUTURE, 2026-06-23] Self-Harness pattern for autonomous eval improvement**
   — arXiv 2606.09498. Three-stage loop: mine failure patterns from execution
   traces, propose minimal harness changes, validate via regression before
   accepting. Direct application: the ADVERSARIAL suite in claude_eval.py
   currently finds routing gaps that are fixed by hand. Self-Harness is the
   version where the agent proposes the fix itself. Prerequisite: traces must
   be trustworthy signal, meaning the tool needs to be stable first. Good
   upgrade target once the tool is past active development churn.

9. **[CONSIDER, 2026-06-23] showDirectoryPicker for collab editor** —
   File System Access API (Chrome). Instead of typing a path into Determined's
   Analyze field, user clicks and picks a folder via OS dialog. Local-first,
   no upload. Relevant when building the collab editor surface (item 3).
   Chrome-only currently, which is fine for a local dev tool.


7. **[LOW/MAC-ONLY, 2026-06-23] md-utils integration** — DandyLyons/md-utils
   (https://github.com/DandyLyons/md-utils). Swift CLI + library for programmatic
   Markdown manipulation: frontmatter CRUD (12+ subcommands, JMESPath search),
   TOC generation, section reordering, Obsidian wikilink parsing + broken link
   detection, Open Knowledge Format (OKF) bundle support. Not staleness-checking
   itself, but the infrastructure that staleness detection sits on top of.
   Relationship to this system: truth kernel produces facts per file; treedocs
   records them in treedocs.yaml; md-utils is the machinery for keeping that
   document in sync (read frontmatter, update it, flag stale entries). The sync
   loop (item 5) drives all three. Mac/Swift, lower priority.

2. **[TOP PRIORITY, NEW 2026-06-18] Evaluate widening the ingestion test
   corpus.** The analysis tool has so far only ever ingested itself (157
   files, its own self-corpus) plus regression fixtures - DESIGN.md
   section 3 flags this explicitly as an open assumption: the reasoning
   layer is "proven, but only proven on one corpus," unverified on a
   differently-shaped codebase. Candidates to evaluate as additional test
   cases, each exercising different capabilities:
   - The game's own source: `world/`, `engine/`, `resolver/`,
     `dungeon_neo/` - real target-domain code, generalizes old item 13
     step 1 ("widen ingestion scope") from a fixed first-step into part
     of this broader evaluation.
   - `tools.old/` - already in-repo, untouched by the self-analysis run
     so far, a reasonable next corpus before the game code.
   - Possibly downloadable open-source projects, for capabilities (or
     codebase shapes/sizes) the in-repo corpora don't exercise.
   Sequencing across these is intentionally **not** fixed - Bart was
   explicit that this is "a listing... not an ordering," and wants
   proposed impacts of alternative orderings rather than one imposed
   priority. Items 13 and 14 below (old items 22/23) were a stated
   prerequisite before widening scope, since both bugs could otherwise
   produce misleading or crashing results on a differently-shaped corpus
   - both are now fixed, so this item is unblocked. Verify whichever
   corpus is chosen first with a regression test asserting a known real
   symbol from that corpus appears correctly in `graph_edges` after
   ingestion (the same bar old item 13 step 1 set).

   **Status update 2026-06-19 (later, this session): ingestion actually
   run against all three non-game-code candidates, all three landed.**
   Used `EngineRunner().run(corpus=..., project_prefixes=[], repo_root=...,
   connection=...)` directly (the headless invocation pattern from
   `tests/core/test_engine_smoke.py` - `run_engine.py`'s own `__main__` is
   GUI-only via tkinter and unusable here). Row counts confirmed by direct
   query against each resulting DB:
   - `tools.old/`: 73 files, 2764 `graph_edges`.
   - `external_corpora/flask/src`: 24 files, 800 `graph_edges`.
   - `external_corpora/sqlalchemy/lib`: 255 files, 20769 `graph_edges`.

   Verification bar this item set ("a regression test asserting a known
   real symbol from that corpus appears correctly in `graph_edges`") is
   met at the time; test file later removed 2026-06-19 - `tools.old/`
   is not actively maintained and the 45-second ingestion run added noise
   to the suite with no ongoing value.

   Hit two new environment issues doing this, both now logged as standing
   defects rather than one-offs: a `disk I/O error` on any brand-new
   sqlite DB write to this mount (section 2d - fixed with
   `PRAGMA journal_mode=MEMORY`), and the delete-path "Operation not
   permitted" bug (2c) turning out not to be scoped to
   `external_corpora/` after all - reproduced on new files anywhere in
   the mount, worked around the same way (`mv` aside).

   Remaining candidate from this item's original list: the game's own
   source (`world/`/`engine/`/`resolver/`/`dungeon_neo/`) - **decided
   2026-06-19 (later session) to do this next, ahead of item 2 below** -
   see Dashboard "Now / next" item 1 for the reasoning (Row 5's new
   ingestion-capture design should be informed by real target-domain
   mutation shapes, not guessed). Not yet started. Cleanup from last
   session's run is fully resolved as of 2026-06-19 (later):
   `_sandbox_cleanup_needed/` deleted by Bart, and the two
   `.git_broken_skeleton` dirs are confirmed gone on his actual machine -
   their lingering visibility to `stat`/`rm` inside the sandbox is a stale
   virtiofs mount-cache artifact, not a real file (Cowork sandbox defect,
   now resolved). No outstanding Windows-side action remains.
2. **Truth.md Phase 1 Row 1 remainder + Row 5: DONE 2026-06-19.**
   Docstring-based intent capture wired end-to-end:
   - `MutationEvent.intent` field added - populated from the containing
     function's docstring first line at parse time.
   - `ClassRepresentation.docstring` field added - captured via
     `ast.get_docstring()` at parse time (functions already had this field,
     it just wasn't being persisted).
   - `functions` and `classes` tables gained `docstring` column;
     `mutations` table gained `intent` column. All three INSERT paths updated.
   - `IntentView` added as the 7th Truth Layer view (`build_intent_view()`
     in `truth/views.py`) - queries `functions`/`classes`/`mutations` tables
     directly, returns per-item docstrings + coverage stats.
   - `INTENT` registered in `QueryPlan.VALID_METRICS` and
     `QuerySemanticsRegistry.VALID_FILTER_KEYS`. `Assessor.intent_view()`
     and `Assessor.all_views()` updated (now returns 7 views).
   - 7 regression tests in `tests/regression/test_intent_view_wiring.py`.
   - Full suite: 127/127 passing (was 120).
3. **Engine/Assessor boundary completion - DONE 2026-06-19** (merged old
   items 3, 4, and 7):
   - [x] Move query execution fully into Assessor: `route_query` moved to
     `assessor/query_router.py`. New signature: `route_query(text, oracle, ...)`
     - no graph/fn params. `api/oracle_router.py` is now a thin re-export.
     `task_generator.generate_task_md` and `task_rereferencer.rereference_task_md`
     take `oracle` directly. `Assessor.generate_task_md/rereference_task_md`
     simplified (no longer fetch graph snapshot). DBOracle is pure data
     access: `get_edge_maps`, `discover_seed_symbols`, `builtin_symbols`.
   - [x] DB-only execution mode: `QuerySession.run_query()` no longer calls
     `get_snapshot_graph()`. Expansion uses `DBOracle.get_edge_maps()` -
     plain `(forward, reverse)` dicts from `graph_edges`, no GraphBundle.
     `_bind_snapshot()` retained as legacy stub for non-query callers only.
   - Old item 7 (architecture split / contracts layer): partially addressed
     by moving routing to assessor layer. Remaining: enforce the DB-only
     boundary more formally, formalize the contracts layer. Still open as
     future cleanup (low urgency now that the query path is clean).
4. **Engine refactor Phase 5: DONE 2026-06-19.** Named reasoning primitives
   (`seed_explanation()`, `expansion_explanation()`, `intent_mapping_trace()`,
   `node_reasons()`, `seed_paths()`, `expansion_edges()`) are implemented on
   `QuerySessionResult` and backed by live trace data from `_route_expand()`.
   Verified: `node_reasons` and `seed_paths` are populated by `_route_expand`
   and flow through `route_query` -> `run_query` -> `QuerySessionResult`.
5. **Trace-weighted ranking (explicitly deferred - merges old items 6 and
   8, same upgrade described from two angles):** replace heuristic
   pruning/scoring with trace-weighted ranking derived from expansion
   provenance (old Phase 6); equivalently, upgrade the ranking refinement
   layer from heuristic scoring to trace-informed scoring (old item 8).
   "Later" per the original Phase 6 note - revisit once query-expansion
   quality (item 6 below) has been validated against real usage, since
   that validation will inform what "trace-informed" should actually
   weight.
6. **Query-expansion validation / `impact_query` semantics audit: DONE
   2026-06-19.** Audited against real self-corpus DB using
   `tools.analysis.truth.query_ast.Select` (69 incoming callers, most-called
   project symbol) as the probe target. Findings:
   - `impact_query` is NOT a pure transitive reverse-dependency closure.
     It expands from a seed SET (token-matched related symbols, not just
     the target), then walks reverse edges at depth-2 from all seeds.
     Result is a neighborhood superset - 86 nodes vs. 47 in the real
     BFS closure. The depth-2 budget was not the limiting factor for this
     corpus (real graph was only depth-2 deep for this symbol anyway);
     seed over-broadness is the real shape of the behavior.
   - The one node BFS found that router missed (`<module>`) is a noise
     artifact already correctly filtered by `symbol_noise.py` line 65
     (`startswith("<")`). Fix #4 is already done - not a gap.
   - `<module>` aside, router returns a SUPERSET of the BFS closure, not
     a subset - the depth budget is not silently truncating anything for
     this corpus.
   **Implications for task.md (item 10):**
   - task.md must NOT present router results as "exact caller set" -
     they are "impact zone" (neighborhood). Call it that explicitly.
   - task.md should show TWO tiers: "Direct callers (confirmed)" from
     `graph_edges WHERE callee = ?` and "Impact zone (may need review)"
     from the router. Both are useful; conflating them is misleading.
   - Fix #2 (implemented 2026-06-19): added `seeds` override parameter
     to `route_query()` - when the caller passes seeds directly, seed
     discovery is skipped. This makes "what depends on X" when X is a
     known symbol use X as the only seed, giving a true reverse closure
     from that specific symbol rather than a token-match neighborhood.
   - Game corpus depth audit DONE 2026-06-20: depth-2 is sufficient for
     world_corpus.db. Max real game chain depth is 3 (random_fill_all ->
     random_fill_field -> get_skill_list callers); depth-3 miss is a
     low-level utility, not an architectural chokepoint. The <module>
     depth-3 miss is noise (already filtered). The DM->world->dungeon_neo
     concern is NOT a depth budget problem - it is a per-corpus-DB
     limitation: cross-corpus calls (3 edges: calculate_movement ->
     dungeon_neo.constants, generate_quest -> dungeon_neo.campaign.Quest,
     __init__ -> dungeon_neo.movement_service.CharacterMovementService)
     are recorded as callee names but dungeon_neo symbols have no entries
     in world_corpus's symbols table, so reverse chains can't cross the
     corpus boundary. Fix is the merged game_corpus.db (TRACKER item 3
     prerequisite). Depth budget itself: no change needed.
7. **Reasoning layer remainder:** answer architectural questions from
   graph truth directly; identify structural influence/dependency zones;
   support oracle-style interrogation queries; an oracle execution
   feedback loop (query -> refinement signal).
8. **Test suite hygiene:**
   - [x] Oracle CLI smoke test harness: DONE 2026-06-19.
     `tests/regression/test_oracle_cli_smoke.py` (4 tests). Exercises
     `DBOracle` + `route_query` + `QuerySession.run_query` against the
     real self-corpus DB. Skips gracefully if DB absent. Suite: 146/146.
   - [x] Symbol ordering DB-deterministic: verified 2026-06-19. All
     production queries use `ORDER BY`; Python sorts used for
     provenance ranking. No test asserts insertion-order positions.
   - [x] Dual routing paths in tests: DONE 2026-06-20. Deleted
     `tests/core/` and `tests/debug/` - both tested the deprecated
     pre-oracle graph/identity layer, neither was in the regression suite.
   - ACCEPTED DEBT (2026-06-20): alias_map normalization, identity factory
     double-construction in parse_ast.py, and classification import
     inconsistency in graph/symbol_classifier.py are all pre-oracle layer
     issues with zero correctness impact on the production query path.
     Leave until the graph/identity layer is formally deprecated or a
     specific bug forces it.
9. **Truth Kernel Tier 3/4 (system replacement / closed-world complete):**
   all items open and explicitly future-state - Assessor fully on the
   Truth Layer exclusively, Oracle fully routed through it, engine
   introspection migrated, legacy dual-path removed, no ad-hoc graph
   inspection paths remaining anywhere, query language frozen.
10. **Agent Capability Layer build order, remainder (old item 13 steps 4
    and 5 - steps 1 and 2 folded into items 1 and 6 above):**
    1. [x] Build the task.md generator off the ripple query from item 6
       above. Markdown, plain checklist format, matching this doc's
       voice. DONE 2026-06-19: `tools/analysis/agent/task_generator.py`,
       wired as `Assessor.generate_task_md(symbol, out_path=None)`.
       Two-tier output: direct callers (graph_edges WHERE callee=?) +
       impact zone (route_query seeds override). 7 regression tests in
       `test_task_generator.py`. 102/102 passing.
    2. [x] Build the "re-reference a task.md" path: read file -> extract
       the originating query -> re-run against current DB -> diff ->
       report. DONE 2026-06-19: `tools/analysis/agent/task_rereferencer.py`,
       wired as `Assessor.rereference_task_md(path, diff_out_path=None)`.
       Returns diff dict + rendered Markdown. 12 regression tests in
       `test_task_rereferencer.py`. 114/114 passing.
    As with item 1 above, Bart's direction is that this is a listing of
    capability pieces, not a locked sequence - propose impacts of
    alternative orderings (e.g. doing corpus-widening work in parallel
    with this rather than strictly before it) rather than assuming one.
12b. **Intent Layer - semantic summaries + knowledge artifacts: DONE
    2026-06-19.**
    - Sub-layer A (AI-generated semantic summaries): `semantic_summaries`
      table added via `ensure_schema()`. `intent/semantic_summary.py`:
      `get_or_generate_summary()` (lazy generation + cache), `get_summary_if_fresh()`
      (read-only, no side effects), `list_summaries()`. LLM backend: local
      Ollama (same model as query_compiler.py); heuristic stub fallback if
      Ollama unreachable. Source_hash staleness detection. Wired as
      `Assessor.semantic_summary()`, `Assessor.semantic_summary_if_fresh()`,
      `Assessor.list_semantic_summaries()`.
    - Sub-layer B (knowledge artifacts): `knowledge_artifacts` table added
      via `ensure_schema()`. `intent/knowledge_artifact.py`:
      `add_artifact()`, `get_artifacts()` (provenance-ranked), `list_artifacts()`,
      `delete_artifact()`, `highest_provenance()`. Valid kinds:
      file_purpose / strategy_decision / query_finding / design_note /
      known_issue. Provenance rank: human-confirmed > ai-confirmed-by-human
      > ai-generated. Wired as `Assessor.add_artifact()`,
      `Assessor.get_artifacts()`, `Assessor.list_artifacts()`,
      `Assessor.delete_artifact()`, `Assessor.highest_provenance_artifact()`.
    - 27 regression tests in `tests/regression/test_intent_layer_ab.py`.
      Full suite: 142/142 passing (was 127).
13. **Truth Kernel Board Tier 0 (DONE 2026-06-20):** DESIGN.md
    view-legality and Combine-legality lists updated to list all 7 views
    (STRUCTURE/STABILITY/INTEGRITY/SUMMARY/SUBSYSTEM/ROLE/INTENT with dates),
    added missing `(STABILITY, INTEGRITY)` pair, noted ROLE/INTENT are
    Select-only. Stale "5 views, now 6" prose fixed throughout.
14. **knowledge.db - shared knowledge overlay: DONE 2026-06-20.**
    Design: DESIGN.md section 7. All steps complete:
    - [x] `oracle/knowledge_oracle.py`: `KnowledgeOracle` wrapping
      `knowledge.db`; creates `knowledge_artifacts` (with `file_hash`,
      `needs_review` columns) and `semantic_summaries` tables.
      `KnowledgeOracle.alongside(corpus_db_path)` opens `knowledge.db`
      next to any corpus DB.
    - [x] `persistence/persistence_engine.py`: `ensure_schema()` now
      creates corpus tables only; knowledge tables live in KnowledgeOracle.
    - [x] `intent/knowledge_artifact.py`: added `file_hash`/`needs_review`
      columns + migration (ALTER TABLE, idempotent); added
      `flag_stale_artifacts()` for ingestion hook. SELECT queries updated.
    - [x] `assessor/assessor.py`: `Assessor.__init__` takes optional
      `knowledge` param; auto-opens `knowledge.db` alongside corpus DB
      when oracle has `db_path`. All artifact methods route to knowledge
      conn; return [] / raise if knowledge is None.
    - [x] `agent/task_generator.py`: `generate_task_md` takes optional
      `knowledge_conn`; `_known_findings()` queries knowledge conn with
      exact + `file::symbol` LIKE match; stale artifacts flagged
      `[STALE - needs review]` in output. Template bug fixed (unsubstituted
      `{symbol}` in direct-callers prose).
    - [x] Existing `generate_location_from_potential` artifact migrated
      from self-corpus DB to `knowledge.db` (row id 1 in knowledge.db).
    - [x] Tests updated: `test_intent_layer_ab.py` (ensure_schema tests
      now call table-create fns directly), `test_task_generator.py`
      (artifact tests use separate knowledge conn). Suite: 148/148.
    - Ingestion staleness hook (`flag_stale_artifacts` call in
      `EngineRunner.run()`) left as a follow-on - schema and function are
      ready, just not wired into the ingest loop yet (low urgency until
      game corpus files start changing actively).
12. **Orphaned-module disposition review (hole vs. dead): INVESTIGATED
    AND REPORTED 2026-06-19.** Evaluated all 9 originally-listed
    candidates - `resolution/symbol_origin_resolver.py`,
    `inspection/explain_file.py`, `utilities/reachable_print_trace.py`,
    `context/build_context_packet.py`, the `contracts/` cluster
    (`contract_validator.py`, `contract_lifecycle.py`,
    `contract_health_aggregator.py`, `contract_types.py`, plus 3 empty
    stub files), `api/get_llm_context.py`, `api/query_entry.py`, the
    empty `orchestration/` directory, and
    `specification/tool_system_contract.json` - via actual import/call-site
    wiring checks (whole-tree grep for each symbol/module), not just
    surface-reading file contents, per this project's standing principle
    of never assuming dead from surface signals alone. **No
    integrate/dispose/delete action taken on any of it - this item's own
    gate requires reporting to Bart first, which is what this entry is.**
    Per-item disposition:
    - **Deleted 2026-06-19 (superseded/empty):** `context/build_context_packet.py`
      (superseded by `context/build_context_bundle.py` - same structural
      fetch, bundle has the correct authority model; packet explicitly
      empties `dependencies`/`referenced_symbols` with "don't trust"
      comments); `api/query_entry.py` (superseded by
      `inspection/explain_file.py` which is now being wired - returns
      only raw counts, no callers/callees/violations/summary); 3 empty
      stub files (`analysis_contract.py`, `failure_contract.py`,
      `representation_contract.py`, confirmed 0 bytes). Also confirmed
      dead, though this is not a new finding:
      `contracts/contract_map.py` -> `contracts/contract_observer.py` ->
      `validation/contract_validation_pass.py` - existing regression
      tests (`tests/regression/test_drift_signals_wiring.py` line 15,
      `tests/regression/test_integrity_view_wiring.py`) already document
      this exact path as zero-caller, and `assessor/assessor.py`'s own
      comment (line 264) confirms the live pipeline replaced it with
      direct DB queries (`evaluate_file_contracts()` is explicitly
      labelled "a no-op stub" there).
    - **Kept - real capability, wire when conditions are met:**
      `utilities/reachable_print_trace.py` - `explore_call_routes()`
      returns explicit traversal *paths* with depth and fanout at each
      node, not just node membership. Different from `impact_query`'s
      node-set expansion. Wire into the Phase 5 trace API
      (`expansion_explanation()`) when that work starts - the `main()`
      at the bottom is a throwaway dev script, ignore it.
      `contracts/contract_health_aggregator.py` +
      `contracts/contract_lifecycle.py` - correct, complete pipeline:
      drift rows -> stability scores + trend direction ->
      ACTIVE/STABLE/DEGRADING/UNSTABLE/STALE/OBSOLETE states with
      recommendations. Not wired because the drift signal they'd consume
      is trivially clean (contracts only catch ingestion-time null checks
      today, not real architectural drift). Wire when the contract layer
      tracks real architectural concerns - these plug straight in without
      changes. `contracts/contract_validator.py` - `ContractRuntimeValidator`
      validates pipeline stages at runtime (edge conservation,
      classification-not-leaking-into-persistence,
      snapshot-graph consistency) - different from `SystemValidator`'s
      post-build checks. Blocker: `load_contract.py`'s broken JSON path
      (loads wrong file, KeyErrors on `domains`). Wire when that chain
      is fixed.
    - **One genuine hole (missing capability that should be wired):**
      `inspection/explain_file.py` is a complete, working, DB-backed
      per-file report generator (imports, symbol density, top
      callers/callees, contract violations, a heuristic semantic
      summary) that nothing currently calls. TIER 2's Role-view
      evaluation above already wants exactly this kind of per-file
      explainability signal - this looks ready to serve that need
      directly rather than needing to be built from scratch.
    - **Not actually orphaned despite zero in-repo callers:**
      `api/get_llm_context.py` - its own docstring identifies it as "the
      ONLY function external systems should call" for LLM-context
      retrieval. Zero in-repo callers is expected here, not a sign of
      dead code: its intended consumer is the future agent CLAUDE.md
      describes, which doesn't exist yet. Recommend: keep as-is, revisit
      only once an actual external consumer exists to confirm the shape
      still fits.
    - **An unfinished-but-coherent feature, not three unrelated items:**
      `contracts/contract_types.py` (typed dataclasses - `SystemContract`,
      `DomainContract`, `OutputContract`, `DependencyRules`,
      `CoreInvariants`, `StabilityPrinciple`) and
      `specification/tool_system_contract.json` (the domains-shaped spec
      those dataclasses exactly mirror: ingestion/representation/
      analysis/indexing/orchestration domains, output_contract,
      dependency_rules, core_invariants, stability_principle) are a
      matched pair - confirmed nothing ever actually loads that JSON file
      into those dataclasses anywhere. The empty `orchestration/`
      directory is the third piece of this same unfinished thread: that
      same spec file's own "orchestration" domain definition ("Controls
      execution flow across all other domains... must not implement
      domain logic") describes exactly what should live there, and
      nothing has been written yet. Recommend treating these three as one
      decision, not three: either finish wiring the typed loader + start
      building the orchestration layer the spec describes, or
      consciously shelve all three together as a deferred design, not
      "delete the loader, ignore the spec, leave the directory empty by
      accident."
    - **New finding, outside the original 9-item list but same
      directory, worth flagging alongside it:** `contracts/
      load_contract.py` (and its consumers `parse_contract.py`/
      `scan_contract.py`) load a *different* `tool_system_contract.json`
      - the one physically sitting in `contracts/` itself
      (`schema_version: 3`, a "modules" pipeline-status document, not the
      "domains" spec above) - and then call `contract["domains"][...]`
      on it. That file has no `domains` key at all, so this chain would
      raise `KeyError` immediately if anything ever called it. Currently
      zero callers, so this is dormant rather than actively broken in
      production - flagging so nobody tries to wire `parse_contract.py`/
      `scan_contract.py` in as-is without first fixing which JSON file
      they're meant to read.
    - **Confirmed no overlap with item 2 (Truth.md Row 1/Row 5):** none
      of the above touch `MutationEvent`, intent/description capture, or
      "why was this change made" semantics at ingestion time - the
      "intent" hits in the contracts cluster are all the word
      "intentionally"/"system intent" in docstrings describing contract
      *design* intent, unrelated to mutation-author intent. Row 5
      remains genuinely unstarted new ingestion work, not something this
      review accidentally already solved or could accidentally break.
13. **Embedding-fallback crash risk in seed discovery: DONE 2026-06-18.**
    `oracle/db_oracle.py`'s `discover_seed_symbols_semantic()` previously
    only caught `ImportError` around the top-level
    `import numpy`/`from ...embedding_model import embed_text`
    statements - any failure *after* that point (the actual model load
    inside `embedding_model.get_model()`, which can fail at call time due
    to a missing model cache, no network access, a corrupted download,
    etc.) propagated uncaught all the way to every `ask.py` query. Fixed:
    the embedding-index build and lookup are now wrapped in
    `except Exception`, logging a warning (`_logger.warning(...)`, new
    module logger added) and falling back directly to `_discover_token()`
    - not via `discover_seed_symbols()`, since that path re-enters
    `discover_seed_symbols_semantic()` through `_discover_combined()` and
    would recurse forever against a failure that won't go away on retry.
    Proof: `tests/regression/test_embedding_seed_discovery_fallback.py`
    (3 tests) - one against the real environment (sentence-transformers
    genuinely not installed in this sandbox, confirming the fix handles
    the exact naturally-occurring case), one simulating a non-ImportError
    failure (`OSError`) to prove the broader exception net works and
    doesn't recurse, one confirming the public `discover_seed_symbols()`
    entrypoint used by `route_query()`/`QuerySession.run_query()` doesn't
    crash either. Full regression suite: 80/80 after.
14. **Dead `runtime_bindings` wiring: DONE 2026-06-18.** `parse_ast()`
    (`ingestion/parse_ast.py`) previously set `FileAnalysis.runtime_bindings`
    directly from its caller-supplied parameter - always `{}`, since
    `scan_project_files.py` line 192 hardcodes
    `runtime_bindings = {}  # still placeholder for now` - even though
    `_extract_runtime_bindings()` was already being called for real
    inside `_extract_symbol_references()`, just discarded after its own
    internal use. Production classification
    (`classify_references.py`'s `route_symbol(runtime_bindings=
    analysis.runtime_bindings, ...)`) therefore always received `{}`, so
    the "runtime" bucket was permanently empty in real output. Fixed:
    `parse_ast()` now also calls `_extract_runtime_bindings()` itself and
    merges the result onto `runtime_bindings` before it's stored on
    `FileAnalysis` - deliberately redundant with
    `_extract_symbol_references()`'s internal call rather than changing
    that function's return signature, to avoid touching its other direct
    caller (`tests/debug/test_symbol_pipeline_trace.py`).
    `scan_project_files.py`'s placeholder line is left untouched (still
    correctly describes the parameter it passes; the fix lives entirely
    inside `parse_ast()`). Proof:
    `tests/regression/test_runtime_bindings_wiring.py` (3 tests) - new
    fixture `tests/fixtures/sample_project/runtime_bucket_case.py`
    (`ai = engine.ai_system; ai()`) run through the real pipeline
    (`parse_ast()` -> `classify_references()`, the same two calls
    `analyze_files()` chains in production) confirms the reference is
    classified `bucket='runtime'`; a regression-guard test confirms
    forcing `runtime_bindings` back to `{}` (the exact pre-fix production
    state) loses the bucket on the same fixture, proving this test would
    have caught the original bug. Full regression suite: 80/80 after.

15. **Agent search layer: token-aware symbol lookup (open).** Current
    `search_symbols` uses substring matching on the full term. This means
    `world_controller` finds `set_world_controller` (a function) before
    `WorldController` (the class), because no substring of the class name
    matches the snake_case query. The CamelCase conversion in
    `_camel_variant()` (added 2026-06-21) is a workaround for the common
    case, but doesn't generalize: a query with tokens that don't form a
    clean CamelCase class name still hits the wrong symbol. The principled
    fix is a token-aware search: split `world_controller` into
    `["world", "controller"]`, find all symbols containing both tokens,
    rank by type (class > function > variable). Side benefit: would surface
    naming-convention relationships (`WorldController` class vs
    `set_world_controller` function) as useful context rather than a
    collision to route around. Requires changes to `search_symbols` in
    `agent_tools.py` and the NEED-resolution path in `agent_resolver.py`.
    Defer until substring workaround proves insufficient on more queries.

16. **"Why was this file included?" explainability on context bundles (open).**
    Every retrieved node should carry a `reason_included` annotation - e.g.,
    "included because `run_analysis_pipeline` imports `scan_project_files`."
    Currently only `query_session.py` mentions this concept; the context
    assembly layer does not surface traversal reasons on its output. This is
    a real debugging aid when AI retrieval goes wrong - the LLM (and the
    developer) can see why a file is present, not just that it is. Gap
    identified 2026-06-23 from Tool Plan.md section 3.2.

17. **Retrieval modes: heuristic profiles per task type (done 2026-06-23).**
    Added `debug_query` and `mutation_query` intents to `query_router.py`:
    detection in `_detect_intent`, traversal budgets in `intent_budget`,
    primitive selection in `_select_primitives`. `debug_query` gets
    reverse-heavy traversal (depth 2) + findings/impact/context primitives.
    `mutation_query` gets balanced traversal + mutations/impact/context primitives.
    Both have matching heuristic patterns in `agent_resolver.py` `_HEURISTICS`
    that map natural-language debug/mutation questions to pre-wired NEED sequences
    (findings, todos, callers, callees). 279/279 regression tests passing.

18. **Safe-zone / hot-zone risk annotation on context output (done 2026-06-23).**
    New `risk_annotator.py` with `score_risk(oracle, symbol)`: pure DB scoring
    (in_degree, out_degree, mutation_count) -> HOT/WARM/SAFE + reasons.
    HOT: in_degree >= 5, or (in_degree >= 3 AND mutations > 0).
    WARM: in_degree >= 2, or mutations > 0. SAFE: everything else.
    Wired into `symbol_brief` (risk line prepended to every brief output).
    New `risk_profile` standalone tool registered in TOOLS dispatch table.
    Pattern added to _PATTERNS ("risk profile for X"), heuristic added to
    _HEURISTICS for "is X safe to modify / how risky is X / blast radius of X".
    Smoke test on self-corpus: _detect_intent correctly scores WARM (2 callers).
    279/279 regression tests passing.

---

## 4. Chronological session log

Moved to HISTORY.md (section B) as part of the 2026-06-18 TRACKER/HISTORY
split - full dated session-by-session record, verbatim, nothing dropped.
