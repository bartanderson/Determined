# RM17 Findings — Two-pass cold analysis of Commonplace

_Two-pass examination. Pass 1: tool output only (no source). Pass 2: adversarial source read. Compare for gaps._

---

## What Determined gets right

- Finds all 8 stubs including all 5 Direct-call frontier stubs
- ABC gap detection: `EntryProcessor` with `process` and `can_handle` unimplemented — correct
- Chain topology (chain-head / chain-middle / chain-tail) is accurate
- Entry-point finding: `capture` has 0 callers = entry point — correct
- Call edges for `_call_llm` (7 callees, correct list)
- Stub roadmap aligns exactly with the 5 stubs documented in DESIGN.md

---

## Ranked gap list

### Gap 1 — Layer-import violation detection (HIGH)

**What's missing:** The planted route-calls-storage violations are completely invisible.
`browse.py` and `capture.py` both call `storage.queries` directly, violating the
4-layer architecture rule ("routes must not import from storage/"). Determined found
0 design violations on any of these routes.

**Why the tool can't see it:** No design docs ingested (Knowledge tab = 0 artifacts).
The layer rule exists only in `DESIGN.md`. Even with docs ingested, cosine-similarity
matching of "routes must not call storage" against a `from storage import queries`
call site is unreliable — it needs a structured import-path rule type.

**How fixable:** Schema + query (medium). The import graph is already tracked.
Need: (a) `ingest_design_docs` run, (b) a new knowledge_artifact kind=`layer_rule`
with structured fields (from_layer, to_layer, direction=forbidden), (c) a query
that checks `symbol_references` against these layer rules.

---

### Gap 2 — Flask route handlers mislabeled as orphans (HIGH)

**What's missing:** 17 of the 18 "orphaned-impl" are almost certainly Flask route
handlers (functions decorated with `@blueprint.route(...)`). These have 0 corpus
callers because Flask invokes them at runtime via URL routing — not via Python calls.
The tool labels `capture()` [SAFE] with `in_degree=0` and the orphan count is noise.

**Why the tool can't see it:** `@capture_bp.route(...)` is a decorator call that
registers the function as a URL handler. The actual "caller" is the Flask WSGI
runtime, external to the corpus. Static analysis doesn't follow decorator registration.

**How fixable:** Easy heuristic. Functions decorated with `@<name>.route(...)` are
entry points, not orphans. File role=`entry_point` already exists in the schema.
A parse-time check for `@*.route(` decorators would reclassify these correctly.

---

### Gap 3 — Dead code vs "ready but blocked" (MEDIUM)

**What's missing:** `_call_llm` is ranked the #2 most-connected root symbol but is
completely unreachable — `suggest_tags()` is a stub returning `[]` without calling it.
The tool shows it with 0 callers but doesn't surface that it's a "ready implementation
waiting for its caller to be unwrapped."

**Why the tool can't see it:** Static call graph knows `_call_llm` has 0 callers.
But the relationship "this function is the intended implementation of that stub" is
expressed only in comments and DESIGN.md ("_call_llm() and _parse_tags() are already
implemented and waiting"). Deductive cross-file intent reasoning is beyond structural analysis.

**How fixable:** Medium. A semantic summary pass over the stub + nearby functions
could surface the connection. The stub roadmap in DESIGN.md explicitly names
`_call_llm` as the ready implementation — if design docs are ingested, concept_search
on "call_llm" near "suggest_tags" could surface this.

---

### Gap 4 — Role INTERFACER vs CONTROLLER for `capture` (MEDIUM)

**What's missing:** `capture()` was assigned INTERFACER (Wirfs-Brock) at 95%
confidence. It's actually a COORDINATOR/CONTROLLER — it orchestrates the entire
capture use case across validate → extract → insert → enrich → tag → redirect.
An INTERFACER is a thin boundary translator. `capture` coordinates 6+ operations.

**Why the tool can't see it:** Role inference uses call diversity heuristics.
The model sees "calls many external things including form.get and render_template"
and matches INTERFACER (crosses a system boundary). But a CONTROLLER also calls
many things — the distinguishing feature is orchestration of a use case, not just
boundary crossing. The 3B model can't distinguish these from call patterns alone.

**How fixable:** Hard. Better signal needed: INTERFACER typically has 1 input and
1 output with a format transformation; CONTROLLER has a sequence of heterogeneous
side effects. Structured role criteria in the design frame context might help.

---

### Gap 5 — Primary write path shows [SAFE] (MEDIUM)

**What's missing:** `capture()` calls `insert_entry()`, `insert_tag()` (x2 paths),
`link_tag()` (x2) — it's the entire write surface. Risk badge: [SAFE], mutations=0.

**Why the tool can't see it:** Risk scoring uses local mutation count (variable
reassignments). DB writes via function calls aren't tracked as mutations.

