Commonplace -- Design Vision and Build Model
=============================================

_Written 2026-07-04. Authoritative intent for the Commonplace sample program
and its role in the Determined guided-journey UI._

---

## The actual work arc (read this first)

This is the next active development work for Determined. The goal is to run
the journey for real -- use Determined to build and navigate Commonplace --
and fix the tool iteratively wherever the experience breaks down. Commonplace
and Determined improve together through actually doing the thing.

**Two entry paths, same destination:**

- **Easy path (intro):** Start with the seed skeleton already in hand. Use
  Determined to understand it, fill out the stubs, and navigate to complete.
  Good for getting familiar with the tool quickly.

- **Hardcore path (full):** Build the seed from scratch, file by file, with
  Determined open. Ingest as you go. The write-reingest-read-frontier loop
  IS the development workflow. This is the real introduction to the tool.

Both paths converge at the seed, then continue: seed -> complete -> enhance.

**How to do this work:**
Start the server. Point Determined at the seed (or a blank directory for the
hardcore path). Walk the journey steps. When something breaks or feels rough,
fix Determined. Continue. This is not a one-shot audit -- it is iterative.
The journey writes itself from what the tool actually does.

**What "enhance" means:**
After reaching complete, add one or two features (tagger wired to llama-server,
semantic search, connection inference) using Determined to navigate a codebase
the user now understands. This demonstrates Determined's value on an actively
evolving project, not just a static corpus.

---

## Purpose

Commonplace is not a test fixture. It is the vehicle for demonstrating and
teaching Determined. It exists in two roles simultaneously:

1. **Canonical demonstration corpus** -- a real Python project with enough
   structure (stubs, design tensions, topology variety, layering) to exercise
   every Determined capability meaningfully.

2. **Guided journey vehicle** -- the project a user builds, step by step,
   using Determined's tools as navigation. By the end they have a working
   program and a working understanding of the tool. The learning came from doing.

These two roles are coupled by design: when a new Determined feature lands,
Commonplace gets a corresponding structure that exercises it. The two evolve
together.

**Out of scope:** using Determined on Determined itself as the demonstration
corpus. That's circular, hard to control, and confusing to new users. Commonplace
gives us full control over what the corpus contains and when.

---

## The three-phase build model

Commonplace is designed around three distinct states. The user travels through
all three using Determined as their guide.

### Phase 0 -- Scratch

A completely blank directory. No files. No DB. The user has Determined open
and starts writing software from nothing.

The scratch-to-seed arc teaches:
- How to create a project and ingest it for the first time
- What Determined's first read looks like (sparse, entry-point focused)
- How write-then-reingest works as a development loop

The key tool here is the write-then-reingest cycle:
  edit_file (write) → reingest_file → frontier changes → decide what to write next

This arc demonstrates edit_file and reingest_file working together -- the
read-reason-write loop closed at the file level.

### Phase 1 -- Seed

The minimum viable corpus: enough structure for Determined to give a
meaningful first read. Written top-down (route first, stubs below) so the
first ingest is clean: one entry point, 2-3 direct-call stubs, near-zero
orphaned implementations.

The seed lives in `examples/commonplace/seed/`. It is a standalone runnable
project -- not a diff, not a partial checkout. A user can copy it, ingest it,
and start working immediately.

The first ingest of the seed should produce:
- 1 entry point (the capture route)
- 2 direct-call stubs (extractor functions called by the route)
- 1 disconnected stub (init_db -- storage not yet wired into the route)
- 0 ABC gaps, 0 chain shapes, 0 conditional stubs
- frontier_priority clearly points at the extractor stubs

This is the lesson: Determined shows you exactly where the edges of the
working system are. The stubs are the frontier. Implement them in priority order.

### Phase 2 -- Complete

The full Commonplace application as it exists in `examples/commonplace/`. The
user arrives here by working through the seed, making implementation decisions
Determined surfaces along the way.

The complete state has (design target -- current examples/commonplace is at partial state):
- 8 stubs across multiple topology shapes (direct-call, chain-head, chain-tail,
  ABC-interface, conditional) [current: 1 is_stub + 1 conditional; ABC/chain shapes not yet added]
- Design tensions documented and detectable via check_design_violations
  [requires ingest_design_docs first; examples/commonplace/docs/DESIGN.md must exist]
- Full layering (routes / services / storage / utils) with known violations
- All Determined frontier features exercised

The journey from seed to complete teaches:
- frontier_priority and detect_topology for implementation ordering
- symbol_context and score_stub for understanding individual stubs
- check_design_violations for design intent cross-reference
- reingest_file for watching the frontier move after each change
- reason_about for architectural decisions (extractor split? eager vs lazy tagging?)

### Phase 3 -- Extras

Optional extensions beyond complete. These are features the user can add
after finishing the guided journey, using Determined on a codebase they
now understand. They demonstrate Determined's value on a non-trivial,
actively-evolving project.

