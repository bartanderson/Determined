Commonplace — Design Vision and Current Status
===============================================

_Written 2026-07-04. Authoritative intent for the Commonplace sample program
and its role in the Determined guided-journey UI._

---

## Purpose

Commonplace is not a test fixture. It is the vehicle for demonstrating and
teaching Determined. It exists in two roles simultaneously:

1. **Canonical demonstration corpus** — a real Python project with enough
   structure (stubs, design tensions, topology variety, layering) to exercise
   every Determined capability meaningfully.

2. **Guided journey vehicle** — the project a new user builds, step by step,
   using Determined's tools. By the end they have a working program and a
   working understanding of the tool. The learning came from doing.

These two roles are coupled by design: when a new Determined feature lands,
Commonplace gets a corresponding structure that exercises it, and the guided
path gains a step. The two evolve together.

**Out of scope:** using Determined on Determined itself as the demonstration
corpus. That's circular, hard to control, and confusing to new users. Commonplace
gives us full control over what the corpus contains and when.

---

## The guided journey model

### Seed and complete

Commonplace exists in two states:

- **Seed** — the tiny shell a new user starts with. Deliberate stubs, gaps,
  and design tensions are present from the beginning, staged to reveal
  progressively as the user works through the guide.

- **Complete** — the fuller working application. The user arrives here by
  following the guide and making the implementation decisions Determined
  surfaces along the way.

The guide walks the user from seed to complete. The stubs are not bugs —
they are the curriculum.

### Highlighted controls

The guided path is expressed through the Determined UI itself, not a
separate tutorial layer:

- Controls relevant to the current step are **highlighted in color**
- Hovering a highlighted control shows a **pedagogical tooltip**: what this
  control shows you, why it matters here, what the data is telling you,
  and what comes next
- The path may be non-linear — multiple valid next steps can be lit
  simultaneously, each tooltip explaining what that branch explores
- The highlights live on the real controls; there is no "tutorial mode"
  that bypasses normal use

This is the GOT navigation model made explicit and teachable. The user
learns the surfaces by using them on a real problem, not by reading docs.

### What the journey teaches

Each step connects data to decision:

1. **Orient** — corpus map, gap summary, hot/warm/safe distribution.
   "Here is what this project is. Here is where the risk lives."

2. **Frontier** — stub list, chain topology, ABC gaps.
   "Here is what is unimplemented. Here is which stub blocks the most."

3. **Understand a stub** — symbol context, design frame, callers.
   "Here is everything known about this symbol. Here is why it matters."

4. **Reason about implementation** — stub scorer, evaluate_claim, waypoints.
   "Here is what implementing this stub requires. Here is the tradeoff."

5. **Design tensions** — check_design_violations, design frame comparison.
   "Here is a place where the code and the design intent diverge."

6. **Plan** — frontier priority, workflow queue, build queue tab.
   "Here is the recommended order. Here is what unblocks what."

7. **Implement and re-ingest** — reingest_file, topology drift.
   "You changed something. Here is what moved."

---

## Current Commonplace design status

### What is implemented (as of 2026-07-04)

**Working application skeleton:**
- `app.py` — Flask factory, all blueprints registered
- `storage/db.py` — SQLite init, schema (entries, tags, entry_tags, connections)
- `storage/queries.py` — CRUD for entries, tags, connections (fully implemented)
- `services/extractor.py` — `extract_metadata()` working; `extract_full_content()` stub
- `services/searcher.py` — `search()` working (SQL LIKE); `semantic_search()` stub
- `routes/capture.py` — URL and note capture, tag wiring, config flag for LLM tagging
- `utils/text.py`, `utils/url.py` — supporting utilities

**Deliberate stubs (the curriculum):**
- `extractor.extract_full_content()` — readable text extraction not implemented
- `searcher.semantic_search()` — falls back to text search; embedding not wired
- `linker.find_connections()` — always returns []; similarity inference not implemented
- `linker._similarity_score()` — always returns 0.0
- `tagger.suggest_tags()` — always returns []; LLM endpoint not wired
- `tagger._call_llm()` / `_parse_tags()` — implemented but never called

