tools/analysis - HISTORY (chronological session log)
=====================================================

Full dated record of what was done session by session.

- For current status and open work: see TRACKER.md.
- For how the system is actually built: see DESIGN.md.
- For the still-relevant operational summary of environment defects: see
  TRACKER.md section 2.

---

## A. Standing environment defects - reference

### 2a. Stale/locked `.pyc` cache bug

Three confirmed variants on this Windows environment: a locked/undeletable
stale `.pyc` whose mtime+size happens to match an intermediate source save
and passes Python's normal cache-validity check; the same thing but where
even `rm -rf __pycache__` reports clean success while the file silently
remains; and a case where deletion succeeds but trusting it without
re-verification still misses the window. All three look the same at
runtime: `inspect.getsource()` shows correct code but the live function
object's actual behavior (or `dis.dis()` output) reflects the old version.

**Takeaway:** if `inspect.getsource()` and `dis.dis()` on the same live
function object ever disagree, or runtime behavior contradicts
visibly-correct source, suspect a stale `.pyc` before assuming the source
is wrong. Use `touch <source.py>` to force a recompile - a `__pycache__`
deletion is not always sufficient on this environment.

### 2b. `sqlite3.OperationalError: disk I/O error` on new DB writes

Any new sqlite DB file written to this mount hits `disk I/O error` on the
first write (table creation). Existing DBs write fine.

**Fix:** run `PRAGMA journal_mode=MEMORY` immediately after
`sqlite3.connect()`, before any other statement. Sqlite's default
rollback-journal mode needs to create a `-journal` sidecar file on first
write; forcing the journal into memory avoids it.

**Caveat:** a stale `-journal`/`-wal`/`-shm` sidecar left from an earlier
failed attempt can re-trigger the error even with the pragma in place,
because sqlite attempts rollback recovery before your `PRAGMA` call runs.
If this error recurs with the pragma in place, check for and clear sidecar
files for that DB path first.

---

## B. Chronological session log

### (pre-history) Founding design intent - stub detection and visualization

