# RM15 Findings -- Commonplace Guided Journey

_Iterative seed-to-complete run. Started from a 5-file skeleton, used Determined's
topology tools to drive implementation order. Sessions 103-104 (2026-07-06/07)._

---

## What the journey proved

**Topology-driven development works.** Starting from a seed with 10 stubs and running
`detect_topology` at each step gave a clear, mechanically-derived implementation queue.
The tool told us what to build first without requiring us to read the code.

**Implementation order matched reason_about (95% confidence):** chain-tail first
(`find_connections`, `suggest_tags`), then direct-call, then chain-head (`enrich_entry`).
The dependency chain resolved in exactly the predicted order.

**Stub count arc:**
- Step 4 (seed baseline): 2 stubs, 6 implemented
- Step 5 (stubs added): 10 stubs, 16 implemented -- chain-head + ABC gap visible
- Step 7 (chain-tail impl): 7 stubs, 19 implemented -- chain collapses, disconnected gone
- Step 8 (direct-call impl): 2 stubs, 27 implemented -- frontier flat
- Step 9 (ABC fix): 0 gaps reported -- corpus complete

---

## Tool findings: what Determined got right

- **detect_topology** correctly identified chain-tail/head/middle at each step
- **find_abc_gaps** detected `EntryProcessor` gap immediately after ABC stubs were added
- **find_conditional_stubs** returned clean (no false positives)
- **reason_about** gave correct implementation order with correct confidence (95%)
- **check_design_violations** surfaced the extractor tension (score 0.43) -- correct hit
- **reingest_file** tracked stub->implemented transitions accurately after each edit
- **Graph edges** used qualified-name suffix matching correctly (`services.tagger.suggest_tags`)

---

## Tool findings: bugs and blind spots found

### Bug 1 -- find_abc_gaps same-file blind spot (FIXED this session)

**What:** `find_abc_gaps` and `_get_abc_gap_set` both used `file_path != ?` to find
overrides, so subclasses defined in the same file as their ABC base were invisible.
`EnrichmentProcessor.process` and `can_handle` in `processor.py` were not detected as
overrides of `EntryProcessor`'s abstract stubs (same file).

**Fix:** Removed `file_path != ?` constraint. Now checks for any `is_stub=0` function
with the same name, regardless of file. Both `_get_abc_gap_set` and `find_abc_gaps` fixed.

**Signal:** The tool reported `ABC-interface: 2` even after concrete overrides existed,
which would mislead a real user into thinking the interface was still unimplemented.

### Bug 2 -- ingest_design_docs project-root mismatch (known, unfixed)

`ingest_design_docs` uses `oracle.get_project_root()` which returns the ingested corpus
root. For the seed corpus (`seed/`), DESIGN.md lives at `examples/commonplace/docs/` --
outside the ingest root. Workaround: call `discover_docs` + `extract_rules` directly
with the correct path. Fix: add explicit `path` arg to `ingest_design_docs`.

### Blind spot 1 -- `semantic_search` detected as stub despite being functional

`semantic_search` was marked `is_stub=1` because its docstring said "STUB" and its
body delegated to `search()` (looked like a fallback/placeholder). The tool cannot
distinguish "this is a stub waiting for embedding support" from "this is a working
fallback." Both have real bodies; only the docstring signals intent. The tool is correct
by its heuristic; the heuristic has limits at the boundary of aspirational vs. functional.

### Blind spot 2 -- orphaned-impl includes Flask route handlers

`capture`, `index`, `create_app`, `get_db`, `init_db` all appear as orphaned-impl
(no corpus callers). These are entry points triggered externally (HTTP, app startup) --
not actually orphaned. The tool correctly flags them for the developer to decide, but
the decision is always "these are fine, they're entry points." A Flask `@route` decorator
heuristic (already filed as RM17 Gap 2) would clean this up.

---

## Determined improvement candidates surfaced

1. **`ingest_design_docs` explicit path arg** -- low effort, high value. Without it,
   any corpus where design docs live outside the ingest root requires manual workaround.

2. **Flask @route decorator = entry point** -- route handlers should be classified as
   Entry-point, not Orphaned-impl. Already filed as RM17 Gap 2.

3. **Stub detection: "STUB" docstring vs. functional fallback** -- `semantic_search`
   was functional but flagged as stub. Consider: if the body contains a real return
   (not `return []`, `pass`, `raise NotImplementedError`), downgrade stub confidence.

---

## Corpus state at journey end

- 16 files ingested
- 0 stubs (2 abstract base method stubs remain in DB but 0 ABC gaps reported)
- 27 implemented functions
- Flat frontier -- no chains, no disconnected, no ABC gaps
- capture -> run_processors -> enrich_entry -> insert_entry pipeline fully wired
