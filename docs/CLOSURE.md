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
- [ ] Stub density per file (stub count / total function count)
- [ ] Dominant classification per file (which class wins across all stubs in file)
- [ ] Output: ranked file list, density score, dominant label, sample evidence
- [ ] Pass criterion: dnd_data.py shows dead-concept dominant; context_builder.py
      shows design-intent/blocked dominant

**Subsystem shape**
- [ ] Cluster stubs by directory/subsystem
- [ ] Clustered blocked-on-prerequisite = design skeleton signal
- [ ] Clustered concept-not-applicable = dead concept remnant signal
- [ ] Pass criterion: dj2 world/ surfaces as design skeleton (5 AI-layer stubs)
      and dnd_data.py subsystem surfaces as dead concept remnant (5 subrace stubs)

**Prerequisite map**
- [ ] Extract named prerequisite from blocked-on comments ("until X is built",
      "when X exists", "blocked on X")
- [ ] Group stubs by shared named prerequisite
- [ ] N stubs sharing prerequisite X → X is a build priority, ranked by N
- [ ] Pass criterion: dj2 AI-layer stubs surface a common prerequisite (AIDungeonMaster /
      AdjudicationEngine / ActionQueue) with count

**Concept ghost map**
- [ ] Concepts named in stubs but absent from live codebase symbols
- [ ] Cross-reference with find_concept_ghosts (already built, RM66)
- [ ] Output: concept name, stub count referencing it, verdict (ghost / partial / live)
- [ ] Pass criterion: CombatFSM surfaces as a ghost (named in contract, no symbol exists)

### 1c. Integration

- [ ] Projections accessible as agent tools (wire into tool_registry, TOOLS)
- [ ] Regression tests for each projection shape (in-memory DB, known stub sets)
- [ ] Full test suite passes (currently 1095 pass, 1 skip — must not regress)

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

Structural integrity: done (2026-07-16). Probe: pending.

Known issue to verify: Q5 confabulation. In session 140 the model invented a
query_router/query_session pipeline that doesn't exist. Fix A (2026-07-15) added
symbol-existence checks to verify_claim. Must confirm Q5 no longer confabulates
against the current Determined corpus before calling this probe passed.

- [ ] Q1 Entry points
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (3 real stubs known: 2x __init__, 1x suggest_tags)
- [ ] Q5 Design drift — also verify no confabulation of non-existent symbols (Fix A check)
- [ ] Q6 Call chains
- Findings:

### dj2 (Python+JS)

Stub sweep: done. 5 RM68-remove, 5 AI-layer gaps. Judgment: pending RM69 Phase 2.

- [ ] Q1 Entry points (331 inferred EP ceiling accepted as dynamic-dispatch floor)
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (10 known real stubs, correct classification is the pass criterion)
- [ ] Q5 Design drift
- [ ] Q6 Call chains
- Findings:

### Commonplace (Python)

Stub sweep: done (1 stub: suggest_tags). Probe: pending.

- [ ] Q1 Entry points
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (suggest_tags should classify as design-intent-stated)
- [ ] Q5 Design drift
- [ ] Q6 Call chains
- Findings:

### rotjs (TS library)

Known issue: lib/ (compiled output) vs src/ (TS source) dual-representation.
lib/ gets all EP; src/ has architecture. Scope to src/ for probe.

- [ ] Q1 Entry points (scope=src/)
- [ ] Q2 Blast radius
- [ ] Q3 Feature shape
- [ ] Q4 Stubs (6 known stubs: 3 in lib/, 1 in src/)
- [ ] Q5 Design drift
- [ ] Q6 Call chains
- Findings:

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
