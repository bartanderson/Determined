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

**Last session (2026-06-25/26, session 19):** Multiple bug fixes + corpus scoping + dj2 design docs.
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

**Before that (2026-06-23, session 15):** Items 16/17/18 done.
Item 16: subgraph_around() tracks reasons dict (explainability).
Item 17: debug_query/mutation_query intents in query_router.py + agent_resolver.py heuristics.
Item 18: risk_annotator.py (HOT/WARM/SAFE), symbol_brief risk line, risk_profile tool.
Also: is_stub detection chain, stub projector (Ollama-driven), auto-discovery to completion loop.
279/279 tests passing throughout.

**Earlier history (sessions 1-9, 2026-06-19 to 2026-06-22):** Full agent pipeline built and validated.
24 tools, 30+ heuristic patterns, PICK/ADVERSARIAL eval commands, game_corpus.db merged,
adversarial validation found and fixed 9 routing gaps. Full detail: HISTORY.md.

**Item 15 done (session 18):** Pattern executor built and wired in. Model no longer picks
tools when a named pattern matches - executor drives the sequence, model only interprets
each step result. 293/293 tests passing.

**Core unvalidated assumption (item 14):** Can the pattern executor + llama3.2:3b correctly
orient a user to an unfamiliar codebase end-to-end? The executor runs deterministically;
the open question is whether the model's per-step interpretations are useful. Cold test needed.

**Full history:** HISTORY.md.

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
Last cleaned: 2026-06-24 (session 17 - verified against live tool run).

---

### BRANCH EXPERIMENT METHODOLOGY (standing, session 18)

Experiments live in branches. Anything uncertain or exploratory goes in a branch.
Working agreement:
- Any session can create a `ui/experiment-name` branch and go wild
- Nothing in a branch needs to be production quality — it needs to be learnable
- Branches are NOT thrown away silently. Before abandoning a branch, extract:
  * What worked (even partially)
  * What felt right that didn't work yet
  * What it revealed about what the right thing is
  * Any code worth porting to another branch
  Store these as a short note in HISTORY.md under "Branch findings"
- Successful experiments merge to main. Partial experiments inform other branches.
- Two branches can run in parallel and steal from each other.
- "I like this thing about branch A, not the rest" is a valid outcome.
  Port the thing, kill the branch, credit the source.

**Active branch plan (session 18):**

| Branch | Experiment | Key question |
|--------|-----------|--------------|
| `ui/spotlight` | One-symbol focus panel, no graph lib | Does hover+click context feel natural? |
| `ui/cytoscape-subgraph` | Cytoscape.js node-expand graph | Hairball threshold? What layout wins? |
| `ui/file-module-graph` | File-level graph, orient view | Better cold start than text output? |
| `ui/call-tree` | Collapsible HTML call tree | Readable without a graph lib? |
| `ui/trail` | Captured replayable investigations | Right storage model? Fork UX? |
| `ui/list-enhanced` | Current mode + clickable symbols + sort/filter | Lowest-friction upgrade path? |

Branch order: spotlight first (no deps, immediate value), then cytoscape-subgraph
(needs library decision), then file-module (reuses cytoscape), then trail (needs
schema design), then call-tree and list-enhanced in parallel as easier options.

Cytoscape.js chosen as graph library: MIT, designed for network graphs, handles
1000s of nodes, has dagre layout (DAG-aware), WebGL renderer available.
Can load from CDN like other deps.

---

### UI VISION: WHERE THIS IS GOING (session 18)

The current UI is a query box that produces text blocks. That is the wrong shape.
The right shape is a living, interactive graph where:

**Every symbol is a node.**
Every result is a subgraph expansion in place. Hovering a node shows its
context inline: name, type, HOT/WARM/SAFE badge, in-degree, whether it has
findings, whether it's a stub. Clicking expands it — shows its callers and
callees as new nodes attached to it. The graph grows as you investigate.

**Trace is visual, not textual.**
"Trace X to Y" is not a form. When two nodes are visible, you can draw a
path between them. The shortest call chain highlights across the graph that's
already on screen. No new query needed — the graph already knows the edges.

**Breadcrumbs are spatial.**
Each investigation adds to a trail you can walk back along. The session
history is not a vertical scroll of text; it's a map of where you went.
You can return to any prior node and branch from it differently.

