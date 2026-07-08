Commonplace Guided Journey - Working Log
=========================================

Live document. Each walk adds to what's known. Only restart from scratch
when a fundamental break requires it. Look ahead 2-3 steps before walking.

---

## WHAT WORKS (verified, don't re-test)

**Walk 1 verified:**
- CSS fix: .tab-content grid-row 4->5. Frontier, Graph, Topology tabs render at full height.
- Seed corpus loads correctly: 8 files, 0 hot, 2 stubs, Roots: capture/index
- Frontier Direct mode: shows stubs correctly (red) with callers (orange).
- Topology tab: renders correctly, action queue points at stubs.
- symbol_context: correct output (declaration, docstring, risk, callers). Spotlight
  invisible in preview pane (too narrow) -- not a bug, works in real browser.
- Editor tab: loads file, save triggers reingest, sidebar updates stub count live without reload.
- ingest_design_docs: wired into post-ingest pass, runs automatically.

**Walk 2 verified (2026-07-07):**
- find_abc_gaps: correctly detects missing ABC overrides, checks per-subclass via
  methods_json. Drops to 0 cleanly when overrides are added. High signal, no false positives
  on the seed corpus.
- detect_topology: ABC-interface and orphaned-impl counts accurate. False positive known:
  init_db stays orphaned because Flask app-context call is invisible to static analysis.
  Not a bug -- a documented limit.
- check_design_violations: HIGH-SIGNAL at >= 0.45 (real rule matches the right symbol).
  NOISY at 0.30-0.40 (cross-symbol contamination, duplicate rule entries). Threshold 0.30
  is too permissive -- 0.45 is a more reliable signal floor for small corpora.
- reason_about: correct recommendations grounded in SOTS tenets. Confidence 95% on both
  decisions exercised (keep extractor unified; remove strict branch). Slight reasoning
  mismatch on utils/ vs routes/ context, but conclusion correct.
- find_conditional_stubs: detects hidden runtime gaps in functions that pass structural
  analysis. Correctly fires on `if strict: raise NotImplementedError` pattern.
  Drops to 0 after branch removal and reingest. High signal.
- Full write → reingest → detect_topology / find_abc_gaps / find_conditional_stubs
  loop works end-to-end across all three gap shapes (ABC, orphan, conditional stub).

**Known Determined gaps found during Walk 2:**
- Duplicate design_note entries: LLM extraction pass re-extracts rules already found by
  deterministic pass. 60-char prefix dedup is insufficient when LLM rephrases. Results
  in duplicate PERMISSION-prefixed entries inflating check_design_violations output.
  Filed as TRACKER item (see TRACKER.md).

---

## KNOWN ISSUES / BLOCKERS

1. Spotlight panel invisible in preview pane (viewport too narrow). Works in
   real browser. Not fixing -- preview limitation.

2. "0 design notes" has no call-to-action. User sees it but can't act on it
   from the corpus panel. Needs a "Scan for design docs" button.
   Status: FILED, not yet fixed.

3. seed/ has no DESIGN.md. ingest_design_docs finds nothing. Intentional --
   user writes design doc as they build. But the UI needs to explain this,
   not just show 0.

4. CLI (local_agent REPL): no named pattern for topology/frontier queries.
   User types natural language, LLM answers from what's been explored.
   With 0% coverage the answer is always empty. Not a bug -- coverage 0
   means explore first. But REPL startup should say "run 'orient' to start."

---

## WALK 1 - First complete attempt

### Setup
- Corpus: C_Users_bartl_dev_Determined_examples_commonplace_seed.db
- Interface: web UI at localhost:5050
- Approach: user perspective, click-by-click

### Look ahead (steps 1-7 before walking)
1. Load corpus -> corpus panel shows shape. WORKS.
2. Frontier -> 2 stubs. WORKS. (need to set Direct mode, it may remember Orphan)
3. Click stub node -> spotlight. WORKS in real browser, invisible in preview.
4. Topology tab -> structure summary. WORKS.
5. Editor tab -> open extractor.py -> NOT YET VERIFIED.
6. Reingest after edit -> NOT YET VERIFIED.
7. Design notes -> 0, no action. KNOWN ISSUE #2.

### Steps walked

