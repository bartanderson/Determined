# Closure Checklist — Engine to UI

Goal: bring the analysis engine to a stable, demonstrable state before redesigning
the UI for other developers to follow. These are the things that matter for closure.
Burnishing (edge cases, corner rounding, optimization) comes after.

Updated in place as items complete. Each item gets a date when done.
New discoveries go in the "Emerging items" section of the relevant phase.

---

## Phase 1 — Judgment layer complete (RM69)

The single most important remaining piece. Without corpus-level projections the
UI has no higher-order story to tell. Single-stub classification (Phase 1) is done
and validated across three corpora (dj2, Determined, Commonplace) as of 2026-07-17.

### 1a. Magic method handling

Must ship before Phase 2 corpus sweep or magic method stubs will be misclassified.

`classify_stub` must look up `__init__`, `__str__`, `__repr__`, `__len__`, `__call__`
etc. by (class_name, file_path) rather than bare name, then use class context as
the primary signal. Five distinct cases (from HISTORY.md 2026-07-17, TRACKER.md RM69):

- [x] **Empty body, no docstring, no siblings** — UNCERTAIN, no signal. Formal
      path exists: is_lifecycle=True but no class context signals → falls through
      to existing genuinely-unknown scoring. (2026-07-17)
- [x] **Protocol/ABC membership** — `__init__` on a Protocol or ABC is flagged
      via `_extract_class_context` reading `base_classes_json`; `score_hypotheses`
      pushes design-intent-stated +1.5 and notes it in output. (2026-07-17)
- [x] **Class docstring states intent** — when stub has no docstring, class-level
      docstring is merged into `intent_text` and scored normally. (2026-07-17)
- [x] **Sibling stub density** — `class_sibling_stubs` (file-level proxy) adds
      blocked-on-prerequisite signal when ≥3 siblings present. (2026-07-17)
- [x] **Instance vars not set** — `_check_init_self_assigns` scans `__init__` body;
      no `self.x =` found → blocked-on-prerequisite +0.6. (2026-07-17)
- [x] Regression tests: 15 new tests, all pass (41 total in test_classify_stub.py)
- [x] No `__init__` collision: `file_path_hint` arg uses `WHERE name=? AND file_path=?`

### 1b. Corpus-level projections (Phase 2)

Each projection is a new aggregation layer above single-stub judgment. All four
must be implemented and validated before this phase is done.

**File shape**
- [x] Stub density per file (stub count / total function count) (2026-07-17)
- [x] Dominant classification per file (which class wins across all stubs in file) (2026-07-17)
- [x] Output: ranked file list, density score, dominant label, sample evidence (2026-07-17)
- [x] Pass criterion: dnd_data.py shows dead-concept dominant — 5/5 stubs concept-not-applicable (2026-07-17)
      Note: required adding _EXPLICIT_ABSENCE_RE fast-path in stub_classifier.py for
      "doesn't have" / "No X in Y system" phrasing that SetFit was missing.

**Subsystem shape**
- [x] Cluster stubs by directory/subsystem (2026-07-17)
- [x] Clustered blocked-on-prerequisite = design skeleton signal (2026-07-17)
- [x] Clustered concept-not-applicable = dead concept remnant signal (2026-07-17)
- [x] dj2 world/ run: shows dead-concept dominant (6/10 concept-not-applicable) (2026-07-17)
      Note: subrace stubs (5) dominate the 5 AI-layer stubs (2 design-intent, 2 unknown).
      Expected "design-skeleton" was wrong — subrace cleanup is the larger signal.
      After RM68 removes subrace stubs, world/ should flip to design-skeleton.

**Prerequisite map**
- [x] Extract named prerequisite from blocked-on comments ("until X is built",
      "when X exists", "blocked on X") (2026-07-17)
- [x] Group stubs by shared named prerequisite (2026-07-17)
- [x] N stubs sharing prerequisite X → X is a build priority, ranked by N (2026-07-17)
- [x] dj2 world/ run: AI-layer stubs have bare docstrings, no named-prereq language. (2026-07-17)
      Tool correct. Expectation was wrong about corpus content. "encounter" (1 stub) found.
      Prerequisite map only fires when docstrings name the blocking concept.

**Concept ghost map**
- [x] Concepts named in stubs but absent from live codebase symbols (2026-07-17)
- [x] Cross-reference with find_concept_ghosts (already built, RM66) (2026-07-17)
- [x] Output: concept name, stub count referencing it, verdict (ghost / partial / live) (2026-07-17)
- [x] Pass criterion: CombatFSM surfaces as GHOST — EncounterFSM surfaces as live (2026-07-17)
      Note: required tightening ghost map matching from base-stripped substring to
      full-concept-name matching (CombatFSM → "combatfsm" not "combat").