**Leaves invite exploration.**
Nodes at the edge of an expanded subgraph are marked: explored vs unknown,
hot vs safe, has-findings vs empty. The "knowable without LLM" facts
(risk badge, stub, dead, entry point) show immediately on every node
without a query. Structural knowledge is ambient, not on-demand.

**Context-sensitive actions live on nodes, not in a sidebar.**
Every node has an action menu: expand callers, expand callees, understand,
risk profile, see findings, trace from here, git history. The sidebar cold-
start actions are for session setup only. Once a graph is on screen, all
further investigation flows from what's visible.

**The investigation accumulates.**
Results don't scroll off. They build spatially. The whole session is visible
as a connected structure. You can see your own reasoning as a graph.

---

### CURRENT UI AUDIT — what is clunky right now (session 18)

1. **Results are static text.** Symbols appear as plain text — you can read
   them but not touch them. Every symbol in every result should be a clickable
   node that opens its context. Currently: copy, paste, retype.

2. **Sidebar knows nothing about screen context.** "Callers of…" fills a blank
   input. It should offer the symbols currently visible in results as options.
   The sidebar is a cold-start panel; it should step back once there's context.

3. **Follow-up chips are text phrases, not structured actions.** They work, but
   they're the LLM's guess at what to ask next. They should be replaced or
   supplemented by structured contextual actions derived from what the result
   actually contains (symbols found → "expand this one", callers found →
   "what calls the caller", risk badge found → "see all HOT symbols").

4. **No visual graph.** The call graph is fully computed and stored in the DB.
   The UI never shows it. Every "callers of X" result is a list of names that
   should be a mini-graph node expansion.

5. **No breadcrumbs.** Once a result scrolls out of view it is gone. There is
   no way to see the shape of the investigation so far or return to a branch.

6. **"Jump to" requires cold symbol knowledge.** "Callers of…" means nothing
   without a symbol name. Should show recently seen / corpus entry points as
   quick options. The tool knows the most-connected symbols; the sidebar should
   offer them.

7. **Risk information is hidden until asked.** HOT/WARM/SAFE is computed for
   every symbol. It should appear passively on every symbol mention in every
   result — not require a separate "risk of changing X" query.

8. **Trace is missing entirely.** Noted above — wrong shape for the feature.
   Belongs on nodes, not in the sidebar.

9. **No investigation state.** The tool has a workflow queue (next_up, backlog).
   The UI shows it only when asked. It should be ambient — visible in a corner,
   updating as items are completed or added.

---

### UI DESIGN DIRECTIVE (standing, applies to all future UI work)

**Knowable things should be known. Known things should be expressed in the UI
in a discoverable, chained fashion — not in isolation.**

Before building or evaluating any UI feature, ask:
- How would a user actually arrive at this? What did they just do or see?
- Does it require the user to supply something the tool already knows? If so, offer it.
- Does it live in isolation or does it connect to what came before and what comes next?
- What is the user's actual need here — and is this the right shape for it?
- Is there a contextual version of this action that is more natural than a cold one?

**The principle:** the UI is a window into a connected body of knowledge. Every result
should suggest next steps. Every action that takes a symbol name should offer the corpus's
known symbols. Every investigation should leave a breadcrumb to related ones. The developer
should never be in a blank field with no hints; the tool knows things and should say so.

**Sidebar / menu directive (session 18, standing):**
The sidebar is for genuine cold-start actions only — things useful before any
result exists. If an action requires a symbol, file, or prior result to make
sense, it belongs in context (spotlight actions, node menus, follow-up chips),
not the sidebar. Before adding or removing any sidebar item, discuss with Bart
first — menu decisions are user-centric and need his sign-off. Bring suggestions
with reasoning; don't just change.