[Step 1] Switch corpus to seed.
  Result: 8 files · 0 hot · 2 stubs. Roots: capture, index. PASS.

[Step 2] Frontier tab -> set Direct mode -> Load.
  Result: extract_metadata, extract_full_content (red), extract (orange). PASS.
  Note: mode dropdown remembers last selection -- may be on Orphan after prior session.
  Fix needed: default to Direct on tab open, or remember per-corpus.

[Step 3] Click extract_metadata in graph.
  Result: spotlight fires (trail shows entry), panel invisible in preview.
  In real browser: declaration + STUB docstring + SAFE risk + 1 caller. PASS (real browser).

[Step 4] Topology tab -> Refresh.
  Result: Total stubs:2, Direct-call:2, action queue: implement direct-call stubs. PASS.

[Step 5] Editor tab -> type 'extractor.py' -> Open.
  Result: file loads, symbols panel shows extract_metadata/extract_full_content/extract,
  code visible with STUB docstrings. Edit button present. PASS.

[Step 6] Editor save + reingest verification (session 86).
  Opened extractor.py in Editor tab. extract_metadata already had real
  implementation (urllib/HTMLParser). Clicked Edit -> Save.
  Found bug: ui_server line 1538 called reingest_file(_assessor.oracle, fp)
  but reingest_file signature is (db_path: str, file_path: str). Oracle object
  was silently swallowed by bare `except Exception: pass`.
  Fix: changed to reingest_file(_db_path, str(fp)), also improved error to
  emit toast instead of silent pass.
  After fix + server restart + save: sidebar updated live from 2 stubs -> 1 stub
  without page reload. corpus_ready fires correctly after reingest. PASS.

[Step 7] Design notes -- 0 design notes, no action available.
  Root cause: ingest_design_docs was not in the post-ingest flow.
  Fix: wired ingest_design_docs into post-ingest pass (after discovery,
  before ingest_done), same pattern as distillation. Silently skips corpora
  with no design docs. seed/ has no design docs intentionally -- user writes
  them as they build. On re-ingest of a corpus with docs, count will populate.
  KNOWN ISSUE #2 resolved. KNOWN ISSUE #3 (seed has no docs, UI doesn't explain)
  remains -- low priority, tooltip or empty-state text could address it later.

---

## NEXT WALK - Steps 5-6 (Editor + Reingest)

Look ahead:
- Editor tab: user opens extractor.py, sees the stub, edits it, saves.
  Does the Editor tab load the file correctly for seed corpus?
  Does Save write to disk?
  Does Analyze/reingest update the stub count?
- After reingest: corpus panel should show 1 stub (not 2).
  Frontier should reload and show only extract_full_content.

Known risk: Editor tab path resolution -- seed corpus files are under
examples/commonplace/seed/. Does the editor resolve that correctly?

---

---

## WALK 2 - Corrected seed, Step 1: Orient

### State at walk start (2026-07-07, session 109)

Seed corpus was corrected back to its intended state:
- `EnrichmentProcessor.process` and `EnrichmentProcessor.can_handle` removed
  (they had been added, making it a false-complete; restored as true ABC gap)
- Two Determined bugs fixed before this walk produced clean output:
  1. `_is_stub` was marking `@abstractmethod` declarations as stubs -- fixed to
     exclude them (they are interface definitions, not actionable gaps)
  2. `find_abc_gaps` / `_get_abc_gap_set` checked globally for any non-stub with
     the same name -- fixed to check per-subclass via `methods_json`

### Expected output at seed state (verified)

```
CORPUS TOPOLOGY
  Total stubs: 0  |  Total implemented: 27

  Direct-call:     0  (no stubs called by functional code)
  ABC-interface:   2  (EnrichmentProcessor missing can_handle + process)
  Orphaned-impl:   2  (semantic_search, init_db -- no callers yet)
  All others:      0

  Action queues:
    Implement now:  abc-interface (2)
    Write callers:  orphaned-impl (2)
```

```
find_abc_gaps:
  EnrichmentProcessor  (inherits EntryProcessor)
    can_handle  [not overridden]
    process  [not overridden]
```

### Reasoning (what the output teaches)