### 1c. Integration

- [x] Projections accessible as agent tools (wire into tool_registry, TOOLS) (2026-07-17)
- [x] Regression tests for each projection shape (in-memory DB, known stub sets) — 35 tests (2026-07-17)
- [x] Full test suite passes — 1144 pass, 1 skip (2026-07-17)

### Emerging items — Phase 1

_(Add new discoveries here as they surface during implementation)_

---

## Phase 2 — Convergence probes (RM67)

For each corpus: does the tool answer the 6 canonical questions cleanly without
confabulation or misrouting? Until these pass, the UI may look broken on real queries.

**Canonical questions (run all 6 per corpus):**
1. Entry points — list_entry_points returns correct EPs, inferred count is at floor
2. Blast radius — blast_radius on a core symbol returns correct answer
3. Feature shape — list_features + feature_shape groups correctly, completeness% sane
4. Stubs — stub sweep: no false positives, real gaps correctly identified
5. Design drift — check_design_violations surfaces at least one real finding (or clean)
6. Call chains — walk_call_chain traces at least one real chain end-to-end

### Determined (Python)

Structural integrity: done (2026-07-16). Probe: done (2026-07-17).

- [x] Q1 Entry points — 160 EPs, top is list_entry_points (49 fan-out). Dominated
      by internal utilities, consistent with known EP ceiling. PASS.
- [x] Q2 Blast radius — dispatch correctly HOT: 124 callers, 1069 extended impact. PASS.
- [x] Q3 Feature shape — list_features works. determined/agent: 39% completeness,
      350 local-missing (cross-module calls; expected for multi-module system). PASS.
- [x] Q4 Stubs — 3 real stubs found; 9 test fixtures also surfaced (FALSE POSITIVES).
      Real: suggest_tags [design-intent-stated 0.70 ✓], __init__ x2 [UNCERTAIN, no signal ✓].
      Note: __init__ #2 is in determined/contracts/, not determined/assessor/ as SESSION_STATE said.
      classify_stub file_path must match full absolute DB path (relative paths miss silently).
      Bug filed: list_stubs should filter test/ files or tag them [TEST].
- [x] Q5 Design drift — not fully testable without ingested layer rules / design notes.
      Confabulation check: search_symbols("query_router") → nothing. BUT graph has dead
      edges run_query → determined.assessor.query_router.route_query (module deleted,
      edges remain). Fix A prevents confabulation; dead edges are a graph quality issue.
- [x] Q6 Call chains — main→run_question: correct (via cmd_ask). dispatch→classify_stub:
      no path (expected). ask→dispatch path traverses .append() list method as a hop —
      false path through collection method calls.
- Findings (bugs to fix):
  1. list_stubs: test fixtures show as stubs — filter files matching tests/ or tag [TEST]
  2. classify_stub docs: file_path must be full absolute path matching DB; relative fails silently
  3. graph_path: method calls on collections (.append, .get etc.) used as path hops → false paths
  4. Dead graph edges: run_query → query_router / query_session modules (deleted); ghost callee noise

### dj2 (Python+JS)

Probe: done (2026-07-17). 10 stubs: 5 subrace dead-concept (RM68 remove), 5 AI-layer design gaps.

- [x] Q1 Entry points - 93 HTTP routes across dungeon_app.py, world_app.py, routes/api.py.
      Flask app structure correctly identified. PASS.
- [x] Q2 Blast radius - `main` HOT: 140 direct callers, 681 extended impact. PASS.
      Note: blast_radius arg is `target` not `symbol`.
- [x] Q3 Feature shape - list_features: world/ shows 564 syms, 10 stubs (correct).
      feature_shape BFS on world/: 43 reachable syms, 39% completeness, 0 stubs shown.
      BFS-only stub count: stubs not reachable from external EPs show as 0 (by-design
      limitation; use list_stubs for authoritative stub count). PASS with note.
- [x] Q4 Stubs - 10 stubs found, 0 false positives. Test fixture check_parley correctly
      excluded by test_ prefix filter. 5 subrace + 5 AI-layer as expected. PASS.
- [x] Q5 Design drift - ai_command: 5 hits from requirements doc (scores 0.37-0.46).
      Surfaces real design context. Requires `symbol` arg. PASS.
- [x] Q6 Call chains - graph_path: main->interactive_mode (1-hop), main->print_result (2-hop)
      both correct. walk_call_chain from __init__: 48-node chain. PASS.
      Note: graph_path uses `src`/`dst` args not `start`/`end`.
