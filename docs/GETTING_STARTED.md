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

### Adding utils

The last addition is two utility files: `utils/text.py` (truncate, clean, make_excerpt) and `utils/url.py` (normalize, validate_url). After re-analyzing, Frontier → Orphan shows:

```
[Orphan] 5 anticipatory · 0 stranded · 5 total

  validate_entry   (blue)
  make_excerpt     (blue)
  normalize        (blue)
  validate         (blue)
  to_dict          (blue)
```

Five orphans. Three are new: `make_excerpt`, `normalize`, and two from the models layer that were already there. All anticipatory — fully implemented, not yet wired.

Now look at what's missing: `validate_url` from `utils/url.py`. It should be here. It has no callers. But it doesn't appear.

Here's why: `utils/validator.py` also has a `validate_url` — written earlier, and it *is* called by `validate_entry`. Determined builds its graph on function names. When it looks up `validate_url` to check for callers, it finds one — the caller of the *other* `validate_url`. The duplicate in `url.py` inherits that caller and disappears from the orphan list.

Two functions with the same name, in different files. One is used. One is dead. Determined can't tell them apart, so the dead one hides behind the live one.

This is a real gap in the tool. On a project you didn't write, you'd see five orphans and think the utils layer is cleanly structured. You wouldn't know a duplicate exists unless you searched for it manually. The orphan view only surfaces what has no callers *by name* — not what has no callers *by identity*.

The lesson for your own project: when Orphan mode shows fewer items than you expected from a new module, check for name collisions. If a function seems like it should be orphaned but isn't, another function with the same name may be pulling it out of the list.

---

## Phase 3: the complete corpus

So far you've watched the skeleton grow — models, routes, utils added one layer at a time. Now load the complete Commonplace application and see what Determined shows when everything is wired up.

In the corpus panel, click **Re-analyze** and point it at `examples/commonplace` (not `seed` — the parent directory). This is the full application.

Switch to **Frontier → Orphan**:

```
[Orphan] 12 anticipatory · 0 stranded · 12 total
```

Twelve orphans on a complete, working application. That's not a problem — it's information. Utility helpers not yet called from routes, model methods the services haven't adopted yet, parser callbacks the main path doesn't reach directly. All anticipatory. All implemented. None broken.

On a working application, orphan mode stops being a bug-finder and becomes a design-reader. These 12 functions tell you where the application has headroom — what it was built to support that isn't fully threaded through yet. If you were extending this application, the orphan list is where you'd start: code written in anticipation of features that haven't landed.

Switch to **Topology**:

```
CORPUS TOPOLOGY
  Total stubs: 1  |  Total implemented: 60

  Shape                  Count  Description
  ──────────────────────────────────────────────────────────────
  Direct-call                1  stubs called by functional code
  ABC-interface              0  abstract methods with no concrete override
  Orphaned-impl             15  implementations with no functional callers
  ...

  Action queues:
    Implement now:  chain-tail (0) > direct-call (1) > abc-interface (0) > chain-head (0)
    Write callers:  orphaned-impl (15)
    Decide:         disconnected (0) | entry-point (0)

Signal: LOW stub pressure — most implemented code is reachable.
```

The "Implement now" queue is not quite empty — direct-call (1) is there. One stub somewhere in the complete corpus is being called by working code. That's a real item. The pressure is LOW, not zero.

This is closer to reality than "done" usually looks. A working application often has one unfinished corner — something planned, partially wired, not yet implemented. Determined found it without being asked. The rest of the picture is clean: 15 orphans all anticipatory, no ABC gaps, 60 implemented functions reachable through the graph.

This is the contrast the walk was building toward. The skeleton had pressure — multiple action queue entries, direct-call stubs, orphaned work. The complete application has almost none. The tool didn't tell you the application is finished. It told you where the remaining pressure is, and how small it is.

When you point Determined at your own project, this is the reference frame. Not "how many stubs" but "where is the pressure." A high direct-call count means broken paths. A full orphan list means unconnected work. A nearly-empty topology means you're building forward, not catching up.

---

## What to do next

You've seen Determined on three corpus states — skeleton, growing, complete. You know what each panel is for and what it can and can't see. Now point it at your own project.

The first thing to check is always Frontier → Direct. If anything is there, fix it before doing anything else — those are broken execution paths. Then Orphan: is the work sitting in your codebase connected to the rest of it? Then Topology: what does the action queue say?

The Ask bar at the bottom runs natural-language queries against the structural database. Type a symbol name to get callers, callees, and risk profile. Type a question about the codebase to get an answer grounded in the graph, not in the model's training data.

Determined won't tell you what your code should do. It tells you what it actually does — and where what it actually does diverges from what you probably intended.