Candidate extras (not yet built):
- LLM tagging wired live (suggest_tags connected to llama-server port 8081)
- Semantic search live (semantic_search using sentence-transformers or llama-server embeddings)
- Connection inference live (_similarity_score + find_connections implemented)
- EnrichmentProcessor override (closes the ABC gap)
- Strict validation mode (implements the conditional stub in validate_entry)

Each extra is a natural next step that Determined surfaces on its own --
the user doesn't need the guide anymore at this point. The tool has become
their navigation layer.

---

## Seed state specification

### Files

```
seed/
  app.py              Flask factory. Registers capture blueprint. Calls init_db().
  config.py           DATABASE path, DEBUG flag, TAGGING_ENABLED = False.
  routes/
    __init__.py
    capture.py        GET: render form. POST: validate url, call extractor.extract()
                      (stub), store result. Two stubs are the direct-call frontier.
  services/
    __init__.py
    extractor.py      extract_metadata() -- STUB. extract_full_content() -- STUB.
                      Module docstring notes the three-responsibility tension.
  storage/
    __init__.py
    db.py             init_db() creates entries table. get_db() returns connection.
                      No queries yet -- insert_entry does not exist at seed.
```

### What Determined sees at seed (first ingest)

```
CORPUS TOPOLOGY
  Total stubs: 3  |  Total implemented: 6

  Shape          Count
  Direct-call    2     extractor.extract_metadata, extractor.extract_full_content
  Disconnected   1     storage.db.init_db (not yet called from route)
  Orphaned-impl  0

  frontier_priority: extract_metadata > extract_full_content
```

The first read is unambiguous: implement the extractor stubs. Everything else
is either working (Flask wiring, route handler structure) or not yet needed
(storage queries don't exist until the extractor returns real data to store).

### Why top-down matters for the seed

If the seed were built bottom-up (storage first, then services, then routes),
the first ingest would show storage functions as orphaned -- working code with
no callers. "Write callers for these 6 functions" is noise, not a lesson.

Top-down means the route exists first and its downstream dependencies are stubs.
The frontier is at the bottom, not in the middle. Determined's output reads
from the entry point down to the gap, which matches how a developer thinks
about a feature: "what does this route need that doesn't exist yet?"

---

## The guided journey steps (seed to complete)

Each step: user reads Determined output, makes a decision, writes code,
re-ingests, reads again. The tool drives the order.

**Step 1 -- Orient**
Load seed corpus. Run knowledge_status and detect_topology.
(corpus_status does not exist; knowledge_status is the equivalent.)
Lesson: entry point + direct-call frontier. "Here is what exists. Here is
where it stops."

**Step 2 -- Implement the first stub**
frontier_priority points at extract_metadata. Run symbol_context on it.
Run score_stub to understand what implementing it requires (urllib, HTML parsing).
Implement it. Re-ingest. Watch direct-call count drop, orphaned-impl possibly rise
(storage queries still missing).

**Step 3 -- Add storage**
The extractor now returns data but nothing stores it. Add queries.insert_entry.
Re-ingest. The route now has a path to completion. Watch orphaned-impl drop.

**Step 4 -- Design decision**
run check_design_violations on extractor.py. It surfaces the three-responsibility
tension from the DESIGN.md rules. Run reason_about: "should extractor be split
into fetcher + parser + extractor?"
Lesson: Determined surfaces design questions, not just structural gaps.

**Step 5 -- Expand the frontier**
Add search, tagging, linking as stubs. Re-ingest. Topology grows:
chain-head appears (pipeline.enrich_entry), ABC gap appears (EntryProcessor).
frontier_priority reorders.

**Step 6 -- Work the topology**
find_abc_gaps, find_conditional_stubs, detect_topology chain shapes.
Each shape has a different priority and a different implementation story.
Lesson: not all stubs are equal. Position in the chain determines urgency.

**Step 7 -- Implement and close**
User picks remaining stubs in priority order, implements each, re-ingests.
Frontier shrinks to zero. The corpus is complete.

---

## Guided UI (future -- Phase 4)

The guided path is expressed through the Determined UI itself, not a
separate tutorial layer:

- Controls relevant to the current step are highlighted in color
- Hovering a highlighted control shows a pedagogical tooltip: what this
  control shows you, why it matters here, what to do next
- Multiple valid next steps can be lit simultaneously
- The highlights live on the real controls; there is no "tutorial mode"

The step sequence above maps to specific Determined controls. Each step
lights up 1-2 controls with a tooltip explaining what they show and why.

This is not built yet. It requires the step sequence to be validated
against real tool output first -- the journey writes itself from what
the tool actually does, not from what we hoped it would do.

---

## Relationship to other docs

- `docs/UI_VISION.md` -- the GOT navigation model that the guided journey demonstrates
- `examples/commonplace/docs/DESIGN.md` -- design rules for Commonplace itself,
  ingested via ingest_design_docs, checked via check_design_violations
- `docs/TRACKER.md` -- open items for Determined features that Commonplace exercises