- Findings:
  1. feature_shape stub count understates when stubs have only internal callers (BFS
     traversal from external EPs doesn't reach them). Authoritative stub count: list_stubs.
  2. blast_radius arg = `target`; graph_path args = `src`/`dst` (not symmetric with other tools).

### Commonplace (Python)

Probe: done (2026-07-17). 1 stub: suggest_tags (design-intent-stated, as expected).

- [x] Q1 Entry points - 8 HTTP routes (list_entries, get_entry, search, index, entry_detail,
      capture_form, capture) + 16 inferred EPs. Flask structure correct. PASS.
- [x] Q2 Blast radius - get_db HOT: 49 direct callers, 34 extended impact. PASS.
- [x] Q3 Feature shape - list_features: services/ shows 1 stub (correct). feature_shape on
      routes/: 7 implemented, 47% completeness (all service/storage calls are cross-feature). PASS.
- [x] Q4 Stubs - 1 stub (suggest_tags, 3 callers). Classified design-intent-stated [0.70].
      Intent language: "Ask LLM to suggest tags... STUB: returns empty list until LLM wired." PASS.
- [x] Q5 Design drift - No layer rules defined; no design_notes ingested. Tool returns clean
      "No layer rules defined" message (no confabulation). Not testable until ingest_design_docs
      runs, but tool behavior is correct. PASS.
- [x] Q6 Call chains - graph_path: extract->extract_metadata (1-hop),
      find_connections->_extract_keywords (1-hop). walk_call_chain: extract chain of 5 nodes
      (extract->extract_metadata/extract_full_content->truncate->clean). PASS.
- Findings: none. Clean corpus, all tools behave correctly.

### rotjs (TS library)

Probe: done (2026-07-18). 6 stubs: 3 src/ + 3 lib/ mirror. All computeFontSize (UNCERTAIN).

- [x] Q1 Entry points (scope=src/) - 156 inferred EPs (library, no HTTP routes). Public API
      methods correctly identified via feature_path=src. PASS.
- [x] Q2 Blast radius - RNG.getUniform HOT: 92 direct callers, 50 extended impact.
      Core RNG is the hot symbol for a roguelike lib. PASS.
- [x] Q3 Feature shape - list_features auto-detects lib/ vs src/ dual representation and
      flags it with a note suggesting src/ scope. feature_shape src/: 107 syms, 0 stubs
      shown (same BFS limitation as dj2), 83% completeness. PASS.
- [x] Q4 Stubs - 6 stubs found (3 src/, 3 lib/ mirror). All are computeFontSize variants
      with no docstring and 0 callers. classify_stub (no file_path): UNCERTAIN [0.35]
      correct — no intent stated. file_path_hint matching fails (finding #1). PASS.
- [x] Q5 Design drift - "No layer rules defined" (clean, no confabulation). PASS.
- [x] Q6 Call chains - graph_path: color.randomize->RNG.getNormal (1-hop) correct. PASS
      with finding: walk_call_chain returns length 0 for TS corpora — graph_edges stores
      callers as FQNs (Cellular.randomize) but tool queries bare names (finding #2).
- Findings:
  1. classify_stub file_path_hint fails for TS corpora — path matching issue; workaround:
     omit file_path and rely on name-only lookup (finds lib/ version, result still valid).
  2. walk_call_chain broken for TS corpora: graph_edges FQN callers (Class.method) not
     matched by bare-name WHERE clause. Use graph_path for TS chain queries instead.
  3. list_features correctly auto-detects lib/ vs src/ dual representation (positive finding).

### dungeoncrawler (TS)

Appears clean (0 stubs confirmed). Probe pending.

- [ ] Q1 Entry points
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (expect 0)
- [ ] Q5 Design drift
- [ ] Q6 Call chains
- Findings:

### dnd-dungeon-gen (JS)

Known issue: JS callee resolution gap fixed (RM62, 2026-07-15) but corpus not
re-ingested since fix. Re-ingest first, then probe.

- [ ] Re-ingest dnd-dungeon-gen to pick up qualified callee names (RM62 fix)
- [ ] Q1 Entry points (were 0 before RM62 fix)
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (6 known stubs)
- [ ] Q5 Design drift
- [ ] Q6 Call chains
- Findings:

### end-of-eden (Go)

Phase 1 evaluation done (2026-07-15): system (270EP) and game (200EP) correctly
most-connected. 0 stubs confirmed. Full probe pending.

- [ ] Q1 Entry points (system + game as dominant, already validated partially)
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (expect 0)
- [ ] Q5 Design drift
- [ ] Q6 Call chains
- Findings:

### ruggrogue (Rust)

Phase 1 evaluation done (2026-07-15): file-level grouping correct, 0 stubs.
Has 20-chapter architecture guide — ground truth for Q3 and Q6.

- [ ] Q1 Entry points
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape (validate against architecture guide chapters)
- [ ] Q4 Stubs (expect 0)
- [ ] Q5 Design drift
- [ ] Q6 Call chains (validate at least one chain against architecture guide)
- Findings:

### Emerging items — Phase 2

_(Add new discoveries here as they surface during probe runs)_

---

## Phase 3 — Housekeeping before UI redesign

These don't block analysis correctness but they block clean handoff to other developers.

### RM68 — Remove subrace concept from dj2

The tool already classified these as dead concept remnants. Do this after RM69
Phase 2 so classify_stub can confirm the concept is fully absent post-removal.

- [ ] blast_radius on subrace stubs to confirm scope (3 files expected)
- [ ] Remove 5 stub functions from dnd_data.py
- [ ] Remove subrace references from dnd_data.py data structures
- [ ] Remove callers in character_generator.py
- [ ] Remove callers in authority_system.py
- [ ] Verify zero remaining references (`grep subrace` returns nothing in dj2/)
- [ ] Re-ingest dj2 and confirm stubs drop from 10 to 5

### Regex-for-semantic-meaning audit

One instance already fixed (stub_classifier, session 201). Survey the rest.
Goal: no pattern list anywhere in the engine is doing the job that embedding
similarity or a trained classifier should do.

Directories to survey:
- [ ] determined/agent/ — audit complete; findings:
- [ ] determined/oracle/ — audit complete; findings:
- [ ] determined/assessor/ — audit complete; findings:
- [ ] determined/ingestion/ — audit complete; findings:
- [ ] Fix any instances found (file here when done):

### Commonplace guided journey — current?

Commonplace is the on-ramp for new developers. It must reflect current tool
capabilities or new users will hit dead ends on the first session.

- [ ] Read docs/COMMONPLACE_VISION.md — still accurate?
- [ ] Walk the journey with current tool — does each step work?
- [ ] Update any stale steps to match current tool output format
- [ ] Confirm suggest_tags stub is classified correctly end-to-end in the journey

### Emerging items — Phase 3

_(Add new discoveries here as they surface)_

---

## Gate: UI redesign starts here

When Phase 1 + Phase 2 + Phase 3 are fully checked:

- The judgment layer gives the UI a higher-order story: what is this system
  trying to become, what's blocking it, what's dead code vs design skeleton
- Convergence probes confirm the tool doesn't confabulate on any corpus
- The codebase is clean enough that new developers aren't inheriting known junk
- The on-ramp (Commonplace) works end-to-end

Then: redesign the UI around the pipeline's actual power. The guided journey
is the on-ramp. The judgment layer outputs (corpus shapes) are the headline.
Corpus-level shapes are the thing no other static analysis tool shows.

---

## Deferred (not blocking UI, comes after)

- **RM21 — Remaining small-model reasoning techniques (Techniques 2, 4, 5, 6):**
  Technique 1 (verification loops) and Technique 3 (traversal pattern) are done.
  Remaining: constrained decoding (T2), MCTS over reasoning (T4), speculative
  verification (T5), large-model browser fallback (T6). All explicitly gated:
  build only after T1+T3 prove insufficient on real multi-hop queries. The
  convergence probes (Phase 2 above) are the trigger — if probes surface new
  confabulation patterns that T1+T3 don't catch, pick up RM21 here.
  Large-model fallback code already exists in dj2/tools.old/bridge/ if needed.

- **RM-Perf**: Optimization Oracle (static purity analysis + profiling overlay).
  Explicitly post-analysis-arc. Compelling for developer demos but not needed
  for closure. Static purity sub-tier (memoizable functions, dead event handlers)
  could ship as a standalone before the full profiling tier.

- **Burnishing**: threshold calibration, hypothesis count caps, signal weight
  tuning, edge case handling. Belongs after the pipeline is stable and the UI
  surfaces it cleanly. Log things here as they surface rather than picking at
  them now.

  _Burnishing log:_
  - SetFit edge case: "STUB: returns empty list until..." → concept-not-applicable
    (returns-empty pulls it that way; fallback handles correctly via embedding)
  - SetFit edge case: "Biometric verification is handled by..." → design-intent-stated
    (no explicit absence signal; acceptable borderline)
  - probe_pass2.py: unknown callee ratio query may have LEFT JOIN artifact (tagged [?])
  - classify_stub body_shape: _extract_body() not validated against all dj2 files
