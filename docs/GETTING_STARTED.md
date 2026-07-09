Determined — Getting Started
============================

This document walks you through a small Python web application called Commonplace — a personal knowledge base for saving and searching web content. You will watch it grow from a skeleton to a complete application to an enhanced one, and at each stage Determined will show you what the codebase looks like from the inside.

The point is not to learn Commonplace. The point is to learn what Determined shows you when a codebase is incomplete, when it is wired up, and when it has been extended — so that when you point Determined at your own project, you recognize what you are looking at.

If you haven't set up Determined yet, start with `SETUP.md`.

---

## Loading the skeleton

The skeleton is a 17-file Python web application with all its pieces in place but not yet fully connected. Load it now so you can follow along.

In the Determined UI:

1. Click the 🗄 icon in the left rail to open the corpus panel
2. Click Re-analyze
3. Browse to `examples/commonplace/seed` inside the Determined folder and select it
4. Click Analyze ↵

When it loads you will see this in the corpus panel:

```
17 files · 0 hot · 0 stubs

Roots
  capture          ↗13
  validate_entry   ↗6
  index            ↗2
  EntryProcessor   ↗0
  EnrichmentProcessor ↗0
Gaps
  docs 71%   distilled 0%   0 design notes   C: 71% (9 missing)
```

---

## The corpus panel: what the call graph looks like from the outside

The corpus panel is a dashboard, not a report. It doesn't tell you everything — it tells you enough to know what kind of problem you're looking at before you dig in.

**17 files · 0 hot · 0 stubs**

The important one is stubs. A stub is a function that exists but does nothing — a `pass` or `raise NotImplementedError` where an implementation should be. Zero stubs means every function in this codebase has a real body. That's the first thing to check: is anything obviously broken?

Hot files are the second thing. A file becomes hot when enough other files import it that it becomes a single point of failure — change it and you break everything that depends on it. At 17 files there isn't enough coupling to flag one. You'll see this change as the codebase grows.

**Roots** are where the call graph starts: functions or classes that nothing else calls. They're how the outside world enters the application.

`capture ↗13` makes 13 outbound calls — that's the main entry point, where most of the application's work happens. `index ↗2` is the home page route. `EntryProcessor` and `EnrichmentProcessor` are abstract base classes. An ABC doesn't get called directly — subclasses implement it and get called instead. Determined surfaces ABCs as roots because they're the top of a class hierarchy, not because they're called by anything.

Here's what the call graph can't tell you from just the headline numbers: it can tell you what's broken, but not what's unconnected. Zero stubs means nothing is broken. It says nothing about whether all the implemented code is actually being used. That's a different question — the Frontier tab answers it.

---

## The Frontier tab: three ways a codebase can have gaps

The **Frontier** tab is where Determined earns its keep. It asks three distinct questions about structural gaps. Each mode is looking for a different kind of problem.

### Direct mode: is anything broken right now?

The dropdown shows **Direct (caller→stub)**. This mode traces every call edge in the graph and asks: does the callee exist and have a real implementation? If working code is calling a stub, there's a broken execution path — something real is waiting on something that does nothing.

Result: **No frontier edges found.**

The skeleton has no broken call edges. Every function that gets called has a real body. This is the most urgent category — if anything were here, you'd fix it before doing anything else.

### Orphan mode: is anything implemented but unreachable?

Change the dropdown to **Orphan**. Result:

```
[Orphan] 1 anticipatory · 0 stranded · 1 total
```

`validate_entry` appears as a blue circle.

This is the gap the corpus panel missed. `validate_entry` is fully implemented — it has a real body, it's not a stub — but nothing in the codebase calls it. The call graph is built from actual import and call relationships. If nothing imports or calls a function, it's an island. Determined doesn't guess at intent; it reads what the code actually does.

Disconnected functions fall into two categories based on what Determined can infer about them:

- **Anticipatory** — implemented, ready to use, written ahead of its callers. Not a bug. Work waiting to be connected.
- **Stranded** — no callers, and no obvious path to ever having one. More suspicious; worth investigating.

`validate_entry` is anticipatory: it validates an entry before saving it, and the route that captures entries was written without calling it yet. The skeleton has the validator ready. The wiring hasn't happened. That's the kind of thing Determined is built to surface — not because the code is wrong, but because the graph is incomplete.

### ABC mode: did anyone forget to implement an interface?

Change the dropdown to **ABC**. This mode checks whether every abstract method on every base class has at least one concrete override somewhere in the corpus. An abstract method with no concrete override is a promise the codebase made and didn't keep.

Result: **No frontier edges found.**

Both ABCs — `EntryProcessor` and `EnrichmentProcessor` — have all their abstract methods overridden by concrete subclasses. No gaps.

This mode is quiet now, but it pays off when the codebase grows. Add a new abstract method to a base class, forget to implement it in one of the subclasses, and ABC mode flags it immediately. The check is a graph query, not a linter — it looks at what's actually defined across the whole corpus, not just whether the syntax is correct.

---

## The Topology tab: the same picture, all at once

You've now seen the three kinds of structural gaps Frontier can find. The **Topology** tab puts all of them in a single view and derives an action queue from the results.

```
CORPUS TOPOLOGY
  Total stubs: 0  |  Total implemented: 31

  Shape                  Count  Description
  ──────────────────────────────────────────────────────────────
  Direct-call                0  stubs called by functional code
  ABC-interface              0  abstract methods with no concrete override
  Chain-head                 0  stubs: functional callers + stub callees [bridge]
  Chain-middle               0  stubs: stub callers + stub callees [blocked]
  Chain-tail                 0  stubs: stub callers only [implement first]
  Orphaned-impl              2  implementations with no functional callers
  Entry-point                0  stubs in route/handler/cli files [external trigger]
  Disconnected               0  stubs with no graph connections

  Action queues:
    Implement now:  chain-tail (0) > direct-call (0) > abc-interface (0) > chain-head (0)
    Write callers:  orphaned-impl (2)
    Decide:         disconnected (0) | entry-point (0)
```