Agreed cold-start sidebar items (session 18):
  - Analyze (ingest a new project)
  - Work queue (where am I, what's next)
  - Find dead code (corpus-wide, no context needed)
  - Unexplored (where hasn't the tool looked)
  - Discover more (expand knowledge layer)
  - Missing docstrings (hygiene sweep)
  - Find todos (corpus-wide scan)

Everything else moves to context: spotlight panel actions, node menus,
follow-up chips on results.

**Practical rules:**
- Sidebar cold-start actions: only for things with no required input, or where the
  fill-then-type pattern is genuinely natural (callers of..., explore file...).
- Two-input actions (trace X to Y): never a blank dual form. Always contextual —
  triggered from a result where X is already known, with corpus-backed suggestions for Y.
- Follow-up chips on every result: the tool should always suggest what to look at next
  based on what the result actually contained.
- Symbol names in results should be interactive where possible — click to investigate,
  not copy-paste into a search box.
- "Knowable without LLM" facts (entry points, dead code, hot symbols, stub files)
  should be pre-populated and surfaced automatically, not waiting to be queried.

**Corollary — trace path specifically:**
"Trace X to Y" is not a sidebar action. It is a contextual action on a result.
When a result surfaces symbol A, the user can say "trace from A" and the UI
offers corpus-known symbols as the destination. The tool has the symbol list;
it should use it. A blank two-field form is the wrong shape entirely.

---

19. **[DEFERRED] Design intent layer: ingest and cross-reference authoritative docs alongside code**

   The tool analyzes code structure but has no awareness of what the code is *supposed*
   to do. Design docs (architectural constitutions, subsystem specs, authority boundaries)
   are the authoritative intent for a project — currently they live entirely outside
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
   - Surface drift: "ContextBuilder re-resolves entities — constitution says it must not"
   - Inform every "where does this go" coding decision without dictating order

   **Nature of this item:** Living, aspirational, off-and-on. Not a one-time feature —
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

1. **[LOW] `files.role` is never populated** - `parse_ast.py` sets `role=None`
   and has a comment "DO NOT recompute elsewhere." The `describe_file` and
   `find_files(role=...)` tools return no role info. Either implement role
   classification at ingestion time or remove the column and tool parameter.

2. **[LOW] `search_symbols` only finds 2 results for 'game_state'** but there
   are likely more (GameState class, game_state parameter names, etc.).
   Current query hits `symbols.name` substring match only - doesn't search
   behavioral_contracts.description or docstrings. Expand when it proves
   insufficient in real use.

3. **[LOW] `missing_docstrings` limit is hardcoded 20** with no way to get
   the full list or filter by file/module. Fine for now; revisit when the
   user actually needs coverage reporting.

4. **[MEDIUM] Wire stub projector into Determined UI** - "fill stub" button
   that picks highest-priority stub (by caller count / neighbor complexity)
   and shows Ollama projection inline. 47 stubs detected in dj2 corpus, all
   with 0 callers (phases.py stubs), so this is real work waiting.
   Requires Ollama running; gracefully degrade when it isn't.

5. **[MEDIUM] Collaborative editor surface** - minimal edit panel in UI where
   projection output and human edits meet. Edits committed here re-ingest the
   file. Not a scratchpad - a commit surface. Depends on item 4 being useful.
   Editor integration options (Bart's preference): Sublime Text first (packages
   exist for external control/automation; Bart uses it for its power and
   flexibility). Fallback: Lite-XL (lightweight, scriptable). Prefer driving
   the real editor over an in-browser textarea if the package ecosystem allows it.

   **Sublime Text integration research:**
   Sublime runs an internal Python plugin host - full programmatic read/write
   access via the `sublime` module. Two viable approaches:

   Option A - existing packages (install via Package Control):
   - Agentic: passes files/selections to Ollama-compatible APIs, streams back
     into editor. Directly relevant - supports local models.
   - AI Bridge + MCPHelper: MCP protocol bridge; external agent sends get/set
     commands and triggers native editor commands. Best fit for our architecture.
   - MCPHelper specifically: lightweight, exposes search/read/trigger primitives.

   Option B - custom Python plugin using sublime API:
   ```python
   view = sublime.active_window().active_view()
   text = view.substr(sublime.Region(0, view.size()))   # read file
   view.run_command("insert", {"characters": "..."})    # write at cursor
   ```
   An external Python agent wrapper or MCP server can drive this directly -
   grants full read/write over files, active tabs, and workspace config.

   Recommended path: MCPHelper (MCP bridge) so Determined's agent can talk to
   Sublime via the same MCP protocol pattern, without hardcoding Sublime-specific
   logic into the tool. Agentic is a useful reference for the Ollama plumbing.

6. **[MEDIUM] Live sync loop: edit -> re-ingest -> update** - re-ingest a
   single changed file without full corpus re-run. Currently the only option
   is full re-ingest (fast at 150 files, but won't scale to large corpora).
   Requires: incremental re-ingestion by file_path, edge delta propagation.

7. **[DEFERRED] contracts/orchestration feature decision** -
   `contracts/load_contract.py` has a dormant KeyError bug (loads wrong JSON,
   calls `contract["domains"]` which doesn't exist). Nothing calls it yet so
   it's silent. Decision: wire the typed loader + build orchestration layer,
   or delete all three (contract_types.py, tool_system_contract.json,
   orchestration/). Must decide before anything tries to use contracts.

14. **[HIGH] Validate small-model pattern following: can llama3.2:3b execute task patterns end-to-end without drifting?**

   The design is complete - registry, task patterns, pre-populated knowledge facts, orient_to_codebase
   workflow - but none of it has been tested cold against a corpus the model hasn't seen before.
   This is the central unvalidated assumption: that a 3B model can follow a multi-step prescribed
   sequence and stay on track without a human steering each step.

   **Why this matters:** Everything built in sessions 16-17 (knowledge layer, tool registry,
   task patterns) is infrastructure for this goal. If the model drifts, the user is back to
   needing to know what to ask - which is the exact hole we've been filling.

   **Likely failure modes to test for:**
   - Model ignores the pattern and free-forms its own tool sequence
   - Model follows 1-2 steps then loses the thread
   - Model calls a tool correctly but doesn't use the result to inform the next call
   - Model hallucinates tool names not in the registry

   **How to fix if it drifts:**
   - Tighter system prompt: feed the active pattern steps explicitly per turn, not just the registry
   - Step injection: agent_resolver injects "NEXT STEP: {tool}" as a hint after each tool result
   - Pattern executor: a thin loop in local_agent that drives the pattern mechanically,
     only calling the model for interpretation between steps (not for tool selection)
   - Shrink the model's job: model decides WHAT to ask, pattern decides WHICH tool - separation of concerns

   **Validation plan:** Run orient_to_codebase cold on a small unfamiliar corpus (not dj2).
   Score: did all 7 steps execute? Did the model use each result before moving on?
   Did it stay on the pattern or invent its own path?

15. **[HIGH] Pattern executor: separate tool selection from model interpretation**

   Current design: the model both decides which tool to call AND interprets the result.
   For named task patterns this is the wrong split - the model is the weakest link for
   tool sequencing, and a 3B model holding a 7-step plan in context is asking for drift.

   Better architecture: when a recognized pattern is active, the executor drives the
   tool sequence mechanically. The model's only job is to interpret each result and
   decide whether the pattern step is satisfied or needs a follow-up before moving on.
   Separation: **pattern decides WHICH tool, model decides WHAT IT MEANS.**

   **What to build:**
   - PatternExecutor class in local_agent.py (or agent_executor.py): takes a pattern
     name from TASK_PATTERNS, runs each step in order, feeds result to model for
     interpretation, advances when model signals ready
   - Pattern detection in agent_resolver: recognize when a user query matches a known
     pattern (e.g. "understand X", "orient to this codebase") and hand off to executor
     instead of the free-form decompose/resolve loop
   - Model prompt per step: instead of full tool list, inject only "Here is the result
     of {tool}. What does this tell you? Say NEXT when ready to continue." - keeps
     the model focused on interpretation not navigation
   - Executor handles: step ordering, result passing, early exit if a step returns
     empty/error, summary at pattern completion

   **Why this matters beyond fixing drift:** even with a capable model, mechanical
   pattern execution is faster, cheaper (fewer tokens deciding what to do), and
   auditable - you can see exactly which steps ran and what each returned.

   **The core insight:** The model is genuinely good at one thing - reading a result
   and saying what it means - and genuinely unreliable at another - holding a multi-step
   plan and executing it faithfully. The pattern executor stops asking the model to do
   the thing it's bad at.

   It also makes the task patterns built in session 17 actually load-bearing rather than
   advisory. Right now they're documentation the model may or may not follow. With the
   executor, orient_to_codebase becomes a thing that runs deterministically, every time,
   and the model just narrates what it sees at each step. The patterns go from "hints"
   to "guarantees."

   Depends on: item 14 (validation tells us which failure modes to harden against).
   Informs: item 13 (self-harness mines executor traces for failure patterns).

8. **[MEDIUM] Auto-populate semantic summaries at ingestion** - `describe_file`
   writes to `semantic_summaries` on demand (requires Ollama). Currently 17/150
   dj2 files are covered. Add an opt-in `--summarize` flag to `local_agent
   --source` that calls `describe_file` for every file after ingestion and
   stores the result. Gracefully skips if Ollama is unreachable. After this,
   `knowledge_status` would show full coverage without requiring prior queries.

9. **[MEDIUM] Distillation pass: compress verbose LLM text to compact facts** -
   `semantic_summaries` and `file_purpose` artifacts store 3-4 paragraph LLM
   responses verbatim. Add a distillation step: pass each verbose blob back to
   Ollama with a compression prompt ("one sentence: what does this file/symbol
   do?") and store the result as a separate `distilled` kind in
   `knowledge_artifacts`. The distilled form is what `symbol_brief` and the
   agent resolver use as a quick-scan; the verbose form stays for full context.
   Subject naming convention: `distilled::<subject>`.

10. **[MEDIUM] Tool chaining: structured output mode** - every tool returns a
    string (right for LLM consumption). When one tool's output drives another
    programmatically (e.g. `list_callers` -> `risk_profile` for each caller,
    or `graph_subgraph` nodes -> `symbol_intent` for each node), the agent has
    to re-parse its own text. Add an internal `_raw` variant for key tools that
    returns structured data (list of dicts), used by agent_resolver's auto-
    expansion phase (phase 2b) instead of text-parsing. External API stays
    string-only. Affected tools: `list_callers`, `list_callees`,
    `graph_most_connected`, `graph_subgraph`, `search_symbols`.

20. **[HIGH] Tools revamp: make tools corpus-generic and actionable** - tools
    were built with dj2 as the implicit corpus and produce noise instead of
    signal. Two concrete problems driving this:
    (a) Corpus-specific assumptions: hardcoded symbol names, file paths,
        heuristics that assume dj2 structure. Known instances fixed
        (process_message placeholder, graph inputs seeded from entry points).
        Audit remaining tools for same.
    (b) Docstrings tab is useless as currently implemented: returns 33+ lint
        warnings about missing docstrings in the target corpus - not actionable
        for understanding code. Should be combined with other "health" signals
        into a single actionable summary (e.g. "files with no coverage AND no
        docstrings = highest-priority to explore"), not a flat lint list.
    General principle: every tab result should answer "what should I do next"
    not "here is a raw dump." Redo tabs as actionable notes, combine where
    redundant.

21. **[HIGH] UI rewrite: interactive graph, context-aware actions, executable results**
    - Full design documented in "UI VISION" and "CURRENT UI AUDIT" sections of this
      file (session 18). Core principle: every symbol in every result is a clickable
      node, not static text. Every action that takes a symbol should offer known
      corpus symbols. Investigations accumulate spatially as a graph, not a text scroll.
    - Concrete work: (a) results as interactive nodes with spotlight panel; (b)
      Cytoscape.js graph replaces text for callers/callees/subgraph; (c) context-
      sensitive action menus on nodes (expand, understand, risk, trace from here);
      (d) follow-up chips derived from result content, not LLM guesses; (e)
      HOT/WARM/SAFE badges ambient on every symbol mention, not on-demand.
    - Branch order from session 18: spotlight first, then cytoscape-subgraph,
      then file-module-graph, then trail, then call-tree/list-enhanced.
    - Item 20 (corpus-generic tools, actionable tabs) is a prerequisite - fix the
      data layer before rebuilding the display layer.

11. **[FUTURE] Trace-weighted ranking** - replace heuristic scoring with
    trace-weighted ranking from expansion provenance. After real usage patterns
    are clear.

13. **[FUTURE] Self-Harness pattern** - knowledge.db is the natural store for
    harvested failure patterns. After ADVERSARIAL traces accumulate, mine them
    into `known_issue` artifacts keyed by failure category, then use those
    artifacts to tune agent_resolver heuristics. Loop: ADVERSARIAL run ->
    extract failure patterns -> store as known_issue -> harness reads on next
    run -> better routing. Closes the improvement loop without touching Ollama.

---

## 4. Chronological session log

Moved to HISTORY.md (section B) as part of the 2026-06-18 TRACKER/HISTORY
split - full dated session-by-session record, verbatim, nothing dropped.