**How fixable:** Medium. Add "calls known storage-write functions" as a HOT signal.
Requires knowing which functions are storage writes — file role + function name
heuristics could identify `insert_*`, `update_*`, `delete_*` patterns in `storage/`.

---

### Gap 6 — Orphan list shows count, not names (LOW)

**What's missing:** Topology says "orphaned-impl: 18" but doesn't list the symbols.
Users have to navigate away to find what's orphaned.

**Why the tool can't see it:** It can. The count is already computed.

**How fixable:** Easy. Add a named list of orphaned symbols to the topology output
or link it to a filtered symbol view.

---

### Gap 7 — Inline comment design tensions invisible (MEDIUM)

**What's missing:** The source has `# DESIGN TENSION:` inline comments and `STUB:`/
`Frontier:` annotations at point-of-occurrence. These are rich design intent that
the tool never reads.

**Why the tool can't see it:** Python AST doesn't include `#` comments. Docstrings
(triple-quoted strings at function top) are extracted; inline comments are not.

**How fixable:** Medium. Raw source text scan for `# DESIGN TENSION:`, `# STUB:`,
`# Frontier:` markers during ingest. Store as knowledge_artifact kind=`inline_annotation`.
Would require source-level (not AST-level) processing.

---

### Gap 8 — `semantic_search` false positive stub (LOW)

**What's missing:** `semantic_search()` is listed as a stub. It's not — it falls back
to `search()` and returns real results. It's a "not yet enhanced" function, not a
placeholder.

**Why the tool can't see it:** Stub detection uses is_stub heuristic. `return search(query)`
looks like a passthrough body. The tool can't distinguish "deliberate fallback" from "stub."

**How fixable:** Hard. Docstring says "Falls back to text search." A semantic docstring
read could distinguish stubs from fallbacks. Or: stub = returns constant/empty;
delegating fallback = returns call result.

---

### Gap 9 — Config-gated paths invisible (LOW structural)

**What's missing:** `TAGGING_ENABLED` gates whether `suggest_tags()` is called.
The tool shows `_call_llm` as always unreachable; in practice it's conditionally
reachable.

**Why the tool can't see it:** Static analysis doesn't evaluate runtime config.
`if current_app.config.get("TAGGING_ENABLED"):` is not traceable without execution.

**How fixable:** Hard. Config-aware analysis would require either: symbolic execution,
or manual annotation of config flags as "gates."

---

### Gap 10 — Design doc auto-discovery (MEDIUM)

**What's missing:** Commonplace has a `docs/DESIGN.md` with explicit constraint rules
written FOR Determined's violation detector. But the tool can't discover and prompt
ingestion of it. Users must know to run `ingest_design_docs` manually.

**Why the tool can't see it:** `discover_docs` tool exists but isn't run at corpus load.
New users don't know to run it.

**How fixable:** Easy. Auto-run `discover_docs` on corpus load and surface "found X
markdown files with design constraints — run ingest_design_docs?" prompt.

---

## Summary

| Quadrant | Count |
|----------|-------|
| Gets right | 6 things |
| False positives | 4 (role, risk, dead-vs-blocked, stub/fallback) |
| False negatives | 5 (layer violations, orphan identity, design tensions, model layer, double-suggest) |
| Blind spots | 6 categories (routing, layer rules, config gates, comments, templates, model adoption) |

**Root cause of most gaps:** No design docs ingested = no rule context. The corpus
was explicitly designed to exercise violation detection, but violation detection requires
`ingest_design_docs` to run first. Auto-discovery of design docs on corpus load would
unlock gaps 1, 3, and 10 in a single change.

**Second root cause:** Flask route decorator pattern causes ~17 false orphans, making
the orphan count meaningless for this corpus type. A route-decorator heuristic fixes this.
