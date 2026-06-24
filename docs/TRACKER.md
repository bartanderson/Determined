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

**Last session (2026-06-24, session 16):** Migration complete.
tools/analysis/ deleted from dj2. Engine now lives exclusively in Determined.
28 regression test files (279 tests) passing. knowledge.db intact (77KB).
dj2 is game code only. Both repos committed and pushed.

**Previously (2026-06-23, session 15):** Items 16/17/18 done.
Item 16: subgraph_around() tracks reasons dict (explainability).
Item 17: debug_query/mutation_query intents in query_router.py + agent_resolver.py heuristics.
Item 18: risk_annotator.py (HOT/WARM/SAFE), symbol_brief risk line, risk_profile tool.
Also: is_stub detection chain, stub projector (Ollama-driven), auto-discovery to completion loop.
279/279 tests passing throughout.

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

All closed items have been moved to HISTORY.md. Items below are genuinely open.
Last cleaned: 2026-06-24.

1. **[LOW] Triage broken test files** - `tests/test_ai_dungeon_master.py`
   and `tests/test_character_creation.py` have genuine syntax errors and are
   silently skipped by the ingestion pipeline. Fix or delete.

2. **[MEDIUM] Collaborative editor surface** - minimal editing panel in the
   Determined UI where AI projection and human edits meet. Projection is the
   opening move; edits committed here feed back into truth via re-ingestion.
   Not a scratchpad - a commit surface. Lives as a panel next to the query area.

3. **[MEDIUM] Wire stub projector into Determined UI** - "fill stub" button
   that picks the highest-priority stub (by neighbor complexity from
   stub_density chart) and shows projection in the collab editor (item 2).
   Prerequisite for item 2 to be useful.

4. **[MEDIUM] Live sync loop: edit -> re-analyze -> update truth** - when a
   file is edited and applied, re-ingest only that file, propagate changes
   through the truth kernel, update downstream projections. Before application:
   speculative "what-if" mode. After: authoritative. Stale projections show red.
   Requires: incremental re-ingestion (single file), propagation via graph edges
   to find downstream affected symbols.

5. **[LOW] Token-aware symbol search** - current `search_symbols` uses substring
   matching, so `world_controller` finds `set_world_controller` before
   `WorldController`. `_camel_variant()` workaround (added 2026-06-21) handles
   the common case. Principled fix: split into tokens, rank by type
   (class > function > variable). Defer until workaround proves insufficient.

6. **[LOW] Wire `utilities/reachable_print_trace.py`** - `explore_call_routes()`
   returns explicit traversal paths with depth and fanout (different from
   `impact_query`'s node-set expansion). Wire into Phase 5 trace API
   (`expansion_explanation()`) when that work starts.

7. **[DEFERRED] contracts/orchestration feature decision** -
   `contracts/contract_types.py` + `specification/tool_system_contract.json`
   are a matched pair (typed dataclasses + domains-shaped spec) but nothing
   loads the JSON into the dataclasses. The empty `orchestration/` directory
   is the third piece. Decision needed: finish wiring the typed loader and
   build the orchestration layer, or consciously shelve all three together.
   `contracts/load_contract.py` has a dormant KeyError bug (loads wrong JSON
   file, calls `contract["domains"]` which doesn't exist in it) - fix before
   wiring any consumer.

8. **[FUTURE] Truth Kernel Tier 3/4** - Assessor fully on Truth Layer,
   Oracle fully routed through it, engine introspection migrated, legacy
   dual-path removed, query language frozen. Explicitly future-state.

9. **[FUTURE] Trace-weighted ranking** - replace heuristic pruning/scoring
   with trace-weighted ranking from expansion provenance. Revisit after
   real usage patterns are clear.

10. **[FUTURE] Self-Harness pattern** - arXiv 2606.09498. Mine failure
    patterns from ADVERSARIAL suite traces, propose minimal harness changes,
    validate via regression. Good upgrade once tool is past active churn.

11. **[CONSIDER] showDirectoryPicker for collab editor** - File System Access
    API (Chrome). OS folder picker instead of typing a path. Chrome-only,
    fine for a local dev tool. Relevant when building item 2.

12. **[MAC-ONLY] treedocs + md-utils** - dandylyons/treedocs (Swift CLI,
    repo-tree descriptions with staleness detection) + DandyLyons/md-utils
    (Swift CLI, programmatic Markdown manipulation). Complementary to truth
    kernel; drive the sync loop (item 4). Mac/Swift only, lower priority.

---

## 4. Chronological session log

Moved to HISTORY.md (section B) as part of the 2026-06-18 TRACKER/HISTORY
split - full dated session-by-session record, verbatim, nothing dropped.