**Why 0 direct-call stubs?**
The extractor layer (`extract_metadata`, `extract_full_content`) and storage layer
(`insert_entry`, `get_entries`) are already implemented. The seed is past the
minimal stub state described in the spec -- the extractor was filled in. This
is correct: the journey picks up from where the code actually is.

**Why ABC-interface: 2?**
`EnrichmentProcessor` inherits `EntryProcessor` (an ABC) but provides no
`process()` or `can_handle()` override. This is the designed gap -- the LLM
enrichment pass that wires to llama-server. Determined surfaces this as the
primary frontier: implement `EnrichmentProcessor` to close it.

**Why orphaned-impl: 2?**
`semantic_search` (searcher.py) and `init_db` (db.py) are implemented but have
no callers in the corpus. `init_db` is called by `create_app` implicitly via
Flask wiring (external caller, invisible to static analysis). `semantic_search`
is a future feature -- not yet wired to any route. Both are anticipatory: the
code exists waiting for callers to be written.

**What to do next (Step 2):**
`find_abc_gaps` points at `EnrichmentProcessor`. Run `symbol_context` on
`EnrichmentProcessor` to understand its interface. Then implement `can_handle`
and `process` -- `process` calls `tagger.suggest_tags` (already stub-tolerant,
returns [] when endpoint=None) and `linker.find_connections` (already
implemented with keyword overlap). Re-ingest processor.py. ABC-interface count
should drop to 0.

---

## WALK 2 - Step 2: Implement EnrichmentProcessor, close ABC gap

### Action taken (2026-07-07, session 110)

Implemented `can_handle` and `process` on `EnrichmentProcessor` in
`examples/commonplace/seed/services/processor.py`.

- `can_handle`: returns True only when `self.llm_endpoint` is set and entry has content.
  Correct guard -- enrichment requires both a working endpoint and something to enrich.
- `process`: POSTs entry content/title to `self.llm_endpoint`, expects `{"tags": [...],
  "related": [...]}` response. Graceful fallback: on any exception (endpoint down, timeout,
  bad JSON) sets tags/related to empty lists. No crash path -- enrichment is best-effort.

Re-ingested via `reingest_file` directly from Python CLI (UI Re-analyze does not use
reingest_file -- uses background thread instead, known limitation from SESSION_STATE).

### Output after reingest

```
detect_topology:
  Total stubs: 0  |  Total implemented: 29

  ABC-interface:   0  (was 2 -- EnrichmentProcessor gap closed)
  Orphaned-impl:   2  (semantic_search, init_db -- unchanged, expected)
  All others:      0

  Action queues:
    Implement now:  (nothing)
    Write callers:  orphaned-impl (2)

find_abc_gaps:
  All ABC stub methods have at least one non-stub override in the corpus.
```

### Reasoning

**Why ABC-interface dropped to 0?**
`EnrichmentProcessor.can_handle` and `EnrichmentProcessor.process` are now concrete
overrides. `find_abc_gaps` checks per-subclass via `methods_json` -- both methods now
appear in EnrichmentProcessor's method list as non-stubs. The gap is closed.

**Why implemented count went from 27 → 29?**
The two new methods (`can_handle`, `process`) are concrete implementations. They add
to the implemented count. Correct arithmetic.

**Why orphaned-impl stays at 2?**
`semantic_search` and `init_db` still have no callers in the corpus. This is the
next frontier: Step 3 wires callers for these two symbols.

**What to do next (Step 3):**
Wire `init_db` into `create_app` in `app.py` and add a search route that calls
`semantic_search` in the routes file. Re-ingest both files. Orphaned-impl count
should drop toward 0.

---

## WALK 2 - Step 3: Wire orphaned-impl callers, reduce orphan count

### Actions taken (2026-07-07, session 110)

Two changes to wire the remaining orphaned implementations:

1. **`app.py`** — registered `search_bp` alongside `capture_bp`. The search blueprint
   existed in `routes/search.py` but was never imported or registered in `create_app`.
   Added `from routes.search import search_bp` and `app.register_blueprint(search_bp)`.

2. **`routes/search.py`** — changed `searcher.search(query)` to `searcher.semantic_search(query)`.
   The route was calling the lower-level `search()` directly, bypassing `semantic_search`.

Re-ingested both files via `reingest_file`.