The "Implement now" queue is empty — nothing broken. The one non-zero entry is **Orphaned-impl: 2**: `validate_entry` and `create_app`, both placed in "Write callers."

`create_app` will always show up here on a Flask project. Flask factories are called by the WSGI server at runtime — there's no in-corpus call to find. Static analysis can't see runtime wiring. This is a structural blind spot in the tool, not a gap in your code. You'll learn to recognize it.

`validate_entry` is the real item. It belongs in the queue.

The priority order in "Implement now" — chain-tail before direct-call before abc-interface before chain-head — reflects execution risk. Chain-tail stubs block the end of a call chain, meaning the chain-head function succeeds but silently returns nothing useful. Direct-call stubs blow up immediately. The ordering tells you what breaks first, not what's easiest to fix.

The topology view becomes most useful once stubs exist. For the skeleton, it confirms what the Frontier modes already told you: 0 stubs, one genuine wiring gap, one known false positive.

---

## The Call tree tab: understanding a specific function

Everything so far has been about structural state — what's broken, what's unconnected. The **Call tree** tab is different: it's a navigation tool. You already know what to look at from Topology and Frontier. Call tree is for understanding how it connects.

Type `capture` and its callees appear:

```
capture
  validate_url
  services.extractor.extract
  run_processors
  services.pipeline.enrich_entry
  storage.queries.insert_entry
  ...
```

A URL comes in, gets validated, extracted, run through processors, enriched, stored. That sequence is the application's main path. The call tree makes it navigable — click any node to trace deeper.

Notice what's not here: `validate_entry`. It's implemented, it would fit logically after `validate_url`, but it's not in the tree because nothing calls it. The call tree shows you what the code actually does. Frontier shows you what it doesn't do yet.

---

## The skeleton's structure

The 17 files follow a layered architecture that's worth knowing before Phase 2, because Determined's numbers reflect it directly:

```
routes/       — HTTP entry points (capture.py, search.py, index.py)
services/     — Business logic (extractor.py, pipeline.py, tagger.py, searcher.py, linker.py)
storage/      — Data layer (db.py, queries.py, models.py)
processors/   — ABC subclasses (cleanup.py, deduplicate.py, enrichment.py)
utils/        — Shared helpers (text.py, url.py)
app.py        — Flask factory
config.py     — Configuration
```

Routes are thin — they receive a request and hand off immediately to a service. Services hold the decisions. Storage is called by services only, never by routes directly. This is why `capture` has 13 outbound calls and why the storage layer is on its way to becoming the hotspot. When you see a function with 10+ outbound calls in your own project, it's either your main entry point or a place where too many concerns are mixing. The call count is a signal.

---

## Phase 2: adding layers and reading the gaps

The skeleton is a starting point. It has structure and intent baked in — you can read the designer's decisions from the call graph. Now we add to it and watch what Determined surfaces as the codebase grows.

This is the real use case: you didn't write this code, or you wrote it six months ago. You're using Determined to figure out what it was trying to become. Each layer you add — or encounter on a real project — shifts the picture. The gaps between what exists and what's connected are where the intent lives.

### Adding the data models

The first addition is a `models/` layer: `Entry`, `Connection`, and `Tag` — dataclasses that represent the application's core objects. Load them and re-analyze (`Frontier → Orphan`):

```
[Orphan] 3 anticipatory · 0 stranded · 3 total

  validate_entry   (blue)
  validate         (blue)
  to_dict          (blue)
```

We had one anticipatory orphan before. Now we have three. `validate_entry` is still there. The two new ones — `validate` and `to_dict` — come from the model classes.

`Entry.validate()` checks that the entry's type is valid and the content is non-empty before saving. `Entry.to_dict()` serializes an entry to a plain dict for JSON responses. Both are fully implemented and ready to use. Neither is called by anything.

This tells you something about how the skeleton was built: the routes and services were written before the model layer existed. They pass raw dicts around rather than `Entry` objects. The models came later and haven't been threaded through yet. Determined didn't tell you the code is wrong — it told you where the design got ahead of the wiring.

On a real project, this pattern is common. You see a utility method or a model method sitting in Frontier Orphan, and the question isn't "is this broken?" It's "was this the direction the codebase was heading?" Sometimes yes — it's anticipatory work waiting to be connected. Sometimes no — it's a design that was abandoned without being deleted.

### Adding the routes

The next addition is two new route files: `routes/api.py` (a JSON API) and `routes/browse.py` (HTML browsing). After re-analyzing (`Frontier → Orphan`):

```
[Orphan] 3 anticipatory · 0 stranded · 3 total
```

The orphan count didn't change — but the corpus panel did:

```
23 files · 1 hot · 0 stubs

Roots
  capture       ↗13
  entry_detail  ↗6
  validate_entry ↗6
  index         ↗3
  ...
```

Two things happened. First, `entry_detail` is now a root — it's a new route with 6 outbound calls, an entry point the web server will call at runtime. Second, `index` went from `↗2` to `↗3` — `browse.py` adds another index route that also calls into storage.

Also notice: **0 stubs, still**. The new routes call storage functions that don't exist yet in `queries.py` — `get_entry`, `get_entry_tags`, `get_connections`, `list_entries`. But those functions were never written at all, not even as placeholders. Determined finds stubs — functions that exist but do nothing. It cannot find missing symbols — functions that are called but were never written. That's what a type checker catches.

This is an important boundary to know. Determined tells you about the shape of what exists. For what's absent entirely, you need runtime errors or static type analysis. The two tools answer different questions.