**Deliberate design tensions (the reasoning prompts):**
- `extractor.py` docstring: three responsibilities in one module (fetch + parse + extract)
- `searcher.py` docstring: calls storage directly, bypasses service layer boundary
- `queries.py` comment: `search_entries` called from both service and storage layers
- `routes/capture.py` comment: URL validation duplicated between route and utils
- `tagger.py` docstring: eager-on-capture vs lazy-on-view open question

### What is missing from Commonplace

**Seed/complete staging not yet defined:**
- There is no documented seed state (which files exist, which are absent)
- The progression from seed to complete has not been designed
- The stubs exist but their order of introduction is not planned

**Design doc is incomplete:**
- `docs/design.html` exists but its content and authority are unknown
- No markdown design doc with invariants, authority rules, or layer boundaries
  that Determined's `ingest_design_docs` and `check_design_violations` can mine

**ABC pattern not represented:**
- No abstract base class with unimplemented methods
- Needed to exercise `find_abc_gaps()` and the ABC frontier UI mode

**Topology variety is limited:**
- Current stubs are mostly leaf stubs (chain-tail)
- No chain-middle or chain-head examples
- No entry-point topology examples (routes register correctly but not documented
  as entry points for Determined's topology detection)

**Conditional stub not represented:**
- No `raise NotImplementedError` inside an if/elif branch
- Needed to exercise `find_conditional_stubs()`

**LLM integration path not documented:**
- `tagger` and `semantic_search` need an endpoint — should point at
  llama-server on port 8081 for consistency with Determined's own LLM setup
- No config or README explaining how to wire this

**Guided journey not built:**
- The UI highlighting and hover-tooltip system does not exist yet
- The step sequence has not been authored
- The pedagogical content (what and why) has not been written

---

## Next steps — in order

### 1. Design doc for Commonplace itself

Write `examples/commonplace/docs/DESIGN.md` (markdown, not HTML) with:
- The application's intended architecture (capture service → storage → search → link)
- Authority rules: "only storage layer touches the DB directly"
- Invariants: "tags are always lowercase", "connections are bidirectional"
- Open questions: the design tensions already in code comments, promoted to doc

This makes `ingest_design_docs` and `check_design_violations` exercisable
on Commonplace's own codebase.

### 2. Add missing topology shapes

Add to Commonplace:
- An ABC with at least one abstract method and no override (exercises `find_abc_gaps`)
- A chain-middle stub (called by another stub, calls another stub)
- A conditional stub (`raise NotImplementedError` inside an if branch)

### 3. Define the seed state

Document and commit a `seed/` snapshot of Commonplace — the minimal starting
point for the guided journey. The seed has:
- `app.py`, `config.py`, `storage/db.py` with schema
- Route stubs (registered but body is NotImplementedError)
- Service stubs (all methods stub)
- No utils, no extractor, no tagger

The complete version is `examples/commonplace/` as it exists. The guide
takes the user from seed to complete.

### 4. Guided UI — highlighting and tooltips

In the Determined UI, add:
- A `data-guide-step` attribute system on navigable controls
- A guide stylesheet: highlighted controls get a colored ring + cursor affordance
- A hover tooltip component that reads step content from a guide definition file
- A guide definition file: JSON or markdown mapping step names to (control, what, why, next)

The guide is off by default, activated by loading a guide-enabled corpus
(Commonplace with a `guide.json` at its root).

### 5. Author the journey steps

Write the step sequence: what the user does at each step, which controls
light up, what the tooltip says, what decision they make, what changes in
the corpus as a result.

---

## Relationship to UI_VISION.md

`docs/UI_VISION.md` describes the GOT navigation model — surfaces presenting
themselves, editor as nav hub, structured panels over prose. The guided
journey described here is that model made pedagogically explicit: the same
surfaces, the same controls, but with highlighted paths and contextual
explanations that teach the user what they are doing and why.

The two documents are complementary. UI_VISION describes the target UI.
This document describes how Commonplace and the guided journey validate and
demonstrate it.
