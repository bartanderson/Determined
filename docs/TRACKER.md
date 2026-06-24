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

**Earlier history (sessions 1-9, 2026-06-19 to 2026-06-22):** Full agent pipeline built and validated.
24 tools, 30+ heuristic patterns, PICK/ADVERSARIAL eval commands, game_corpus.db merged,
adversarial validation found and fixed 9 routing gaps. Full detail: HISTORY.md.

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
