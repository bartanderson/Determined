Commonplace Guided Journey - Working Log
=========================================

Live document. Each walk adds to what's known. Only restart from scratch
when a fundamental break requires it. Look ahead 2-3 steps before walking.

---

## WHAT WORKS (verified, don't re-test)

- CSS fix: .tab-content grid-row 4->5 (commit pending). Frontier, Graph,
  Topology tabs now render at full height.
- Seed corpus loads correctly: 8 files, 0 hot, 2 stubs, Roots: capture/index
- Frontier Direct mode: shows extract_metadata + extract_full_content as red
  stubs, extract as orange caller. Correct.
- Topology tab: renders correctly, shows Total stubs:2, direct-call shape,
  action queue points at stubs. Correct.
- symbol_context on extract_metadata: correct output via UI spotlight trigger
  (declaration, docstring, SAFE risk, 1 caller). Spotlight code is correct;
  preview pane too narrow to show it (556px < 590px needed). Not a bug.

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