**Core concept (Bart's original session opener):**
The shape of missing code - functions that exist as stubs - combined with
their surrounding behavioral contracts and call graph context, forms a safe
work queue for guided development. Filling a stub cannot silently break
callers because existing contracts act as guardrails.

**Step 1 - Stub detection in parse_ast.py:**
During the AST walk, flag any function whose body is exclusively `pass`,
`...`, `raise NotImplementedError`, or a bare `return None`. Emit stub
metadata into the symbol graph including: module, function name, cyclomatic
complexity of neighbors, and what calls into it.

**Step 2 - DBOracle query:**
Stubs should be first-class queryable facts, not just annotations.

**Step 3 - Plotnine visualization:**
Stub density per module as a sorted bar chart, colored by neighbor
complexity. This is the development guidance interface - showing where the
work is and how risky each gap is to fill.

This intent drove the initial parse_ast.py + DBOracle + stub projector work.
The visualization (plotnine) was deferred; stub detection and querying landed.
Item 4 (stub projector in UI) is the direct descendant of Step 3.

---

### 2026-06-27 (session 26)

**Item 5 done. Editable editor + save to disk.**

Editor tab (panel-editor) is now read/write. "Edit" button switches the read-only code
table to a full-height textarea pre-filled with the file's content. "Cancel" discards
changes; "Save" emits `save_file` to the server, which validates the path is within the
project root, writes the file (UTF-8), and emits `save_result` back. On success the file
reloads and a toast confirms the save. `stub_projection` now also opens the stub's source
file in the Editor tab and scrolls to the function's line number, landing the user directly
at the stub to review or apply the projection.

Server: new `handle_save_file` socket handler in ui_server.py (path-safety check via
`Path.resolve().relative_to(project_root)`, write via `fp.write_text(content, encoding="utf-8")`).

298/298 tests throughout.

---

### 2026-06-27 (session 25)

**Item 4 done. Stub projector wired into UI and agent. Stale item 15 removed.**

Item 15 was already implemented in session 18 but never removed from the open items list.
Cleaned up.

Item 4 (stub projector in UI):

Two new agent tools: `list_stubs` ranks stubs by caller count; `project_stub` calls
`stub_projector.project_stub(db_path, symbol)` and returns the suggested body with context.
Both registered in TOOLS and REGISTRY.

UI: `handle_symbol_quick` now returns `is_stub`; `handle_project_stub` socket handler runs
in a background thread and emits `stub_projection`. Client: when spotlight opens for a stub
symbol (detected from `symbol_quick_result.is_stub`), a "fill stub" button appears in the
spotlight action bar. Clicking it fires `project_stub`, disables the button, and shows the
suggested body in the `sp-source` panel with caller/contract context in the header.

298/298 tests throughout.

---

### 2026-06-27 (session 24)

**Items 20 and 21 closed. Bag wiring for graph_most_connected + risk_profile. Ambient risk badges.**

Item 14 was validated last session (llama3.2:3b PASSES orient_to_codebase cold). Session 23
fixed four bugs found during that validation (VALID_KINDS, truncation, idempotent extract
message, kind mismatches). All 22 commits from tools/audit branch merged to main.

This session:

Bag wiring (was pending from session 23): `graph_most_connected` and `risk_profile` now
return `(text, bag_items)` tuples. The dispatch function in `agent_tools.py` auto-calls
`assessor.bags.auto_add_items(items)` on any tuple return. HOT/WARM symbols named in orient
sessions now accumulate in the system bag automatically with name, file_path, risk level,
and in_degree.

Item 20 (Tools revamp - corpus-generic and actionable): Audited all tools for dj2-specific
hardcoding - none found beyond the already-fixed instances (process_message placeholder, entry
point seeding). Docstrings tab already replaced with Chat sidebar query. General principle
satisfied: 6-tab layout + Chat sidebar is actionable by design.

Item 21 (UI rewrite): All branches from session 18 plan were already landed:
- Spotlight panel (full click-through with risk profile, callers, callees, actions)
- Cytoscape subgraph (Graph tab)
- File-module import graph (Imports tab)
- Breadcrumb trail
- Call tree tab

Final piece (21e - ambient badges): `attachSymbolHandlers` now fires `symbol_quick` for all
new symbols immediately on DOM insertion (no 280ms hover delay). `symbol_quick_result` applies
`sym-risk-hot` / `sym-risk-warm` CSS to matching `.sym-link` spans. HOT symbols show red,
WARM show orange, SAFE stays default blue. Hover tooltip unchanged - still fires at 280ms and
shows full badge + docstring + stats.

298/298 regression tests throughout.

---

### 2026-06-25/26 (session 19)

**Items 16/17/18 fixed. Corpus scoping complete. Item 14 unblocked.**

Item 16 (DB lock WinError 32 on re-analysis): Fixed in `ui/ui_server.py` `handle_ingest`.
Close oracle connection before deleting DB file: `_oracle.conn.close()`, `_oracle = None`,
`_assessor = None` before `Path(db_path).unlink()`.

Item 17 (UI corpus switch tabs not refreshing): Fixed in `ui/templates/console.html`.
`_startupFired` boolean replaced with `_startupFiredFor` that tracks DB path, so tab
refresh fires on corpus switch not just first connect. `ingest_done` event now emits
`socket.emit("corpus_status")` which triggers `corpus_ready` and the full tab refresh
flow, instead of manually firing a query.

Item 18 (knowledge.db no corpus scope): Fixed across 8 files. Added `corpus TEXT` column
to `knowledge_artifacts` and `semantic_summaries` (with migrations for existing rows).
`KnowledgeOracle.alongside()` now sets `corpus_key = os.path.basename(corpus_db_path)`
and passes to `__init__`. All reads/writes in `assessor.py`, `agent_tools.py`, and
`knowledge_artifact.py` now scope to `corpus_key`. `get_artifacts()` / `list_artifacts()`
filter `(corpus = ? OR corpus IS NULL)` to treat legacy rows as belonging to all corpora.

Also fixed: `run_engine.py` __main__ had `repo_root = "."` hardcoded - caused
`ValueError: not in subpath` for any corpus outside the Determined directory.
Fixed to `repo_root = selected_target`. `scan_project_files.py`: added "3.10", "3.11",
"3.12" to `DEFAULT_IGNORED_DIRECTORIES` to exclude Python version-named venvs.

Regression fix: `test_list_callees_no_callees` checked for "No callees found" but
message had changed; updated to `"No" in result and "callee" in result.lower()`.

298/298 tests passing.

dj2 design docs committed: `docs/design/00E AI_LAYER_OPPORTUNITIES.md` (tool-calling DM,
EventLog as AI memory, structured adjudication outputs, NPC as deterministic state,
Persona UI eval, trust boundaries). `docs/design/00F ASPIRATIONAL_DESIGN_INTENT.md`
(authority boundaries, AI DM vision, world architecture, audio, reactive world, decision
checklist; section H links back to Determined item 19 with specific extraction targets).



### 2026-06-16 (morning)

**Noise-filter unification.** `split.i.surface` and `cursor.self.oracle.conn`
-style internal dotted-accessor symbols were showing up as query seeds -
structurally real but not meaningful query targets. Unified into
`oracle/symbol_noise.py` (`is_noise_symbol`/`is_accessor_chain_noise`),
applied consistently at both discovery time (`db_oracle._discover_token`)
and expansion time (`oracle_router._is_valid_symbol`) - no more drift
between the two call sites' filtering behavior.

**AI compiler wired to a real LLM.** `truth/query_compiler.py` rewritten
to try a local Ollama call (`llama3.2:3b`) first, validate its output
through `QueryPlanner`, and fall back to the original rule-based
intent->AST table on any failure. Local-only, no Anthropic API call.

**Torch warning diagnosed (not yet fixed for real - see 2026-06-17 entry
below for the actual fix).** The recurring torch warning on Windows
(sentence-transformers pulling in PyTorch) doesn't respond to
`PYTHONWARNINGS=ignore`, because it's emitted via `logging.warning()`
(`torch.distributed.elastic`'s own glog-style logger), not via
`warnings.warn()` - the `warnings` module's env var has no effect on a
plain `logging` call.

### 2026-06-16 (later same day) - agent readiness gaps closed

An evidence-based assessment found the individual pieces solid but no wired
front door: `QuerySession.run_algebra()` - the one method chaining real
NL -> AI compiler -> AST -> executor -> real views - had zero callers
anywhere and had never been run end-to-end against a live project DB. Two
views (SUMMARY, SUBSYSTEM) were similarly orphaned: implemented, but with
only stub-dict test coverage, never called from `assessor.py`. Legacy
dead-end agents (`oracle/agent.py`'s `GraphOracleAgent`,
`oracle/nl_agent.py`'s `NaturalLanguageGraphAgent`) bypassed
oracle_router/QuerySession/Truth Layer entirely and looked like "the agent"
to a future session, risking being mistaken for the real integration point.

Closed same day:
- `Assessor.summary_view()`/`subsystem_view()`/`all_views()` wire SUMMARY
  and SUBSYSTEM to real DB-backed data (`reduced_snapshot()`/
  `bucket_summary()`/`file_count()` for SUMMARY, the real graph snapshot
  for SUBSYSTEM).
- `Assessor.ask(text)` wraps `session().run_algebra(text,
  views=self.all_views())`; `tools/analysis/ask.py` is the new CLI
  entrypoint - `python tools/analysis/ask.py <db_path> "<question>"` - run
  successfully end-to-end against the real project DB.
- Deleted `oracle/agent.py`, `oracle/nl_agent.py`, and their only real
  consumer `tests/debug/oracle_compare_harness.py`, per Bart's conditional
  approval ("If you have something better they can both go") - `ask.py` /
  `Assessor.ask()` is that something better.
- Deleted `truth/test_harness.py` (`TruthTestHarness`) - a manual
  print-based runner where pass/fail meant only "no exception was thrown,"
  zero real callers, per Bart's stated preference for real assertion-based
  tests over decorative harnesses.
- New regression suite: `tests/regression/test_run_algebra_end_to_end.py`
  (4 assert-based tests - all 5 views build from real seeded data,
  SUMMARY/SUBSYSTEM execute through the algebra, `ask()` runs end-to-end,
  `ask()` is deterministic). Full sweep: this suite (4) +
  `test_oracle_router_persistence_lock.py` (6) +
  `truth/tests/test_query_algebra.py` (32) = 42/42 passing.

### 2026-06-16 (same day, loose-script cleanup pass)

Audited every loose top-level `.py` file in `tools/analysis/` plus two
test files that surfaced as dependents. All traced to one root cause:
`tools/analysis/run_analysis_pipeline.py` does not exist anywhere in the
repo and never did in this session's visibility - it was the
orchestration entrypoint an earlier architecture iteration was built
around, since superseded by `engine/run_engine.py` (ingestion) + `ask.py`
(querying).

Deleted 7 dead files: `run.py` (subprocessed into the missing module),
`debug_run.py` (imported it directly), `run_parity_test.py` (imported 5
more nonexistent `engine.core.*` modules plus a nonexistent
`engine.parity.ParityChecker`, had an internal `NameError` bug and
unfinished placeholder comments - superseded by the real, working
`engine/parity_contract.py` + `engine/structural_parity_diff.py`),
`load_config_profiles.py` (expected a nonexistent
`analysis_profiles.yaml`, zero callers), `tests/core/test_pipeline_smoke.py`
and `tests/core/test_reference_extraction_integrity.py` (both imported the
missing module - their other imports, `test_db_utils.py` and
`graph/project_context.py`, were confirmed still legitimately used by
other live tests), and a top-level `rewrite plan for routing to
classification.md` (a near-duplicate early draft of `docs/Symbol
Classification Stabilization Plan.md` - kept the cleaner copy, deleted
this one).

Kept, dormant but functional (standalone diagnostic CLIs, no broken
imports, just no current callers): `db_probe_toolsold.py`,
`db_toolsold_audit.py` (heavy overlap with each other - candidates to
merge if ever revived), `debug_gap_report.py`.

Added STATUS NOTE headers (no other content changed) to three older
planning docs that all assumed the now-dead `run_analysis_pipeline.py`/
`debug_run.py` were the live entrypoints: `Symbol Classification
Stabilization Plan.md` (now condensed into DESIGN.md section 4),
`current predecessors still useful/architectural triage protocol.md`
(out of scope for this consolidation pass), and `contracts + visibility.md`
(now condensed into DESIGN.md section 5).

### 2026-06-16 - Truth.md Phase 1 findings: algebra is alive

Ran the actual verification Phase 1 calls: are the algebra mechanics
real or dead code? Findings, read directly from code, not assumed:

The mechanics are alive and tested - `truth/query_ast.py`
(Select/Filter/Combine), `truth/query_plan.py` (Planner + Registry), and
`truth/query_executor.py` (Executor) are all real, non-stub
implementations, with 25+ passing tests in
`truth/tests/test_query_algebra.py` covering valid/invalid Combine pairs,
metrics, filter keys, and executor determinism.

At the time of this finding, three of five views were wired to real data
(STRUCTURE, STABILITY - though with `drift_signals` hardcoded `[]`, and
INTEGRITY); SUMMARY and SUBSYSTEM were still orphaned. Both gaps were
closed the same day (see the "agent readiness gaps closed" entry above) -
by the time this finding was written up in full, all 5 views were real,
and the verdict on Phase 1's exit criteria ("Truth Layer produces real
output from real project data") was recorded as **MET**. Phase 1 closed;
Phase 2 (router vs. Truth Layer comparison) was left open, to start
whenever prioritized.

### 2026-06-16/17 - Truth.md Phase 3: evidence-based gap audit

Trigger: Bart noticed `ask()` had no way to answer "what is the purpose of
this file" and asked whether that was one hole or a symptom of several.
Ran real questions against a real DB, recorded actual output, no guessing.
Found 5 concrete rows:

- **Row 1** - "what is the purpose of X" / "why does X exist" / "what is
  the role of X" all fell to the catch-all `general_query` intent (no
  category existed for purpose/why/role phrasing) and produced the
  byte-identical fallback `Combine(Select(STABILITY), Select(INTEGRITY))`
  regardless of which file was actually named - the symbol mentioned in
  the question never had a path into those views at all. Absent category,
  not a tuning problem.
- **Row 2** - role/responsibility classification existed and was real
  (`engine/responsibility_map.py` + `Assessor.responsibility_map()`,
  keyword-matching file path + callee names against real DB data,
  confirmed with real totals across the bucket categories) but had zero
  path into `all_views()`/`Select()`/`Combine()` - a wiring gap, same
  shape as the SUMMARY/SUBSYSTEM orphaning already fixed.
- **Row 3** - `drift_signals` was hardcoded `[]` at the
  `build_stability_view()` call site - a query against it validates and
  executes cleanly, and silently always returns nothing real. Flagged as
  "the most dangerous gap shape," since the algebra can't signal that it
  doesn't actually know.
- **Row 4** - `_module()` in `truth/subsystem_view.py` assumed dotted,
  module-qualified symbol names (`symbol.split(".")[:2]`), but this
  codebase's real call graph is mostly bare function names with no dots -
  so the "subsystem" key ended up being the function name itself, 355
  "subsystems" for a project with roughly 60-70 real files. Worse than a
  hole, since it looks like an answer.
- **Row 5** - no intent/description field exists anywhere on
  `MutationEvent` (`shared/types.py` has only `line_number`/`target`/
  `operation`/`raw_expression`), so "why was this mutation made" has
  nothing to recover regardless of view or query - genuinely never
  captured, same shape as Row 1.

Pattern across all 5: two failure shapes, not five unrelated ones -
"never captured" (Rows 1, 5, needs new ingestion) vs. "captured/computable
but not wired or wired wrong" (Rows 2, 3, 4, needs only connection work).
Rows 2, 3, and 4 were all closed over the following day.

### 2026-06-17 - ROLE view added (Row 1/Row 2 closed)

Per Phase 4's rule ("one missing capability, one implementation, one
measurable improvement"): added ROLE as a 6th Truth Layer view, same fix
pattern as the SUMMARY/SUBSYSTEM wiring - connect an existing thing, no
new heuristics.

- `truth/views.py`: `RoleView` dataclass + `build_role_view()`, a pure
  transform of `responsibility_map()`'s existing output.
- `assessor/assessor.py`: `Assessor.role_view()`, wired into `all_views()`
  (now 6 keys: STRUCTURE/STABILITY/INTEGRITY/SUMMARY/SUBSYSTEM/ROLE).
- `api/oracle_router.py`: `_detect_intent()` gained a `role_query` branch
  (purpose/why-does/why-is/role-of/what-role/what-kind-of phrasing);
  `_select_primitives()` maps it to `["role"]`; `_route_expand()`'s
  `intent_budget` gained a zero-traversal-depth entry for it (ROLE is
  file-level, not graph-dependent - zero budget is the honest answer).
- `truth/query_plan.py` / `truth/query_compiler.py`: ROLE registered with
  `totals`/`files` metrics; `role_query` compiles directly to
  `Select("ROLE", ...)`, not a Combine fallback.

Measured improvement: `assessor.ask("what is the purpose of ingest.py")`
now returns `intent == "role_query"`, a `Select` (not `Combine`) AST, and
real per-file role data - not the previous byte-identical fallback
regardless of file named.

New coverage: `tests/regression/test_role_view_routing.py` (5 tests).
Full sweep: 47/47 (5 new + 4 run_algebra_end_to_end + 6
oracle_router_persistence_lock + 32 pytest).

### 2026-06-17 (continued) - algebra shape contract audit

Real bug from Bart's Windows machine (the only place the live Ollama
compiler is reachable): `AttributeError: 'list' object has no attribute
'totals'`. Root cause was not an AI compiler error - Ollama had compiled
`Select("ROLE", metric="files")` for a one-file question, a legitimate,
registry-valid, arguably more precise choice than the full view. The bug
was a test (and implicitly, any future consumer) assuming `QueryResult.data`
always had one fixed shape.

Per Bart's framing - the algebra is "valid checkboxes the AI selects...
the consumer's job is to handle whichever valid checkbox came back, not
demand one specific one" - did a full audit, not a one-test patch:

- `truth/query_executor.py`: added `get_field(result, name, default)`,
  the shared shape-safe way to read any `QueryResult` field regardless of
  whether `metric=None` (attribute/key access on the full view) or
  `metric=name` (already-unwrapped value).
- Found and fixed a real shape inconsistency: SUBSYSTEM was the only one
  of 6 views whose full-view shape was a bare dict instead of a
  dataclass. Added `SubsystemView` dataclass, updated
  `build_subsystem_view()` to return it.
- Removed dead+wrong `QuerySemanticsRegistry.validate_metric()` (zero
  callers, checked the wrong dict - would have rejected every legitimate
  metric had it ever been called).
- `query_compiler.py`'s `_ALGEBRA_SPEC` (the text fed to Ollama) now
  generates directly from the registry instead of being hand-typed,
  closing a drift risk between what the model is told and what's
  enforced.
- Fixed the two broken consumers to handle real shapes via `get_field()`
  rather than assuming one.
- New suite: `tests/regression/test_query_result_shape_contract.py` (4
  tests) - proves `get_field()` agrees with direct metric-selection for
  every (view, metric) pair against real data, returns the documented
  default rather than guessing, and that every view's full shape is now
  attribute-accessible.

Full sweep: 57/57 (25 regression + 32 pytest).

### 2026-06-17 (later) - determinism test fix

Bart's Windows run hit `test_ask_role_question_is_deterministic` failing
on byte-identical-AST comparison - two calls of the same question
compiled to two different, both-valid ASTs (`Select("ROLE")` vs.
`Select("ROLE", metric="files")`). Same bug class as the shape-contract
fix, one level up: an LLM compiler at `temperature=0.0` is not guaranteed
to land on the same valid choice twice (greedy decoding isn't
bit-reproducible across requests with llama.cpp/Ollama - floating-point
non-associativity in parallel reduction, a backend property, not a
codebase bug).

Fixed the test's invariant, not the compiler: now asserts
`intent == "role_query"` on both calls plus agreement on the real role
classification read via `get_field()`, rather than raw AST text equality.
No production code changed. Full sweep: 57/57 (same counts, fixed test
now passing for the right reason). This fix's real value only shows on
Bart's Windows machine, since that's the only place the live-Ollama
nondeterminism actually occurs.

### 2026-06-17 (later still) - Track A completed; Track B item 2 closed

Per Bart's direction ("Track A, then also fix subsystem fragmentation"),
did both in one session.

**Track A - DB-backed symbol discovery API:** added `list_symbols`,
`find_symbols`, `find_files`, `find_modules`, `symbol_module_map` to
`oracle/db_oracle.py`, all DBReader-only (distinct in purpose from the
pre-existing `discover_seed_symbols`, which is NL-query relevance scoring
for `route_query`'s seed step - these are general-purpose lookup
primitives for browsing/bootstrap). Confirmed production seeding was
already 100% DB-backed (`QuerySession.run_query()` already passes
`self.oracle.discover_seed_symbols` as `find_symbols_fn`); removed the
dead `_seed_symbols()` decoy wrapper in `api/oracle_router.py` (its one
call site was already commented out - never live, same "looks like a
feature, isn't" shape as the deleted `_apply_intent_weights` stub and the
deleted legacy agent files).

**Track B item 2 - SUBSYSTEM fragmentation (Row 4):** root cause was
`_module()`'s dotted-name assumption not matching this codebase's mostly-
bare-name call graph. Fix: `_module()`/`build_subsystem_view()` now take
an optional `module_map` (built by the new `symbol_module_map()` - real
`symbols` table declarations, file_path's containing directory as the
module); a symbol is looked up in the map first (exact, then bare tail
segment), with the old dotted-name heuristic as fallback only for symbols
absent from the map (builtins, external calls, noise) - confirmed
non-breaking against the existing test fixture before writing the fix.
Wired in: `Assessor.subsystem_view()` passes the real map by default, so
the fix is live on the production path.

New suite: `tests/regression/test_discovery_api_and_subsystem_fix.py` (7
tests - 5 discovery methods including the ambiguous-name deterministic
tie-break, plus a direct with-vs-without-module_map comparison showing
`"do_thing"` stops being its own singleton subsystem). Full sweep: 64/64.

### 2026-06-17 (later session) - Track B item 1 closed: drift_signals wired

Closed Row 3. Same shape as Row 2/4: `ContractDriftClassifier`
(`contracts/contract_drift_classifier.py`) already existed with the exact
output shape `build_stability_view()` expects, with zero callers anywhere.

- `assessor.py`'s `stability_view()` now calls
  `ContractDriftClassifier().classify(reports)` and passes the real
  result, replacing the hardcoded `[]`.
- `file_contract_reports()` violations gained a `"layer": "graph"` key
  (the only contract this method produces, `symbol_reference_integrity`,
  isn't in the declared-contract registry, so `"graph"` was chosen as the
  most accurate available label, not pulled from a registry lookup that
  doesn't cover it).
- `ContractDriftClassifier.classify()` hardened with a `_field()`
  dict-or-attribute shape-safe accessor (same principle as `get_field()`),
  since real violations are plain dicts, not the attribute-style
  `ContractViolation` from the dead `contract_observer.py` path.

Measured improvement: a seeded DB with N broken symbol references now
returns real, correctly-classified drift signals (confirmed for
transient/recurring/structural count thresholds) instead of `[]`.

New suite: `tests/regression/test_drift_signals_wiring.py` (6 tests).
Full sweep: 60/60 (54 prior + 6 new).

With Rows 2, 3, and 4 all closed, every "captured/computable but
wired-wrong" gap from the Phase 3 audit is resolved - what remains (Row
1's non-Row-2 remainder, Row 5) is exclusively the "never captured"
category, needing new ingestion.

### 2026-06-17 (later session) - single-file ROLE filter scoping fixed; torch warning actually silenced

Bart hit two real problems running `ask.py "what is the purpose of
db_probe_toolsold.py"` on his Windows machine.

**Torch logging warning (the real fix, vs. the diagnosis-only note from
2026-06-16):** confirmed it's emitted by `torch.distributed.elastic` via
plain `logging`, not `warnings.warn()`. Fixed by silencing the actual
source: `logging.getLogger("torch.distributed.elastic").setLevel
(logging.ERROR)`, added in `oracle/embedding_model.py`'s `get_model()`
alongside the (harmless, left in place) existing `warnings.filterwarnings()`
calls.

**ROLE-view filtering gap (the bigger issue):** the query returned every
file in the project instead of just the one named. Three independent bugs
stacked:
1. `Filter` (`query_ast.py`) and `_apply_filter` (`query_executor.py`)
   were both fully implemented and planner-validated, but nothing upstream
   ever constructed a `Filter` - `Select.filter` had been `None`
   end-to-end since the algebra was built. Same orphaned-primitive shape
   as drift_signals.
2. `QueryExecutor._select()` applied `Filter` *before* metric projection -
   every real view is a dataclass, not a dict/list, so even a correctly
   built `Filter` would have silently done nothing. Fixed by reordering:
   project the metric first, then filter.
3. `VALID_FILTER_KEYS` had no `"ROLE"` entry at all - added
   `{"file_path"}`.

Fixed deterministically, not via the AI compiler (the buggy run had gone
through Ollama and still produced `metric=None` despite the prompt
preferring `metric="files"` for one-file questions - prompt compliance
isn't guaranteed even at temperature 0.0). `query_compiler.py` gained
`_extract_single_file_filter()` (regex, single `*.py` token) and
`_maybe_scope_to_named_file()` (rescopes a bare unfiltered
`Select("ROLE")` to `metric="files"` plus a `Filter("file_path",
"endswith", name)`, re-validated through the planner) - a new
`"endswith"` operator was added since the question names a bare filename
while `DBOracle` stores full paths. Wired into both `compile_query()` and
`compile_and_explain()`, deliberately narrow (only fires on the exact bug
shape - a compiler that already chose a specific metric is left
untouched).

New suite: `tests/regression/test_single_file_filter_scoping.py` (10
tests). Full sweep: 80/80 (48 regression + 32 pytest).

### 2026-06-17 (later still) - old pre-regression-suite tests audited

Bart asked whether to weed out the old test files under `tests/core/`,
`tests/debug/`, `tests/integration/`, `tests/semantic/`, and
`test_embedding_seeds.py` (predate the `tests/regression/` convention).
Audit, not deletion, was the right call.

Before any change: 105 passed, 5 collection errors, all one root cause -
5 files imported `create_database`/`initialize_database` from the deleted
module path `persistence.persist_file_analysis`. Both functions are alive
in `persistence/persistence_engine.py` - just a stale import path, not
dead code.

Fixing the import alone would have been wrong:
`persistence_engine.create_database()` unconditionally deletes-then-
recreates its target file, and all 5 old tests called it against the same
hardcoded path - so every one of the 4 "assertion-only" tests was silently
wiping whatever the smoke test had just persisted and asserting against
an empty DB, vacuously true every time. Same "looks green, tests nothing"
shape as the drift_signals/orphaned-Filter bugs, in the old test layer.

Fix: moved the shared DB to an OS-temp-dir path
(`test_db_utils.py:SHARED_TEST_DB_PATH`, categorically can't collide with
a real product DB path); the smoke test builds it via a real
`EngineRunner` run and does not delete it afterward; the 4 downstream
tests now open it without wiping and `pytest.skip()` with a clear message
if unpopulated.

Once real, 4 of the 5 failed for real, surfacing genuine findings (not
caused by this change): 710+ `(file_path, name)` duplicate pairs (possibly
a real raw-engine-run duplicate-insertion issue, or dedup that normally
happens later in `persist_all()` but is bypassed by this direct smoke
test - undetermined at the time); stdlib/builtin callees reported as
"unresolved" (predates the noise-filter unification and doesn't know
those are expected not to resolve against the project's own symbols
table); and a "short names only" assumption that doesn't hold for
qualified stdlib call targets. Flagged to Bart rather than silently
patched, since it's a behavioral judgment call about the engine/
persistence layer. Full sweep after: 106 passed, 4 failed, 0 collection
errors.

### 2026-06-17 (run-on continuation) - bucket-gate bug root-caused; the 4 flagged failures resolved for real

Continuing directly: Bart's instruction was to actually fix the 4 flagged
failures, not leave them as known issues. All 4 shared one root cause,
plus a second, independent environment bug was found verifying the fix.

**Root cause: the function/class -> `symbols` insert was gated on a
condition that could never be true.** `persist_file_analysis()` checked
`if getattr(obj, "bucket", None) == "project"`, but
`FunctionRepresentation`/`ClassRepresentation` have no `bucket` field at
all and nothing ever sets one on them (`bucket` is only ever set on
`SymbolReference` objects). Unconditionally False for every function and
class in this codebase's history - the `symbols` table had never once
held a real function/class declaration. The 710+ "duplicate" finding from
the prior entry was downstream of an earlier patch (commit f7acec9) that
papered over this exact symptom by stuffing raw, uncanonicalized
caller/callee call-site names - including external/stdlib references -
into `symbols` under the wrong taxonomy (`symbol_type='caller'/'callee'`,
with zero live consumers reading that, confirmed via exhaustive grep -
`db_oracle.py`'s `symbol_module_map()` already explicitly filters to
`('function','class')`, defending against exactly this pollution).

Fix: removed the dead `bucket == "project"` gate (now unconditional,
matching the always-run `INSERT INTO functions`/`classes` directly above
each - `EngineRunner` only scans project-corpus files, so every
function/class found IS a project declaration by construction); removed
the caller/callee pollution block entirely. Verified end to end: a real
engine run now populates `symbols` with 660 real rows (552 functions, 108
classes), zero caller/callee noise.

**Three of the four flagged tests needed real fixes once `symbols` held
real data for the first time:** a duplicate-edge `GROUP BY` was missing
`file_path` (flagging cross-file line-number coincidences as duplicates);
two tests were checking that stdlib/builtin/external callees resolve
against the project's own symbols table (wrong invariant - restricted both
to `WHERE bucket = 'project'`, confirmed 0 unresolved vs. ~170 false
positives before); the uniqueness test's `GROUP BY` was missing
`symbol_type`/`line_number`, flagging legitimate same-named methods on
different classes in the same file as duplicates - now effectively a
regression guard against the `symbols.canonical_id UNIQUE` constraint ever
loosening. The fourth (`test_symbol_storage_format.py`) needed no change,
it passed once the pollution block was gone.

**Full sweep after all fixes: 110 passed, 0 failed, 0 skipped, 0
collection errors** (up from 106 passed / 4 failed at the start of this
run-on session).

### 2026-06-17 (Pass 2) - older predecessor docs assessed and disposed; semantic-identity-reconstruction findings surfaced

Bart's go-ahead to do Pass 2: assess `docs/current predecessors still
useful/` (3 files) and an older predecessor subfolder (7 files) for
whether their vision still aligns, is partially superseded, or fully
superseded - grounded against the actual current codebase, not just read
against each other.

**Disposition of all 10 files:**

- `architectural triage protocol.md` - left in place, unchanged. Already
  carries a 2026-06-16 status note marking the methodology "still a
  reasonable process" with one corrected stale reference
  (`run_analysis_pipeline.py` -> `engine/run_engine.py`). No new findings.
- `old checklist.md` (the "C3" classification model) - left in place, new
  status note added. Still substantially describes current reality:
  `route_symbol()` -> `_route_symbol_core()` is the same single-pipeline,
  no-re-entry model, and `classification_gap` is alive across the current
  codebase. What it predates: the shadow/trace observability layer (see
  DESIGN.md section 4 below).
- Three files specific to an exploratory test-coverage pipeline - left in
  place at the time with a status note (not superseded, actually built,
  but only satisfying the structural contract, not the substance). Bart
  later decided to remove that pipeline from the codebase entirely
  (2026-06-17), which makes these three files moot along with it.
- `Module Governance.md` - moved to `docs/del/`. Superseded in specifics
  (file paths, `run_analysis_pipeline.py`/reducer ownership - that file is
  deleted) but its module-card methodology (OWNS / DOES NOT OWN / OUTPUTS /
  INVARIANTS / MATURITY) is the direct conceptual ancestor of DESIGN.md
  section 4's Authority Model, which superseded it.
- `Key insight about what we missed and where we are going.txt` - moved
  to `docs/del/`. Its diagnosis (premature semantic flattening in
  `route_symbol()` - leaf names like "dataclass" can't match
  fully-qualified project identities) was correct and was acted on;
  superseded by the fix now documented in DESIGN.md section 4.
- `Semantic Identity Reconstruction Migration Plan.md` - moved to
  `docs/del/`. Partially superseded - see the semantic-identity-
  reconstruction status correction (open item 15, section 3) for the full
  finding.
- `status as of 05242026.txt` - moved to `docs/del/`. A snapshot-in-motion
  ("Phase 2 actively working, Phase 2.5 emerging, Phase 3 not started")
  whose motion has since stopped/redirected - historical waypoint only.
- `test file list.txt` - moved to `docs/del/`. Flat reference list, no
  standalone content to assess.

**New findings, written up in full in DESIGN.md and TRACKER.md (not
repeated here):**

- DESIGN.md section 4 gained a new "shadow/observability layer" subsection
  documenting `route_symbol_shadow()`/`TraceCollector`/CP0-CP4 as real,
  live, currently-undocumented architecture.
- TRACKER.md gained two open items in section 3: a status correction for
  semantic identity reconstruction ("Phase 3 not started" corrected to
  "Phase 3 deliberately abandoned, different but stable end state
  reached" - now item 15), and a decision-needed item for the exploratory
  pipeline noted above. The latter was later removed outright once Bart
  decided to delete that pipeline rather than finish or integrate it.

### 2026-06-17 (later still) - Tier 2 evaluation: Stability/Integrity/Subsystem/Role usefulness

Per section 3 item 1 (top of the priority-ordered open-items list): the
four Tier 2 checklist items were all "correctness-verified, not yet
evaluated against real tasks." Did the evaluation for real, against a real
DB - not the hand-seeded fixture data `tests/regression/` uses - by running
`EngineRunner` over this project's own `tools/` corpus (same pattern as
`tests/core/test_engine_smoke.py`) and querying all 6 views through
`Assessor`/`ask.py`. Result: 157 files, 631 symbols, 2127 references, a
real non-trivial graph. Verdict for all four: see section 1b's Tier 2
block, now closed with detailed verdicts. Summary here; evidence and root
causes only, not repeated from section 1b:

**Stability/Integrity (evaluated together - they share one data source):**
`Assessor.file_contract_reports()` has exactly one contract check: does a
persisted `symbol_reference` have a null caller or callee. Against the
real 157-file DB this returned 142 stable files, 0 unstable, 0
drift_signals - not because the project has zero real issues (this
project's own incident history says otherwise - dead bucket-gate, orphaned
Filter, hardcoded `drift_signals=[]`, etc., none of which this check is
shaped to catch), but because a working ingestion pipeline simply doesn't
produce null caller/callee pairs. The check is real and correctly wired,
it's just answering a narrower question ("did ingestion corrupt this row")
than its view names ("STABILITY", "drift_signals") suggest. Looked for
richer validation already built but unused, same shape as the Row 2/3/4
wiring gaps closed earlier this week, and found two: `validation/
system_validator.py`'s `SystemValidator` class (which `Assessor.
validation_summary()` bypasses, reimplementing 2 of its 4 checks inline
and dropping its `_validate_contracts` escalation path) and `validation/
contract_validation_pass.py`'s `ContractValidationPass` (zero callers
anywhere, confirmed via grep). Also found `IntegrityView.db_mismatches`
(`truth/views.py`) is permanently hardcoded `[]` ("no DB comparison
anymore") - an orphaned-looking field nobody has flagged since the
drift_signals fix. Recorded as new open items 16 (partial) and 17.

**Subsystem interpretability:** the Row 4 fix (real module_map instead of
dotted-name heuristic) holds up - 31 subsystems against the real DB,
matching the project's actual ~27 top-level package directories
(api/, assessor/, graph/, oracle/, truth/, ...), not the previous ~355
near-singleton fragmentation. But inspecting the real output surfaced two
new issues: (1) `oracle/db_oracle.py`'s `_file_path_to_module()` doesn't
trim the stored `file_path` to a project-relative path before dotting it,
so subsystem identity strings carry the full absolute filesystem path
(confirmed: `sessions.eloquent-magical-bohr.mnt.dj2.tools.analysis.oracle`
instead of `tools.analysis.oracle` in this session's sandbox) - the
codebase already has two correct utilities for this
(`core/pathing.py` and `graph/module_resolution.py`, both named
`module_name_from_file_path()`) that `_file_path_to_module()` didn't
reuse; (2) the per-subsystem "modules" dependency list has no
builtin/stdlib filtering (confirmed: `len`, `str`, `RuntimeError`,
`print`, etc. appear as cross-subsystem dependencies), unlike hotspot
ranking which explicitly excludes builtins. Recorded as new open items 16
(the path issue) and 18 (the noise-filtering issue).

**Role classification interpretability:** `engine/responsibility_map.py`'s
`detect_file_roles()` keyword-matches role-pattern substrings (e.g.
"graph", "report", "symbol") against the joined text of a file's path plus
all its callees' names. Verified directly against real callee data why
this misclassifies: `db_oracle.py` (a persistence/query-layer file) is
flagged with `classification=True`/`graph=True`/`reporting=True` solely
because it references `tools.analysis.graph.graph_builder.GraphBundle`/
`GraphEdge` (a type it consumes, not builds), `oracle.embedding_model.
embed_symbol`/`symbol_noise.is_accessor_chain_noise` (substring "symbol"),
and a plain `print()` call (substring "report" - no, substring match is
on "print" itself, which is in the `reporting` pattern list). The heuristic
conflates "calls something whose name contains keyword X" with "this
file's job is X." Orchestrator files fare better by accident:
`run_engine.py` correctly gets every role true, since it really does call
into every subsystem - true, but undifferentiating, since the same
"all roles true" output would result from a file that haphazardly touched
one function in each subsystem with no real orchestration responsibility.
No new tracked item for this one - the fix (move from callee-substring
matching to declared-import/declared-call-target analysis, or to the same
DB-backed module_map used for SUBSYSTEM) is more of a redesign than a
mechanical bug, and is better left as a judgment call for whenever Role
classification becomes load-bearing for something, rather than speculative
work now.

**Method note:** this is the first session to evaluate a Truth Layer view
against a real engine run rather than either the regression suite's
hand-seeded fixture or a single one-off question. Worth keeping as the
default evaluation method going forward - the fixture is good for proving
mechanics aren't stub code, but every usefulness finding above only showed
up against real data shape (real file count, real callee names, real
absolute paths).

**Note on Ollama availability:** Ollama is not reachable from a sandbox
session, so all `ask()` calls in a sandbox go through the rule-based
compiler fallback, not the live LLM path - irrelevant to view/signal
evaluation but worth flagging so a future session doesn't mistake
fallback-path output for AI-compiler output.

### 2026-06-17/18 (item-16 fix session) - SUBSYSTEM path-pollution fix (item 16) closed

Followed Bart's standing reprioritization instruction ("anything high
priority affecting other sections would be good, otherwise take them in
order, update in an understandable way") to work item 16 ahead of item 2:
`_file_path_to_module()` is shared by the SUBSYSTEM view and by
`find_modules()`/`symbol_module_map()`, general-purpose discovery-API
primitives that future Agent Capability Layer work (item 13) is expected
to build on, so the path-pollution bug would otherwise have propagated
into whatever gets built on top of discovery next.

Fix turned out larger than item 16's original framing ("mechanical - reuse
an existing utility"): both existing `module_name_from_file_path()`
utilities need an explicit `project_root`, and nothing persisted one.
Added: `project_meta` key/value table; `persistence_engine.
set_project_root()`, called from `persist_all()`'s new optional
`project_root` param; `EngineRunner.run()` threading its `repo_root`
through; `DBOracle.get_project_root()` (persisted value, falling back to
common-directory-prefix inference for pre-existing DBs); and
`_file_path_to_module()` gaining an optional `project_root` param
(default `""`, exact prior behavior preserved for callers that don't pass
one). New regression file `tests/regression/
test_subsystem_path_pollution_fix.py` (7 tests). Full suite: 85/85 passed,
no regressions.

### 2026-06-18 (item-17/18 fix session) - INTEGRITY view gap (item 17) and SUBSYSTEM builtin filter (item 18) both closed

Per Bart's "if the small ones are independent of [item 2] let's get them
done" - item 2 (mutation-intent capture) stays explicitly deferred,
untouched this session.

Item 18 (SUBSYSTEM dependency lists not builtin/stdlib-filtered):
`build_subsystem_view()` gained an optional `builtin_symbols` set,
sourced from the same DB-authoritative `DBOracle.builtin_symbols()` that
hotspot ranking already uses, and now skips any edge where the caller or
callee is a confirmed builtin before module resolution.
`Assessor.subsystem_view()` was updated to pass it through. New
regression file `tests/regression/test_subsystem_builtin_noise_filter.py`
(5 tests). See section 3 item 18 (now closed) for full detail.

Item 17 (INTEGRITY view thinner than the codebase's own validation logic):
two real gaps, fixed together. (1) `Assessor.validation_summary()` now
calls the real `SystemValidator._validate_contracts()` /
`_validate_graph_integrity()` / `_validate_shape_signals()` instead of a
parallel inline reimplementation that never escalated contract violations.
`_validate_contracts` itself had a shape bug - bare `getattr()` against
violations that are actually dict-shaped in production, so an
error-severity violation never escalated, no visible failure - fixed with
a new `_field()` helper in `system_validator.py` (same precedent as
`contract_drift_classifier.py`'s `_field()` and `query_executor.py`'s
`get_field()`). (2) `IntegrityView.db_mismatches` was permanently
hardcoded `[]`. Reviving `engine/structural_parity_diff.py`'s
`run_structural_diff()` was investigated and ruled out - it needs an
in-memory object Assessor's DB-only architecture never produces, and
wiring it would mean fabricating data, which "never invent information"
rules out. Used what's real instead: `Assessor.run_integrity_check()`'s
already-computed `edge_count_mismatch` signal (`graph_edges` vs
`symbol_references` table-count disagreement), extracted via a new
`Assessor.db_mismatches()` and threaded through `build_integrity_view()`'s
new optional `db_mismatches=None` parameter. New regression file
`tests/regression/test_integrity_view_wiring.py` (6 tests).

Full project test suite after both fixes: 96/96 passed
(`pytest tools/analysis/tests/`), no regressions.

### 2026-06-18 (item 20: code-quality / weak-spot audit of live, wired code)

Per Bart's request ("next" -> confirmed "start item 20"): a robustness/
fragility review of code that IS wired and running, independent of item
21's dead-code/orphaned-module disposition focus.

**Scope method.** Computed the real live module surface by static
import-graph reachability (Python `ast`, no dynamic execution) starting
from the two real entry points: `ask.py` (query side: `python
tools/analysis/ask.py <db_path> "<question>"`, wraps `Assessor.ask()` ->
`QuerySession.run_algebra()`) and `engine/run_engine.py` (ingestion side:
scans the project, populates the SQLite DB). Result: 50 modules reachable,
64 not. Cross-checked two ways: grepped for `if __name__ == "__main__"`
(7 files, all already accounted for in the reachable/not-reachable split);
compared the 64 unreached modules against item 21's known orphaned-module
candidate list - they line up closely, which cross-validates the item 20 /
item 21 boundary rather than leaving it as an assumption.

**Audited the 50 live modules for:** bare/swallowed excepts, TODO/FIXME/HACK
debt, hardcoded stub/placeholder returns reaching production output, and
exception-handling that doesn't match its own docstring's promised
behavior. Found zero bare `except:`, zero TODO/FIXME/HACK comments. Found
three `except Exception` sites (schema check in `query_session.py`'s
`QuerySession.__init__`, session persistence in `query_session.py`'s
`persist_query_session()`, gap-recording in `system_self_model.py`) - all
three are deliberate, well-commented, non-fatal "record the gap, don't
invent" patterns consistent with the project's stated principles, not bugs.
`observability/fault_injector.py`'s `inject_edge_drop()`/
`inject_classification_drift()` are confirmed hard-gated off by
`ENABLE_FAULTS = False  # hard off for now` in `engine/run_engine.py` line
14 - working as intended, not a live concern.

Two genuine gaps were found. Both are reported here as audit findings -
**neither has been fixed**; fixing is a separate decision for Bart,
tracked as TRACKER.md items 22 and 23.

**Finding 1 - embedding-fallback crash risk (TRACKER item 22).**
`oracle/db_oracle.py`'s `discover_seed_symbols_semantic()` and
`discover_seed_symbols()` wrap the `sentence-transformers`/
`embedding_model` import in `try/except ImportError` and document that
they "fall back to token-based if the sentence-transformers package is not
installed." But the actual model load (`embedding_model.get_model()` ->
`SentenceTransformer("all-MiniLM-L6-v2")`, lazy-loaded on first call) and
every inference call (`embed_text()`, used at `db_oracle.py` line 628) sit
*outside* that try block. A failure there - HuggingFace download/network
failure, corrupted local model cache, anything other than "package not
installed" - is not caught and does not degrade to the documented
token-only fallback; it propagates. This is on the hot path of every
real query: `assessor/query_session.py`'s `run_query()` (line 159) calls
`route_query(text, graph, self.oracle.discover_seed_symbols, ...)` at line
164 with no surrounding try/except of its own, so any uncaught exception
from the embedding path crashes the whole `ask.py` invocation.

**Finding 2 - dead `runtime_bindings` wiring, "runtime" bucket
permanently empty in production (TRACKER item 23).** This is the same bug
shape as the two previously-fixed "looks wired but isn't" gaps (hardcoded
`drift_signals = []`, hardcoded `IntegrityView.db_mismatches = []`, both
above) - a real, individually correct, individually-tested piece of logic
that never actually reaches production output because the wiring
connecting it was never completed.

`ingestion/parse_ast.py` contains two separate, disconnected
`runtime_bindings` code paths:
- The real one: `_extract_runtime_bindings()`, called internally at line
  150 inside `_extract_symbol_references()`, feeding a local
  `runtime_bindings` variable used only for that function's own
  call-resolution at line 197 (`resolved = alias_map.get(raw) or
  runtime_bindings.get(raw) or local_symbol_map.get(raw)`).
- The production one: `parse_ast()` (lines 477-548) takes
  `runtime_bindings` as an *external parameter* (line 483:
  `runtime_bindings = runtime_bindings or {}`) and stores whatever it's
  given directly onto `FileAnalysis.runtime_bindings` (line 545) -
  *without* ever calling `_extract_runtime_bindings()` itself.

The external parameter all but always arrives empty: `ingestion/
scan_project_files.py` line 192 hardcodes `runtime_bindings = {}  # still
placeholder for now` and that empty dict flows straight through
`analyze_files()` (line 205) into every `parse_ast()` call in the real
ingestion pipeline (`engine/run_engine.py` -> `scan_project_files()` ->
`analyze_files()` -> `parse_ast()`).

Downstream, `classification/classify_references.py`'s real production
function builds its `ProjectGraphContext` and calls `route_symbol(name=
ref.callee, runtime_bindings=analysis.runtime_bindings, ...)` for every
single symbol reference - so it always classifies against an empty
`runtime_bindings` dict, meaning the documented `runtime` bucket (per
`classify_references.py`'s own contract comment: `project | runtime |
builtin | stdlib | external | unknown`) can never be assigned in
practice, no matter what the code actually does at runtime.

Verified empirically against the real project DB:

    sqlite3 ... "SELECT bucket, COUNT(*) FROM symbol_references GROUP BY bucket ORDER BY 2 DESC"
    -> ('builtin', 895), ('project', 803), ('stdlib', 308), ('external', 256)

Zero `runtime` rows out of 2262 total references - the smoking gun.
`tests/regression/test_runtime_resolution_lock.py` (and similar) still
pass because they construct `SymbolEnvironment`/`FileAnalysis` fixtures by
calling `_extract_runtime_bindings()` (or building the dict by hand)
directly, bypassing the broken production wiring entirely - so test-green
gave no signal that the real pipeline never produces a non-empty
`runtime_bindings` in practice. A fix, if Bart wants one, would have
`parse_ast()` call `_extract_runtime_bindings()` itself and thread the
result onto `FileAnalysis.runtime_bindings`, replacing the
`scan_project_files.py` placeholder - not attempted this session, since
item 20 is an audit/report task, not a fix task.

**Regression baseline:** 74/74 passed across 13 modules. Neither finding
above is currently caught by any existing test.

**Outcome:** item 20 closed as an audit/report deliverable; two new
tracked items opened (22, 23) for Bart to prioritize fixing or explicitly
deferring. No code was changed this session.

### 2026-06-18 (SystemSelfModel session) - item 19 closed

`SystemSelfModel` (`inspection/meta/system_self_model.py`) documented and
tested. See TRACKER.md section 3 item 19 (now closed) for full detail.

### 2026-06-18 (items 22+23 fix session) - embedding-fallback crash risk and dead runtime_bindings wiring both closed

Items 22 and 23 from the item-20 audit, fixed together since they were
both "wiring never completed" shapes.

Item 22: `oracle/embedding_model.py`'s model-load and inference paths
wrapped in try/except, falling back to token-based discovery on any
failure, not just `ImportError`. Confirmed the fallback actually fires by
verifying against a test that induces a model-load failure.

Item 23: `parse_ast()` now calls `_extract_runtime_bindings()` itself and
threads the result onto `FileAnalysis.runtime_bindings`, replacing the
`scan_project_files.py` `{}` placeholder. Verified empirically: re-ran
the ingestion pipeline and confirmed non-zero `runtime` rows in
`symbol_references`.

6 new regression tests. Full suite: 80/80 (74 prior + 6 new).

### 2026-06-18 (doc consolidation) - TRACKER.md/HISTORY.md split + DESIGN.md expansion

Bart's direction: keep TRACKER lean (current status, open items) and move
the historical record out. HISTORY.md (this file) created as the new home
for the session log and defect details, split from TRACKER.md section 4.
DESIGN.md expanded with new sections covering the shadow/observability
layer and Authority Model that had been living only in predecessor docs.

Five older per-topic docs retired to `docs/del/` after the consolidation
was cross-checked (three independent passes) for anything factual that
didn't make it across: REFACTOR OPS BOARD.md, Truth Kernel Board.md,
Truth.md, TRUTH KERNEL v1.md, todo-done.md. Nothing found missing.

### 2026-06-19 (ingestion run) - three external corpora ingested; regression proof added

Ingested all three candidate corpora from section 3 item 1 using the
headless `EngineRunner().run(corpus=..., project_prefixes=[],
repo_root=..., connection=...)` pattern:
- `tools.old/` - 73 files, 2764 graph_edges
- `external_corpora/flask/src` - 24 files, 800 graph_edges
- `external_corpora/sqlalchemy/lib` - 255 files, 20769 graph_edges

Row counts confirmed by direct query against each resulting DB. The sqlite
`PRAGMA journal_mode=MEMORY` workaround (section 2b) was required for all
new DB files.

Permanent regression proof added:
`tests/regression/test_external_corpus_ingestion.py` (2 new tests,
asserting a known real symbol from `tools.old/` appears correctly in
`graph_edges` after ingestion). Full suite: 82/82.

Also repaired `.git` directories for `external_corpora/flask` and
`external_corpora/sqlalchemy` - both had kept an empty clone skeleton
instead of the real git history after a prior Windows rename/move cleanup.
Real `.git` recovered from sandbox-local clones and swapped in.

### 2026-06-19 (orphaned-module disposition review) - item 12 investigated and reported

Investigated all 9 originally-listed orphan candidates plus the empty
`orchestration/` directory and `specification/tool_system_contract.json`,
checking actual wiring (import/call-site grep across the whole tree), not
just file contents in isolation.

Key findings:
- Most candidates confirmed genuinely dead (zero callers anywhere).
- `inspection/explain_file.py` - complete, ready-to-use capability that
  nothing currently calls. A real "hole," not dead weight.
- `api/get_llm_context.py` - not orphaned despite zero in-repo callers;
  it's the documented external integration point for a consumer (the
  future agent) that doesn't exist yet.
- `contract_types.py` + `specification/tool_system_contract.json` + empty
  `orchestration/` directory - three pieces of one coherent, unfinished
  feature, not independent dead files.
- New finding outside the original list: `contracts/load_contract.py`'s
  consumers load a different `tool_system_contract.json` (the one in
  `contracts/`, schema_version 3) and would `KeyError` immediately if
  called, since that file has no `domains` key. Dormant only because
  nothing calls it.

No integrate/dispose/delete actions taken - per the item's own gate:
report findings to Bart before any disposal. Full per-item findings in
TRACKER.md section 3 item 12.

Also re-sequenced TRACKER.md's Dashboard "Now / next" list: game-code
corpora ingestion now comes ahead of Row 1/Row 5, since Row 5's new
ingestion-capture design should be informed by real target-domain mutation
patterns.

---

## UI Navigation + Editor Experiments (2026-06-25)

Ran 7 time-boxed trials to find the right navigation and code-viewing
paradigm. Each branch deleted after verdict. Full protocol was in
docs/EXPERIMENTS.md, which is also now retired.

Results:
- Trial 1 (spotlight panel): PROMISING → graduated to main. Click symbol,
  get risk/callers/callees/intent/findings in a side panel. Backtick-based
  symbol detection, dotted-callee linkification, builtin filtering.
- Trial 2 (call-tree): KILL. Degenerates to a clickable list — no spatial
  position, no inline annotation.
- Trial 3 (graph/Cytoscape): PROMISING → graduated to main. Force-directed
  neighborhood, risk coloring, node tap opens spotlight. Graph = terrain,
  spotlight = inspect.
- Trial 4 (trail/notebook): DEFERRED. Not enough saved investigations yet.
- Trial 5 (inline viewer): PROMISING → graduated to main. "View source"
  button in spotlight renders function body with line numbers in-panel.
  Uses ast.end_lineno for accurate boundaries. No external dependency.
- Trial 6 (Sublime Text): KILL. subl path:line works from CLI but socket
  event never reached server handler. Scrapped: external editor launch is
  out of scope — the tool is the examination surface.
- Trial 7 (Lite-XL): KILL. No CLI argument for line numbers; treats all
  args as file paths. Same scoping decision as Trial 6.

Navigation loop on main: graph (terrain) → spotlight (inspect) → inline
viewer (read). External editors: users open independently if needed.