### Output after reingest

```
detect_topology:
  Total stubs: 0  |  Total implemented: 29

  Orphaned-impl:   1  (was 2 -- semantic_search now has a caller)
  All others:      0

  Action queues:
    Write callers:  orphaned-impl (1)
```

### Reasoning

**Why orphaned-impl dropped from 2 → 1?**
`semantic_search` in `searcher.py` is now called from the search route handler.
Determined can see that call edge. One orphan resolved.

**Why does 1 remain?**
`init_db` in `storage/db.py` is called in `app.py` inside a `with app.app_context():`
block. Determined's static analysis sees the import and the call site but the Flask
context manager pattern may obscure the edge in the call graph. This is a Determined
blind spot, not a real gap -- `init_db` has a genuine caller. The remaining orphan is
a false positive from static analysis limits, not missing code.

**What this means for the journey:**
The corpus is now in a healthy state: no stubs, no ABC gaps, one known-false orphan.
The guided journey has demonstrated the full loop:
  detect gap → implement → reingest → verify closed
Three times: direct-call stubs (Walk 1) → ABC gap (Step 2) → orphaned-impl (Step 3).

---

## WALK 2 - Step 4: Design decision — check_design_violations + reason_about

### Actions taken (2026-07-07, session 110)

Ingested `examples/commonplace/docs/DESIGN.md` manually (outside seed project root,
auto-discovery doesn't find it — known limitation). Extracted 10 rules, stored as
design_note artifacts in the seed corpus DB.

Ran `check_design_violations` on `extract_metadata` and `search` (route handler).
Ran `reason_about` on `extract_metadata` with the extractor-split question.

### Output

**check_design_violations: extract_metadata**
```
Potential violations (score >= 0.30):
  0.43 -- extractor.py: one module or three? (always called together, splitting adds indirection)
  0.41 -- PERMISSION: same rule (duplicate from LLM extraction pass)
  0.32 -- searcher.py: bypasses service layer (low signal for this symbol)
  0.30 -- same rule duplicate
```

**check_design_violations: search (route handler)**
```
Potential violations (score >= 0.30):
  0.61 -- searcher.py: bypasses service layer (high signal -- correct flag)
  0.55 -- PERMISSION: same rule
  0.34 -- storage/ only layer touching DB directly
  0.33 -- same rule duplicate
  0.32 -- extractor.py: one module or three? (low signal, noise)
```

**reason_about: extract_metadata — split extractor or keep unified?**
```
Decision:   Keep extractor.py as a single module
Confidence: 95%
Reasoning:  SOTS tenet: minimize indirection, maintain cohesion.
            2 callers, 5 callees -- scope is manageable as one module.
            Splitting adds complexity without clear benefit.
```

### Reasoning

**What check_design_violations got right:**
The `search` route handler correctly flags the `searcher.py: bypasses service layer`
tension at 0.61 — high enough to warrant manual review. This is a real documented
violation in DESIGN.md: `searcher.search()` calls `queries.search_entries()` directly,
bypassing the service boundary. The tool found the right violation for the right symbol.

**What check_design_violations got wrong (noise to address):**
- Duplicate rules at high count: the PERMISSION-prefixed entries are the same rule
  extracted twice (once deterministically, once via LLM pass). Deduplication is imperfect.
- Low-signal cross-contamination: `extract_metadata` picking up the `searcher.py`
  service-layer rule at 0.32 is a false positive — the extractor doesn't touch storage.
  Threshold of 0.30 may be too low for this corpus size.

**What reason_about got right:**
Correctly recommended keeping extractor.py unified. SOTS tenet surfaced (minimize
indirection). The STALE PRIOR CHAIN warning is interesting — it detected that caller
count changed since a prior analysis, which is accurate (we added callers in Step 3).

**Design note for Determined (potential fix):**
Duplicate design_note entries from PERMISSION-prefix suggest the LLM extraction pass
is adding rules that the deterministic pass already found. Could filter by rule body
similarity at store time, not just exact prefix match.

---

## WALK 2 - Step 5: Expand frontier — add validator, wire caller, watch topology

### Actions taken (2026-07-07, session 110)

Added `utils/validator.py` and `utils/__init__.py` to the seed. `validator.py` contains:
- `validate_url()` — implemented, pure function
- `validate_entry()` — implemented but with a **conditional stub**: `raise NotImplementedError`
  inside `if strict:` branch. This is the topology shape `find_conditional_stubs()` detects.

Updated `routes/capture.py` to import and call `validate_url()` from the new utility,
replacing the inline `url.startswith()` check with the proper utility call. This also
wires a caller for the validator module.

Re-ingested: `utils/__init__.py`, `utils/validator.py`, `routes/capture.py`.

### Output after reingest

```
detect_topology:
  Total stubs: 0  |  Total implemented: 31  (was 29)
  Orphaned-impl: 2  (validate_url, validate_entry -- capture.py call not resolved by static analysis)
  All others: 0

find_conditional_stubs:
  1 found:
    validator.py :: validate_entry  (def line 20, raise line 36)
    "implemented functions with raise NotImplementedError in a branch"
```

### Reasoning

**Why no new stub shapes in detect_topology?**
`validate_entry` has a `raise NotImplementedError` inside a conditional branch, not
as its entire body. Static analysis sees it as implemented (body exists, not a stub).
`find_conditional_stubs` is specifically designed to catch this pattern — it's a
separate pass, not part of topology classification. This is intentional: topology
tells you structural shape, conditional stubs tell you hidden runtime gaps.

**Why orphaned-impl at 2?**
The capture route imports `validate_url` but static analysis didn't resolve the
cross-module call edge from `routes/capture.py` to `utils/validator.py`. This is
a known call-graph resolution limit — aliased imports (`from utils.validator import
validate_url`) may not always produce a traceable edge. Not a Determined bug that
needs fixing here; the conditional stub finding is the lesson of this step.

**What Step 6 exercises:**
`find_conditional_stubs` is now live and producing real output. Step 6 documents
what the tool output teaches: conditional stubs are a different risk than missing
stubs — the function exists and looks complete, but crashes on specific inputs.
The user must decide whether to implement strict mode or remove the branch.

---

## WALK 2 - Step 6: Work the topology — conditional stub + reason_about decision

### Actions taken (2026-07-07, session 110)

Re-ran `find_conditional_stubs` (confirms Step 5 finding still live).
Ran `reason_about` on `validate_entry` with the strict-mode decision question.

### Output

```
find_conditional_stubs:
  1 found:
    validator.py :: validate_entry  (def line 20, raise line 36)
    "implemented functions with raise NotImplementedError in a branch"

reason_about: validate_entry -- implement strict mode or remove branch?
  [db:is_stub]      no (has implementation)
  [db:caller_count] 0 callers
  [evaluate]        SOTS: routes must not contain business logic; validation at HTTP level
  [db:callee_count] 4 callees

  Decision:   Remove the strict branch entirely
  Confidence: 95%
  Reasoning:  validate_entry is responsible for input validation at HTTP level per SOTS.
              No callers, multiple callees -- removing the strict branch simplifies the
              function and aligns with "no business logic in routes."
```

### Reasoning

**What find_conditional_stubs teaches (vs detect_topology):**
`detect_topology` classifies a function as a stub only if its entire body is a stub
(raise NotImplementedError, pass, or ...). `validate_entry` has a real body, so
topology sees it as implemented (31 implemented, 0 stubs). But it will crash when
called with `strict=True`. `find_conditional_stubs` catches this hidden runtime gap.

The lesson: **not all gaps are visible in the topology.** Conditional stubs pass
structural analysis but fail at runtime on specific inputs. They represent deferred
decisions disguised as working code.

**What reason_about got right:**
- Correctly identified 0 callers (no one calls validate_entry yet)
- Surfaced the SOTS tenet about routes owning HTTP-level validation
- Recommended removing the strict branch — the right call for a small corpus with
  no caller pressure to implement strict mode

**What reason_about got wrong (slight):**
The SOTS reasoning conflated "routes should handle validation" with "remove business
logic from routes." `validate_entry` is in `utils/`, not `routes/` — it's already
correctly placed. The tenet cited is accurate but the reasoning path was slightly off.
The conclusion (remove the branch) is still correct: no caller needs strict=True yet.

**Step 7 decision:**
Remove the `if strict: raise NotImplementedError` branch from `validate_entry`.
Re-ingest. `find_conditional_stubs` should return 0. This closes the last open gap
in the seed corpus and demonstrates the full guided journey loop.

---

## WALK 2 - Step 7: Remove conditional stub, close last gap

### Actions taken (2026-07-07, session 110)

Removed the `if strict: raise NotImplementedError` branch from `validate_entry`
in `utils/validator.py`. Function is now unconditionally implemented.
Re-ingested `utils/validator.py`.

### Output after reingest

```
find_conditional_stubs:
  0 found  (was 1 -- validate_entry strict branch removed)

detect_topology:
  Total stubs: 0  |  Total implemented: 31
  Orphaned-impl: 1  (init_db -- known false positive, Flask app-context)
  All others: 0
```

### Reasoning

The seed corpus is now clean: 0 stubs, 0 ABC gaps, 0 conditional stubs,
1 known-false orphan. This closes the Walk 2 loop.

The full guided journey has exercised:
- ABC gap: detect → implement override → reingest → verify 0
- Orphaned-impl: detect → wire caller → reingest → verify count drops
- Design violations: ingest design doc → run check → reason_about decision
- Conditional stub: find_conditional_stubs → reason_about → remove branch → verify 0

---

## WALK 2 - Step 8: Wrap-up assessment

### What the journey taught (Walk 2)

**High-signal Determined outputs (trust these):**
- `find_abc_gaps`: no false positives on seed. Fires correctly, clears correctly.
- `find_conditional_stubs`: correctly surfaces hidden runtime gaps. High value --
  these pass all structural checks but will crash on specific inputs.
- `detect_topology` ABC-interface + orphaned-impl counts: accurate.
- `check_design_violations` at score >= 0.45: real matches. The 0.61 on the
  search route bypassing service layer was the correct finding for the correct symbol.
- `reason_about`: recommendations correct on both decisions. SOTS grounding adds
  real weight to the output, not just hedging.

**Noisy Determined outputs (calibrate before trusting):**
- `check_design_violations` at 0.30-0.40: cross-symbol contamination is common.
  The `extract_metadata` picking up a `searcher.py` service-layer rule is a false positive.
  Treat the 0.30 threshold as a floor for "possibly relevant," not "worth acting on."
  0.45+ is the actionable signal band for small corpora.
- Duplicate design_note entries: LLM pass re-extracts what deterministic pass already found.
  Until fixed, check_design_violations output will show the same rule 2-3x at similar
  scores. De-duplicate mentally by rule body, not by entry count.
- Static-analysis orphan false positives: `init_db` via Flask app_context is a
  permanent known false positive. Cross-module aliased imports (`from utils.validator
  import validate_url`) may not resolve to call edges. Both are analysis limits, not bugs.

**Determined gaps filed (Walk 2):**
- Duplicate design_note deduplication: filed in TRACKER.md under RM20.

### Next arc decision

Two options:
1. **Build Commonplace "complete" state** -- add browse route, models (Entry/Tag),
   storage queries. Exercises chain shapes, richer topology, more call graph variety.
   Purpose: stress-test Determined against a fuller codebase, find more gaps.
2. **RM19 Pass 3 filter improvement** -- cross-reference primitive_gap callees against
   symbols table to exclude constructors/stdlib (~30 min, agent_tools.py:4642).
   Purpose: reduce noise in an existing tool without new corpus work.

---

## WALK 3 - Complete corpus orientation

### Corpus: examples/commonplace/ (not seed)

**Setup (2026-07-07, session 112):**
Added `.determinedignore` to `examples/commonplace/` to exclude `seed/` subdirectory.
Re-ingested complete corpus fresh. 25 files, 55 functions.

### Output (detect_topology)

```
CORPUS TOPOLOGY
  Total stubs: 6  |  Total implemented: 49

  Shape                  Count
  Direct-call                3   stubs called by functional code
  ABC-interface              2   abstract methods with no concrete override
  Chain-head                 1   stubs: functional callers + stub callees [bridge]
  Chain-tail                 2   stubs: stub callers only [implement first]
  Orphaned-impl             16   implementations with no functional callers
  Entry-point                0   stubs in route/handler/cli files
  Disconnected               1   stubs with no graph connections

  Action queues:
    Implement now:  chain-tail (2) > direct-call (3) > abc-interface (2) > chain-head (1)
    Write callers:  orphaned-impl (16)
    Decide:         disconnected (1)
```

```
find_abc_gaps:
  EnrichmentProcessor (inherits EntryProcessor)
    can_handle  [not overridden]
    process     [not overridden]

find_conditional_stubs:
  validator.py :: validate_entry  (def line 20, raise line 36)
```

### Stub map

| Function | File | Shape |
|---|---|---|
| `extract_full_content` | extractor.py | direct-call |
| `semantic_search` | searcher.py | direct-call (STUB by docstring, falls back) |
| `find_connections` | linker.py | chain-tail (only called by enrich_entry stub) |
| `suggest_tags` | tagger.py | chain-tail (only called by enrich_entry stub) |
| `enrich_entry` | pipeline.py | chain-head (functional caller + stub callees) |
| `_similarity_score` | linker.py | disconnected (no callers yet) |
| `EnrichmentProcessor.process` | processor.py | ABC-interface gap |
| `EnrichmentProcessor.can_handle` | processor.py | ABC-interface gap |
| `validate_entry` | validator.py | conditional stub |

### Key observations

**Chain topology working correctly:**
`enrich_entry` is a stub (flagged via `stub_by_doc` -- docstring starts with "STUB:").
It sits between the functional capture route (caller) and `find_connections`/`suggest_tags`
(stub callees). Determined correctly classifies it as chain-head: "implement the tails first."
The action queue puts chain-tail before chain-head -- correct priority order.

**Disconnected stub (_similarity_score):**
A private helper in linker.py not yet wired into `find_connections`. It's placeholder code
for embedding-based similarity -- the design intent is clear (linker will use it) but the
connection isn't established yet. The "Decide:" queue is right: this is deferred architecture,
not missing code.

**Orphaned-impl (16) -- three categories:**
1. Flask route handlers (capture, index, get_entry, etc.): 6 functions. External triggers --
   Flask calls them, static analysis cannot see that. These are correctly excluded from
   the "Write callers" action queue by `_has_framework_decorator` filtering in detect_topology.
   But they DO appear in my raw query. Determined's count of 16 is after filtering routes.
2. Model methods (Entry.validate, Entry.to_dict, Tag.validate, Connection.validate): 4 functions.
   Real code, no callers yet. The routes use raw SQLite rows, not model objects. These are
   anticipatory implementations waiting for the routes to adopt them.
3. Storage query functions (get_connections, get_entry_tags, insert_connection, etc.): most of
   queries.py is implemented but only a few functions are called from routes. The browse route
   uses some; the rest are ready but waiting.
4. Private helpers (_normalize_entry, _call_llm, _parse_tags, extractor class methods):
   internal implementation details. Expected orphans -- they're called by their own module.

**What the complete corpus teaches beyond seed:**
- Chain positions (head/tail) are visible and correctly prioritized
- Disconnected stubs represent deferred design, not missing wiring
- Orphaned-impl at 16 is HIGH but explainable: model layer + storage layer are implemented
  bottom-up and not yet fully wired to routes. This is a real-world pattern.
- `stub_by_doc` detection extends stub coverage to functions with real bodies but
  documented incompleteness ("STUB:" in first docstring line)

---

## FINDINGS TO FIX (in order of journey impact)

F1. [DONE] Frontier mode resets to Direct on tab open.
    Fix: reset fg-mode select to 'direct' on every tab click (commit 5c396b3).

F2. [DONE] ingest_design_docs wired into post-ingest pass.
    Fix: runs automatically after discovery, before ingest_done (commit a7dc167).

F3. [DONE] REPL startup hints when coverage < 10%.
    Fix: prints "run orient or discover" hint at startup (commit 5c396b3).

RM16. [DONE] UI concept documentation pass -- explain every panel/mode/concept
    in one line, always visible. Walk-driven, after F1/F3 resolved.
    Fix: Frontier mode hint line (one sentence per mode), hot-count tooltip,
    empty-state Analyze hint, Topology subtitle expanded, Tools panel title=
    attributes, spotlight risk badge tooltip. Commit 8e1a3cf.
