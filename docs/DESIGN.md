tools/analysis - DESIGN (consolidated)
=======================================

This file consolidates the design/architecture docs that used to live as
separate files in tools/analysis/docs/. The originals are preserved in
docs/del/ for reference, not deleted, in case anything below was condensed
too aggressively:

- AGENT CAPABILITY LAYER v1.md
- TRUTH KERNEL v1.md
- truth query algebra.md
- contracts  + visibility.md
- Symbol Classification Stabilization Plan.md
- work flow.md

For live status, checklists, and the session-by-session history of what's
actually been built and verified, see TRACKER.md (consolidated from
REFACTOR OPS BOARD.md, Truth Kernel Board.md, Truth.md, todo-done.md - also
in docs/del/). This file is architecture/intent; TRACKER.md is "what's true
right now and how we got there." Per the working agreement in CLAUDE.md, new
accepted design decisions get implemented and then tracked in TRACKER.md -
this file should not turn into a 6th competing source of status truth.

Consolidated 2026-06-17.

---

## 1. Core philosophy (from work flow.md)

The database snapshots are just the substrate. What matters is that you can:

- Run the pipeline on any codebase (or subdirectory) to produce a .db
  snapshot.
- Query that snapshot to answer questions like "what functions are never
  called," "which modules have the most dependencies," "where are side
  effects happening."
- Use those answers to decide what to keep, discard, or refactor.
- Iterate on the tool (better indexing, smarter classification, richer
  contract extraction) knowing you have a repeatable way to measure
  improvement.

No cross-run manifests, timestamps, or decision tables were needed to get
started - those are polish. The core loop is: snapshot -> query -> reason ->
act. This is the philosophy everything else in this doc builds on.

---

## 2. Truth Kernel - query algebra design

This is the current, locked design for how natural-language questions get
turned into deterministic, structured answers. It originates from an
earlier exploratory draft (see "2.1 Earlier draft" below) and was tightened
into the spec actually implemented.

**Core idea, one sentence:** convert questions into a small, closed query
algebra, execute it deterministically, and never allow AI or heuristics to
invent structure beyond that algebra.

### System shape

Exactly 4 things, everything else derived:

1. Query AST (structure)
2. Query Validator (rules)
3. Query Executor (deterministic runtime)
4. Query Compiler (the only AI-facing component)

### Layer 1 - query primitives

AST nodes: `Select(view, metric?)`, `Filter(key, op, value)`, `Combine(left,
right)`. Keep this exact; no expansion unless a real gap forces it.

Checkpoint: the AST can represent all existing test queries, no new node
types required.

### Layer 2 - query validation (the real core)

Every AST must pass: VALID / INVALID + reason. Rules are strict but small:

- **View legality** - only registered views: STRUCTURE / STABILITY /
  INTEGRITY / SUMMARY / SUBSYSTEM / ROLE / INTENT (7 total; ROLE added
  2026-06-16, INTENT added 2026-06-19).
- **Metric legality** - must match `QueryPlan.VALID_METRICS[view]`.
- **Combine legality** - only registered pairs are allowed:
  `(STRUCTURE, STABILITY)`, `(STRUCTURE, INTEGRITY)`, `(SUMMARY, STABILITY)`,
  `(SUBSYSTEM, STRUCTURE)`, `(STABILITY, INTEGRITY)`. ROLE and INTENT are
  Select-only for now (no Combine pairs registered). No guessing, no fallback.
- **Filter legality** - filter keys must be in `allowed_keys(view)`.

Checkpoint: invalid combine, invalid metric, and invalid filter all hard-fail.

### Layer 3 - query executor

Executes a validated AST into deterministic output:

- `Select` returns `view[metric]` or the full view.
- `Filter` wraps a `FilterResult`, no mutation.
- `Combine` is a strict structural join only - `{left: resultA, right:
  resultB}`. It does NOT merge meaning, infer relationships, or rewrite
  data.

Checkpoint: the same query always produces identical JSON, no hidden
sorting randomness, no interpretation logic in this layer.

### Layer 4 - query compiler (the only AI surface)

Input: natural language. Output: AST only. The compiler may only produce
`Select`/`Combine`/`Filter` nodes built from the registry - no expansion, no
synonym injection, no "semantic interpretation," no guessing new views, no
runtime discovery.

Example: "what depends on resolve_analysis_db_path" compiles to
`Combine(Select(STRUCTURE), Select(INTEGRITY), Filter(key="symbol",
op="==", value="resolve_analysis_db_path"))`.

Checkpoint: the compiler never invents structure, always outputs a valid
AST, and the executor never depends on NLP.

### Layer 5 - view functions

`build_structure_view`, `build_stability_view`, `build_integrity_view`,
`build_subsystem_view` (plus `build_role_view`, added later). Views must
never call other views - they are pure transforms of DB/graph data.

### Full runtime flow

```
USER QUESTION
    -> QUERY COMPILER (AI)
    -> AST
    -> VALIDATOR
    -> EXECUTOR
    -> RESULT OBJECT
    -> NARRATOR (optional)
```

### Build order (as originally planned)

1. Lock validation rules and combine rules; make the executor deterministic.
2. Hard-test AST coverage; confirm no missing node types.
3. Replace ad-hoc graph inspection paths with the algebra.
4. Connect the compiler safely - last step, not first.

### Explicitly out of scope

No adaptive query expansion, no semantic scoring layer, no ML ranking of
symbols, no heuristic hotspot-inference changes, no "AI reasoning over the
graph." These would break determinism, which is the entire point of the
design: AI can only talk about truths that already exist in structured
form. The system is a closed-world reasoning substrate, not an open
reasoning system - combinations must be enumerated, views must be fixed,
filters must be constrained.

For the current build/test status of every layer above (AST, Executor,
Planner/Validator, Compiler, Views, and the ROLE/INTENT views added after this
spec was written), see TRACKER.md's Truth Kernel Tier Status section - it is
the authoritative "is this actually true today" answer, not this file.

### 2.1 Earlier draft (superseded, kept for historical context)

`truth query algebra.md` was the original sketch of this idea, written
before TRUTH KERNEL v1 above locked in the final shape. The reframe it
argued for - "you are not building a smart AI system or a reasoning graph,
you are building a verifiable system introspection engine with a
constrained query language; AI is only a query compiler and a narrator" -
is the same core idea carried into the spec above, just with different
layer names (it called the views STRUCTURE_VIEW/STABILITY_VIEW/
INTEGRITY_VIEW/SYSTEM_SUMMARY_VIEW instead of bare names, and proposed a
`truth_query_spec.py` file as the source of truth for legal
views/combinations/filters/aggregations). Nothing in it contradicts the
locked design above; it was superseded by it, not overruled. Kept here only
so the evolution of the idea isn't lost - the locked spec above is what to
build against.

---

## 3. Intent Layer - semantic summaries and knowledge artifacts

**Status: built and wired (2026-06-19). See TRACKER.md item 12b for proof.**
The sections below are the original design reasoning; they remain accurate
except for the "nothing built yet" framing. Section 3b (below) documents the
2026-06-20 knowledge.db architecture decision that extends this layer.

### The problem this solves

The structural graph (graph_edges, symbol_references) answers "what calls
what" correctly and deterministically. What it cannot answer is "what is
this file *for*" - and the current Role view's heuristic approach (keyword
substring match on callee names) was rated NOT YET RELIABLE in the Tier 2
evaluation precisely because it confuses "this file references a
graph-related symbol" with "this file is a graph component." There is no
durable, grounded layer that captures intent.

This means every session that asks about a module's purpose either runs a
fresh heuristic guess or has to re-derive the answer from scratch. Knowledge
produced during one session - what a module does, what a strategy decision
was, what a query revealed - is ephemeral. It disappears when the session
ends, and the next session starts cold.

### Two sub-layers, not one

These are related but distinct and should be built and treated separately:

**Sub-layer A: AI-generated semantic summaries.** Per-file, per-module,
per-subsystem descriptions of what something does, generated by an AI
reading the actual source rather than inferring from call-graph position.
These are auto-generated and auto-invalidated. Storage: a `semantic_summaries`
table with `subject` (file path or module name), `kind` (file / module /
subsystem), `content` (the summary text), `source_hash` (hash of the file
content at generation time), `model_version`, and `generated_at`. The
source_hash is the staleness signal: if the file's current content hash
doesn't match the stored hash, the summary is stale and gets excluded from
answers or queued for regeneration. Generate lazily on first query for a
given subject, not eagerly at ingestion time - most files in a corpus will
never be queried, and a full cold-generation pass over a large corpus is
expensive. These summaries are advisory and second-class: they do not
override structural ground truth, and a query that contradicts a structural
fact should say so explicitly rather than trusting the summary.

**Sub-layer B: Knowledge artifacts.** Findings, strategy decisions, and
confirmed facts produced during sessions and stored as durable, first-class
artifacts that the query layer can retrieve and reason over in future
sessions. This is the layer that captures "turns out explain_file.py is a
complete per-file report generator that nothing calls" or "don't do the
architecture split until after intent capture is done" in a form the system
can surface when asked "what do we know about the contracts layer." Storage:
a `knowledge_artifacts` table with `subject` (file path, module name,
subsystem, or free-form topic), `kind` (file_purpose / strategy_decision /
query_finding / design_note / known_issue), `content`, `provenance`
(human-confirmed / ai-generated / ai-confirmed-by-human), and `created_at`.
Provenance is load-bearing: a human-confirmed artifact outranks an
ai-generated one when they conflict, and the query layer should say so
explicitly rather than silently preferring one. Artifacts are stored
deliberately - not automatically after every query, which would produce
noise - via an explicit "keep this" signal from the user mid-session or
from the AI at the end-of-session SESSION_STATE update pass.

### Why the distinction matters

AI-generated summaries describe what code structurally does at a point in
time. Knowledge artifacts capture what has been *determined* - through
querying, through sessions, through judgment calls - and may include
things that aren't derivable from code at all (strategy decisions, known
issues, intent behind a design choice). The staleness model is also
different: a summary goes stale when the source file changes (detectable
via hash); an artifact goes stale when the underlying situation changes
(detectable only by a human or by a query that contradicts it). Both can
coexist in the system as long as they're clearly typed and provenance-labeled.

### How this fits the existing Truth Kernel

The Truth Kernel is deliberately deterministic and closed: AI is only a
compiler and narrator, not a source of structural facts. This layer extends
that model upward rather than breaking it. Structural ground truth (graph
edges, symbol references, file counts) stays in the deterministic layer and
is never overridden by intent-layer content. The intent layer answers
questions the structural layer cannot answer at all ("what is this for,"
"what did we decide about this") without competing with the structural layer
on questions it already answers well. The query compiler routes questions
to the right layer - structural or intent - not to a blend of both.

### Sequencing

Build after the semantic summaries work is scoped and after inspect/
explain_file.py is wired (section below) - that wiring will show exactly
where the heuristic signal breaks down and what the AI summary needs to
cover. The artifact mechanism should be built alongside the Agent Capability
Layer (section 3a below), not before, since the task.md mechanism is a
natural first consumer of the knowledge artifact store: a task.md is itself
a durable artifact tied to a query, and the re-open-and-check-drift
requirement it already specifies is the same staleness model the artifact
layer needs. Build them together, not twice.

---

## 3a. Agent capability layer (design proposal - nothing built yet)

**Status: design only. Not one line of this has been implemented.** The
build-order checklist for this section lives in TRACKER.md under "Agent
Capability Layer build order" - that's where checkboxes belong; this
section is for the reasoning behind them, not for tracking what's done.

### Why this layer exists

The concrete trigger was small: Bart half-remembered a design decision -
"potentials that collapse at trigger time" - and asked for it to be
checked rather than trusted from memory. It checked out, but only
partially: `world_controller.py`'s `potential_locations` and
`generate_location_from_potential`, `world_map.py`'s on-demand-generation
comment, and `travel_system.py`'s `EncounterPoint.activate()` /
`generate_encounter()` all confirmed the mechanism is real and wired up -
but `region_id` is hardcoded `None` at the point a potential is created,
so `generate_location_from_potential` always returns `None` right now.
Wired, but dead.

That's the pattern worth naming: a half-remembered fact about a large
codebase turned out to be mostly right and partly wrong, and the only way
to find out which parts was to go look. This is the same problem the Truth
Kernel already solves one level down - "the AI must not invent structure,
it must read it off the DB" - showing up one level up, for the person
doing the designing. Bart's own framing for this is "the boundary is my
memory": past some size, a codebase stops fitting in one person's head,
and the limiting resource isn't AI capability, it's how much of a large,
changing system one person can keep accurately in mind at once. This
layer is about extending the Truth Kernel's discipline outward to cover
the actual game code (world/, engine/, resolver/, dungeon_neo/, etc.),
which has never been ingested at all - right now, questions about it
require ad-hoc grep, not a query.

### The shape: four layers, one throughline

It's tempting to describe this as four independent features to build.
That's the wrong frame - two of the four layers are already built, because
they're the same mechanism the Truth Kernel runs on, just narrower in
scope than they need to be. The other two are genuinely new, and one of
them depends on a fact about the system that hasn't been checked yet.

**Knowledge - widen the substrate, don't redesign it.** The
`graph_edges`/`symbol_references` tables and the ingestion pipeline that
populates them already exist and already work; they're just scoped to
`tools/analysis` itself. Pointing that same ingestion at `world/` +
`engine/` + `resolver/` + `dungeon_neo/` (with `core/`, `og_system/`,
`routes/`, `ai/` as a second pass) is "run the thing we already have over
more files," not new design.

**Reasoning - proven, but only proven on one corpus.** The query algebra
(Select/Combine), the 6 views, and `Assessor.ask()` as the NL front door
are real, tested, and regression-covered - but every test that proves that
runs against `tools/analysis`'s own code. "This works" and "this works on
a much larger, differently-shaped codebase full of game logic instead of
analysis-tool logic" are different claims, and only the first one has been
checked. Applying this project's own verify-don't-assume discipline to
itself: the reasoning layer should be treated as proven-on-one-corpus, not
proven, until it's actually been run against the widened Knowledge layer.

**Tracking - a durable record has to answer to ground truth, not just
exist.** Nothing like a per-task durable record exists yet; TRACKER.md is
the closest analogue, but it's meta-notes about the analysis tool itself,
not a workspace for tracking an in-progress change to the game code. The
task.md mechanism below is the proposed answer. The reason its
re-open-and-recheck-drift requirement isn't optional: a checklist that
just sits there and gets read is, eventually, "memory in a different file
format" - exactly the failure mode this whole layer exists to avoid. A
task.md only earns its keep if reopening it re-asks the question it was
built from, against current DB state, every time.

**Capability - the payoff layer, and the one most likely to fool you if
skipped past.** An `impact_query` intent already exists in
`api/oracle_router.py`. What's unverified is whether it returns the full
transitive reverse-dependency closure of a target symbol, or only what the
explainability trace's depth budget happens to surface along the way -
those are very different guarantees, and right now nobody has written down
which one it actually provides. This project has hit the "looks done,
isn't" pattern more than once already (orphaned Truth Layer views with
zero real callers, `drift_signals` hardcoded to `[]`, `Filter` nodes that
were referenced but never constructed) - the lesson each time was that an
unverified assumption about what a piece of code actually does is exactly
where the next one of these is hiding. `impact_query` is a plausible next
home for that bug, precisely because it looks finished. It has to be
audited against real data before the task.md mechanism is built on top of
it, not after.

### The task.md mechanism, and where it's deliberately *not* meant to help

Bart's own stated workflow: for a SIMPLE ripple - a rename, a literal
string in a known-small set of places - he already has the right tool,
Sublime Text global search, navigate, edit, and this system shouldn't
insert itself there; that would just be friction for no benefit.

For a NON-simple ripple - where the chain includes pass-through logic,
indirect callers, or effects a literal-string search can't see (an
interface contract, a data shape, a behavior that changes meaning two
calls downstream) - that's the case this is meant to help with. Not by
guessing: by enumerating the real chain from the graph and giving a
structured place to work through it "one at a time in order till we get it
fixed," in his words, including "hate to leave something broken."

A task.md, generated from a ripple/impact query, should contain:

- the target symbol/file and the query that produced this file, so it can
  be regenerated, not just read
- the full discovered chain in both directions, distinguishing "local
  effect at this site" from "pass-through logic that itself needs to
  change" - those are different kinds of work and collapsing them into one
  undifferentiated list would defeat the purpose
- one checklist line per affected site, each in a state: OPEN / IN
  PROGRESS / DONE / ABANDONED (with reason) - reusing the same state
  machine as durable backlog items generally, rather than inventing a
  second one
- nothing marked DONE on the file as a whole until every line is DONE or
  explicitly ABANDONED with a reason - no silent partial completion

Re-opening a task.md has to do more than display the file: it has to
re-run the query that generated it against current DB state and report
drift - sites that no longer exist, new sites that now match, anything
that changed shape since the file was written. Skip that, and a task.md
from last week goes stale exactly the way a half-remembered design
decision does - which is the thing this whole layer was built to stop
happening.

### Decisions Bart has already made, and why

1. **Where should task.md files live?** Answer: the docs folder, same
   folder as this file. The alternative under consideration was a
   dedicated `tools/analysis/tasks/` directory; the simpler answer won
   because there's no benefit yet to a separate location until there's
   evidence one is needed - matching the project's general preference for
   not building structure ahead of a demonstrated need for it.
2. **Should ABANDONED require a reason every time**, or is that overkill
   for a one-person backlog? Answer: if the AI isn't sure of the reason, it
   should ask; if Bart says he doesn't care, fall back to a sensible
   default (e.g. "user ok'd"). This keeps the state machine honest without
   making it bureaucratic - the point of requiring a reason is to prevent
   silent abandonment, not to extract paperwork.
3. **For "pass-through logic," is structural call-chain enumeration enough
   for v1**, or should the existing contract/classification machinery
   (section 5 below) be pulled in too, to flag behavioral/type risk along
   the chain? Answer: keep v1 to structural call-chain enumeration only;
   add more later if a real case demonstrates the need. This is the same
   discipline as decision 1 - resist scope creep that isn't backed by
   evidence yet, especially here, where section 5's contract systems are
   themselves only partially reconciled with each other.

Build sequencing, what's actually started, and current status all live in
TRACKER.md - intentionally not duplicated here.

## 4. Symbol classification & routing architecture

This was originally a 4-iteration execution plan (Symbol Classification
Stabilization Plan.md). As of 2026-06-16, the target files largely exist
under their planned names (graph/symbol_classifier.py,
graph/symbol_router.py, graph/build_dependency_graph.py,
graph/module_resolution.py, ingestion/scan_project_files.py,
ingestion/extract_symbols.py) and most of the plan's intent has landed.
Two things in the original plan are now stale and should not be followed
literally: every "VALIDATION" step said to run
`python tools/analysis/run_analysis_pipeline.py`, which no longer exists
anywhere in the repo (deleted in the loose-script cleanup - see TRACKER.md;
the real entrypoints are `engine/run_engine.py` for ingestion and
`ask.py` for querying); and Iteration 3's target file
`persistence/persist_file_analysis.py` doesn't exist either - persistence
now lives in `persistence/persistence_engine.py`. Treat what follows as the
historical design record of the classifier/router/graph layer, not as
runnable instructions.

### Objective

Stabilize the analysis pipeline by separating symbol ingestion, symbol
normalization, symbol routing, symbol classification, and persistence
responsibilities into a deterministic pipeline with explicit authority
boundaries between stages. Deliberately avoids graph redesign, semantic
inference, or advanced runtime analysis.

### The problem this solved

The system used to mix multiple identity domains into a single classifier
path: static AST identities (`AIBoundary`, `world.map.generate_loot`),
runtime-derived access chains (`self.ai_system`, `ctx.session`,
`generate_structured_data.self.ai_system`), and language/builtin/external
symbols (`any`, `max`, `pathlib.Path`, `flask.jsonify`) - all run through
one comparison system. That caused false `external_unknown`
classifications, inconsistent project classification, debugging opacity,
unstable heuristics, namespace contamination, and persistence ambiguity.

### Target architecture (the part that's still the live mental model)

```
RAW SYMBOL -> NORMALIZATION -> ROUTER -> DOMAIN CLASSIFIER -> PERSISTENCE
```

Each layer has exactly one authority, and is explicitly never responsible
for the others' jobs:

1. **Ingestion authority** - extracts symbols from AST, preserves canonical
   identities, builds the project symbol universe. Never classifies, never
   does runtime inference, never persists, never touches graph semantics.
2. **Normalization authority** - canonical comparison identity, stable key
   extraction (e.g. `ai.ai_boundary.AIBoundary.classify_intent` ->
   `classify_intent`). Never classifies, routes, or persists.
3. **Routing authority** - decides symbol domain only: project / runtime /
   builtin / stdlib / external. Never persists, builds graph, or does
   semantic interpretation. Implemented as `route_symbol()`,
   `is_runtime_symbol()`, `is_builtin_symbol()`, `is_static_project_symbol()`
   in `graph/symbol_router.py`.
4. **Domain classification authority** - classifies only within an
   already-routed domain. Never routes, normalizes, or persists.
5. **Persistence authority** - deterministic storage only (insert rows,
   commit transactions, store already-classified entities). Never
   classifies, routes, normalizes, or does semantic interpretation - no
   project matching, bucket inference, classification heuristics,
   normalization logic, or fallback decisions belong here.

Final expected shape:

```
RAW SYMBOLS -> INGESTION -> NORMALIZATION -> ROUTING
                                                |
                       +------------------------+------------------------+
                       v                        v                        v
                  PROJECT                  RUNTIME                BUILTIN/EXT
                 CLASSIFIER               CLASSIFIER               CLASSIFIER
                       |                        |                        |
                       +------------------------+------------------------+
                                                v
                                          PERSISTENCE
                                                v
                                       DEPENDENCY GRAPH
```

### Success criteria (the bar this was measured against)

Symbol domains separated before classification; project identity
deterministic; runtime traces don't contaminate static analysis;
persistence performs storage only; graph relationships stay reproducible;
debugging localized by layer; each layer has exactly one authority;
classification behavior predictable and explainable.

The original plan broke this into 4 iterations (identity stabilization,
routing layer separation, persistence stabilization, graph consistency
stabilization), each with its own target files, required outcomes, and
non-goals. Per the status note above, that level of detail is now mostly
historical - the files and authority boundaries it specified are in place.
If the authority model above is ever violated by future changes, this
section is the reference for what "violated" means.

### The shadow/observability layer (added after this plan; not in the original design)

This wasn't in the original Symbol Classification Stabilization Plan, but
it's real and live in `graph/symbol_router.py` / `graph/route_trace.py`
today, and it isn't documented anywhere else, so it belongs here.

`route_symbol()` is still the only production entrypoint - a thin wrapper
over `_route_symbol_core()`, explicitly commented in the source as "the
historical routing truth source... must remain deterministic and
structurally stable." Nothing about that has changed.

Alongside it, `route_symbol_shadow()` runs the same core router but also
attaches a `TraceCollector` that records CP0-CP4 checkpoints (raw input,
canonical/normalized form, classification input, project/runtime/
builtin/stdlib match flags, final result) plus a parallel "CP2.5 semantic
observation" pass that records lexical/decomposition signals and candidate
semantic identities (surface, fqdn guess, module, confidence, evidence).
The source comments are unusually explicit about what this layer is and
is not: "This is NOT a production routing path," "MUST NOT influence CP3
routing decisions," "All routing decisions in this module are final
within the pipeline" (referring to the CP3 stage the legacy router owns).
It's a pure observation/audit channel, not an alternate routing path.

This is the resolution of an older, larger ambition. The
"semantic identity reconstruction" line of work (see
`docs/del/Semantic Identity Reconstruction Migration Plan.md`) originally
proposed a phased migration - through CP2.5 and CP3 checkpoint stages,
comparing a shadow semantic-aware router against the legacy one - toward
eventually replacing `route_symbol()` with identity-aware resolution. The
code comments confirm that the comparison/shadow infrastructure got built
close to as specified, but the end state didn't: a full "CP2.5 semantic
observation layer" that could influence routing was tried, then marked
`(DEPRECATED)` and removed from execution, then replaced by the current
"SEED DISCOVERY LAYER" (DB-backed symbol lookup, explicitly "no semantic
interpretation, no identity reconstruction") plus the permanent
trace-only CP2.5 that exists today. In other words: the diagnosis behind
the migration plan was correct and the audit tooling it called for got
built, but the project deliberately stopped short of the planned
pipeline replacement and settled on "legacy router stays sole authority
forever, shadow/trace layer watches and records but never decides." That's
a quieter, more conservative outcome than the original plan envisioned,
and it's consistent with this section's own authority-model principle:
one layer, one authority, and "use the shadow output to inform a human or
a future decision" is a different thing from "let the shadow output make
the decision."

No open item currently tracks whether this shadow/trace layer is being
used for anything (e.g. periodic comparison runs, drift detection) or
just sitting there instrumented but uncalled outside of
`classification/classify_references.py`'s direct use of
`route_symbol_shadow()`. Worth a real audit before the Agent Capability
Layer's Knowledge-widening work (section 3) starts touching this part of
the pipeline.

---

## 5. Contracts & governance - exploratory notes (superseded)

This section is a condensed version of `contracts  + visibility.md`, kept
for the conceptual framing even though its concrete proposal is moot. The
original read as an AI-assisted brainstorming transcript rather than a
committed plan; its concrete proposal - plugging a "safe evolution
protocol" into `run_analysis_pipeline` and `debug_run.py` - is moot because
both of those files were deleted in the loose-script cleanup (see
TRACKER.md; the pipeline module never existed, debug_run.py only imported
it). The conceptual framing below predates, and was effectively superseded
by, the Truth Kernel / oracle work in section 2 above, which is further
along and already running against real data.

**The observation that mattered:** the codebase already had (and may still
have) 4 overlapping contract systems, not one - a JSON contract registry
(`tool_system_contract.json`, classification boundary rules, CP0-CP1
pipeline rules), Python contract modules
(`semantic_pipeline_contract.py`, `classification_contract.py`,
`contract_validator.py`), embedded inline contracts (LOCKED-comment style
invariants in `evaluation_snapshot.py`/`symbol_classifier.py`/
`semantic_candidate_builder.py`), and structural contracts in the
ingestion/graph layer (`BehavioralContract`,
`_extract_behavioral_contracts`, `FileAnalysis.behavioral_contracts`). The
real problem identified wasn't "we need to design a contract system" - it
already existed, distributed and partially inconsistent - it was "there is
no single arbitration layer deciding which contract is authoritative when
they disagree."

**The 3-layer mental model proposed** (reality layer = the actual codebase;
truth-extraction layer = snapshots/metrics/classifier outputs;
constraint layer = contracts in all their forms) is still a reasonable way
to think about where a future "contract precedence" system would sit, if
one is ever built. It is not currently built, and nothing in section 2's
Truth Kernel design depends on it - the Truth Kernel's STABILITY view reads
real contract violation reports directly rather than going through any
arbitration layer. Worth a skim if this idea is revisited; don't treat any
file/entrypoint name in the original as current.

---

## 6. SystemSelfModel & system_shape_tags (Tier 2 introspection)

**Naming note before anything else:** this section's "system shape" is
unrelated to section 2's "### System shape" subsection above. Section 2
uses that phrase for the 4-part query-algebra design (AST / Validator /
Executor / Compiler). This section's `system_shape_tags` is a completely
different, unrelated piece of vocabulary: a set of boolean tags computed
from live DB data about *this specific codebase's* structural properties.
The collision is purely a naming accident from two different exploratory
threads; don't conflate them.

This capability was found, during the 2026-06-18 from-the-beginning
codebase review, to be real, live, and production-wired - but undocumented
anywhere before now. It belongs here for the same reason the shadow/
observability layer (section 4) does: it exists, it's load-bearing, and a
future session shouldn't have to rediscover it from scratch.

### What it is

`SystemSelfModelBuilder` (`inspection/meta/system_self_model.py`) builds a
`SystemSelfModel` - the assessor's account of its own blind spots. It is a
Tier 2 Truth Kernel component in the sense used elsewhere in this doc: it
does not invent facts, it only reports on structural conditions that are
already measurable from `oracle`/`graph`/`system_shape`, plus a small,
fixed set of honestly-labeled limitations of the inspection layer's own
design. Every field is either (a) populated from a real, checkable
condition, or (b) a fixed structural caveat - nothing fires unconditionally
except the caveats that are explicitly meant to.

`SystemSelfModel` has six list fields: `capabilities`, `limitations`,
`structural_biases`, `failure_modes`, `inference_gaps`, `notes`.

### Where it's wired in

Confirmed live in two places, not just a standalone utility:

- `Assessor.self_model()` (`assessor/assessor.py`) calls
  `SystemSelfModelBuilder(self.oracle).build()` directly.
- `QuerySession`'s result object includes the self-model in its output.
- The `query_sessions` table (see `persistence/persistence_engine.py`'s
  `ensure_schema()`) has a reserved `self_model TEXT` column for it.

### How `build()` derives each field

1. **Graph observability** - reads `oracle.get_snapshot_graph().edges`.
   Zero edges -> `failure_modes: graph_empty_state`. 1-9 edges ->
   `limitations: low_observability_graph`. These are mutually exclusive
   (empty vs. sparse-but-nonempty).
2. **Router presence** - `_router_module_present()` checks
   `importlib.util.find_spec("tools.analysis.api.oracle_router")` rather
   than importing it directly, to avoid a circular import between
   `oracle/`, `api/`, and `inspection/`. If present:
   `structural_biases: router_is_primary_decision_layer,
   router_expansion_budgets_not_fully_calibrated`, plus
   `capabilities: query_expansion_via_router`. If absent:
   `failure_modes: router_module_unreachable`.
3. **DB-derived system shape** - calls
   `inspection.system_shape.generate_system_shape(oracle.conn)` inside a
   try/except (see "Failure path" below) and maps its
   `system_shape_tags` onto self-model fields:
   - `external_dependency_heavy` -> `limitations: external_dependency_dominance`
   - `high_coupling_core` -> `failure_modes: high_coupling_core_risk`
   - `contract_weak_system` -> `limitations: contract_coverage_weak`
   - `hotspot_concentrated` -> `structural_biases: analysis_concentrated_in_few_hotspots`
   - `cross_layer_coupling_detected` -> `failure_modes: cross_layer_coupling_present`

   (`generate_system_shape()` itself, in `inspection/system_shape.py`,
   computes these 5 tags from the `files`/`imports`/`symbol_references`/
   `contract_violations` tables - notably not from `graph_edges`, so the
   graph-observability checks above and these tag checks are independently
   seedable/testable.)
4. **Oracle capability checks** - `hasattr(oracle, "get_snapshot_graph")`
   -> `capabilities: symbol_graph_traversal`;
   `hasattr(oracle, "file_reference_map")` -> `capabilities:
   contract_violation_detection`. These check for real methods that
   execute against DB-derived data, not aspirational claims.
5. **Fixed, unconditional caveats** - always appended regardless of any
   runtime check, because they're structural properties of the current
   architecture, not conditionally-detected facts:
   `inference_gaps: semantic_identity_is_heuristic_not_ground_truth,
   edge_bucket_assignment_is_best_effort_classification`;
   `notes: system_self_model_is_derivative_not_authoritative,
   self_model_reflects_db_snapshot_at_query_time_not_live_state`.

### Failure path

If `generate_system_shape()` raises for any reason (missing table, bad
data, etc.), `build()` catches the exception and records
`inference_gaps: system_shape_unavailable:<ExceptionType>` rather than
propagating the error or silently producing a partial/wrong shape. The
rest of the self-model (graph checks, router checks, oracle capability
checks, fixed caveats) still gets built normally - a broken system-shape
query degrades the self-model, it doesn't crash it.

### Test coverage

As of 2026-06-18 this has a dedicated regression test file,
`tests/regression/test_system_self_model.py` - see TRACKER.md item 19.
Before that, it had zero direct test coverage despite being live and
wired into two production call sites.

---

## 7. knowledge.db - shared knowledge overlay (decided 2026-06-20)

### The problem

`knowledge_artifacts` and `semantic_summaries` were originally stored inside
each corpus DB (`world_corpus.db`, `engine_corpus.db`, etc.). This created
two problems:

1. A finding about `world/world_controller.py` could only be stored in
   `world_corpus.db` - not visible when querying any other corpus.
2. Corpus DBs are expendable rebuild artifacts. Rebuilding `world_corpus.db`
   would silently delete all human-confirmed findings stored in it.

### The design

A single `knowledge.db` at the repo root holds only the two intent tables:
`knowledge_artifacts` and `semantic_summaries`. All corpus Assessors read and
write to this shared DB via an optional second connection (`KnowledgeOracle`).

- Corpus DB answers "what is the structure" (graph_edges, functions, classes).
- `knowledge.db` answers "what do we know about the code" (findings, summaries).

Assessor's `knowledge` parameter defaults to opening `knowledge.db` in the
same directory as the corpus DB. Tests that don't need it pass `None`.

### Staleness

`semantic_summaries` already has `source_hash` - no change needed.

`knowledge_artifacts` gains two new columns:
- `file_hash TEXT` - hash of the subject file at artifact creation time.
- `needs_review INTEGER DEFAULT 0` - set to 1 by the ingestion pipeline when
  a re-ingest detects the subject file changed (new hash). Never auto-deleted;
  human confirms whether the finding still applies.

The ingestion pipeline (`EngineRunner.run()`) checks `knowledge.db` after each
file is processed: if any artifact's `subject` references that file path and
the stored `file_hash` differs from the newly computed hash, it sets
`needs_review = 1` on that artifact.

`generate_task_md()` surfaces `needs_review` artifacts with a "[STALE - needs
review]" prefix so the agent knows to verify before trusting the finding.

### Why this survives the planned corpus DB merge

The three game corpus DBs (`world_corpus.db`, `engine_corpus.db`,
`dungeon_neo_corpus.db`) are planned to merge into a single `game_corpus.db`
once `_persist_graph_edges` supports per-file edge management (TRACKER item 3).
Because `knowledge.db` is separate, that merge is a pure structural operation -
findings survive untouched, no migration required.

---

## 8. Local conversational agent (design - 2026-06-20)

### Purpose

A local, Ollama-powered conversational agent that lets Bart interrogate any
corpus DB in plain English, with conversation history held in memory for the
session. The goal is to replace the need to involve Claude for routine
codebase questions - "what touches encounters", "what is travel_to_location
responsible for", "what do we already know about character creation" - by
giving the model sharp, focused tools backed by the analysis layers already
built, rather than asking it to reason over raw code.

The model is `llama3.2:3b` (already running locally for semantic summaries
and query compilation). It is small and will not reason well over large
inputs. The design compensates by keeping every tool's output small and flat,
and by decomposing questions into sequences of focused tool calls rather than
one large context dump. The model orchestrates; the tools do the work.

### Conversation model

- History is a simple in-memory list of `{role, content}` messages for the
  session. Volatile - intentionally cheap to restart.
- Each turn: user input appended, model responds, model may call tools,
  tool results fed back, model synthesizes final answer.
- Pattern: ReAct loop (Reason -> Act -> Observe -> repeat until answer).
  Model outputs a structured tool call, we execute it, feed the result back
  as an observation, model decides next step or answers.
- Session ends when user types `quit` / `exit` / `q`. No persistence of
  conversation history across sessions - the knowledge.db is the durable
  layer for anything worth keeping.

### Tool set - each tool returns a small flat result

**Discovery tools** - find what exists

1. `search_symbols(query: str) -> list[{name, file, line, type}]`
   Calls `oracle.find_symbols(query)`. Returns up to 20 matching symbols
   across the corpus. Used when the model needs to locate a symbol by name
   or partial name before doing anything else with it.

2. `search_files(query: str) -> list[str]`
   Calls `oracle.find_files(query)`. Returns matching file paths. Used for
   "what files are in the encounter system" style questions.

3. `list_callers(symbol: str) -> list[{caller, file, line}]`
   Direct callers only - `graph_edges WHERE callee = ? OR callee LIKE
   '%.symbol'` (same fix as task_generator). Returns who calls this symbol,
   directly and by qualified name. Small result: direct graph edges only,
   not the full impact zone.

4. `list_callees(symbol: str) -> list[{callee, file, line}]`
   What this symbol calls - `graph_edges WHERE caller = ?`. Lets the model
   trace a call chain forward one step at a time.

5. `symbols_in_file(file_path: str) -> list[{name, type, line, has_docstring}]`
   All functions and classes defined in a file. Used when the model needs
   to understand what a file contains before deciding which symbol to dig
   into. `has_docstring` flag tells it whether intent data is available
   without fetching it yet.

**Understanding tools** - what does it mean

6. `describe_file(file_path: str) -> str`
   Calls `Assessor.semantic_summary(file_path, kind='file')`. Returns the
   Ollama-generated summary (now working - auto-reads source). If Ollama
   falls back to the heuristic stub, the result prefix says so and the
   model should note it is structural only. This is the primary tool for
   "what does X do" questions at the file level.

7. `symbol_intent(symbol: str) -> {name, file, line, docstring} | None`
   Returns the docstring for a specific function or class from the
   `functions`/`classes` tables. Layer 2. Returns None if no docstring
   exists - model should note the gap rather than guessing.

8. `symbol_brief(symbol: str) -> str`
   Calls `Assessor.generate_task_md(symbol)`. Returns the full two-tier
   brief: direct callers (confirmed) + impact zone. The richest single-symbol
   output the system can produce. Used when the model needs a complete
   picture of one symbol rather than building it up tool by tool.

**Knowledge tools** - what do we already know, what should we remember

9. `get_findings(symbol: str) -> list[{kind, content, provenance, stale}]`
   Calls `Assessor.get_artifacts(symbol)` against knowledge.db.
   Returns stored artifacts provenance-ranked (human-confirmed first).
   `stale=True` when `needs_review=1`. Model should surface stale findings
   explicitly rather than treating them as current.

10. `store_finding(symbol: str, kind: str, content: str) -> str`
    Calls `Assessor.add_artifact(symbol, kind, content, provenance='ai-generated')`.
    Writes a finding the model has derived during the session to knowledge.db
    for future sessions. Model should use this when it has synthesized
    something non-obvious that would cost tool calls to re-derive later.
    Valid kinds: `file_purpose / strategy_decision / query_finding /
    design_note / known_issue`. Returns confirmation string.
    Provenance is always `ai-generated` - human can upgrade via direct DB
    edit or future tool.

**Navigation tools** - help decompose

11. `files_in_directory(path: str) -> list[str]`
    Lists `.py` files under a given directory path (e.g. `world/`,
    `dungeon_neo/`). Does not recurse past one level. Used when the
    model needs to survey a subsystem before picking which file to
    describe or which symbol to chase.

12. `ask_truth_layer(question: str) -> str`
    Calls `Assessor.ask(question)` - the existing NL -> Truth Kernel
    algebra path. Returns a structured answer from the 7 truth views
    (STRUCTURE / STABILITY / INTEGRITY / SUMMARY / SUBSYSTEM / ROLE /
    INTENT). Use when the question is about the codebase's structural
    health, stability, or a system-wide view - not for per-symbol questions,
    which the other tools handle more directly.

### Tool call protocol (ReAct pattern for llama3.2:3b)

The model does not natively output JSON tool calls reliably at 3b scale.
We use a simple text protocol the system prompt defines and we parse:

```
TOOL: tool_name
ARGS: {"key": "value"}
```

The agent loop:
1. Build prompt from system prompt + conversation history
2. Call Ollama, stream response
3. Parse for TOOL/ARGS blocks in the response
4. If found: execute tool, append observation to history, loop back to 2
5. If not found (model is answering): print response, append to history,
   wait for next user input

The system prompt instructs the model to use exactly one tool call per
response turn, reason briefly about why before calling it, and synthesize
a final plain-English answer once it has enough information. This keeps
individual Ollama calls small and the reasoning transparent.

### System prompt design

The system prompt must be short enough that llama3.2:3b can hold it in
context alongside the conversation history and tool results without
degrading. Key elements:

- One-paragraph role statement: "You are a codebase analysis assistant for
  a Python dungeon-master game project. You have tools to query a structural
  analysis DB. Use them to answer questions factually. Do not guess - if you
  don't know, call a tool."
- Tool list: name, one-line description, argument names. No examples in the
  system prompt - examples go in the tool protocol section.
- Tool call format: the exact TOOL/ARGS syntax, with the rule "one tool
  call per response, reason briefly first."
- Synthesis rule: "Once you have enough information, answer in plain
  English. Note when a finding is stale or when a tool returned no results."
- Storage rule: "If you derive a non-obvious finding, store it with
  store_finding before answering."

### File layout

```
tools/analysis/
  agent/
    local_agent.py     - the agent loop, tool dispatch, Ollama calls
    agent_tools.py     - tool function implementations (wrappers over existing layers)
    agent_prompt.py    - system prompt and tool protocol definitions
```

`agent_tools.py` is the piece to build and test first, in isolation from
the agent loop. Each tool is a plain function taking a corpus oracle + an
input dict and returning a plain string or list. Test each tool against
a real corpus DB (world_corpus.db) with known expected outputs before
wiring into the agent loop.

### Architecture decision - three-phase model (2026-06-20)

The ReAct loop (model reasons → calls tool → reasons → calls tool) was
built and tested but proved too demanding for llama3.2:3b: the model echoed
the system prompt rather than using it. Root cause: the model is too small
to hold a long system prompt + conversation history + reasoning in context
simultaneously while also producing reliable tool call syntax.

**Replacement: three-phase deterministic pipeline.**

The model's job is narrowed to only two things it handles well at 3b scale:
decomposing a question into information needs, and summarizing factual results.
Everything in between is deterministic and not model-dependent.

```
Phase 1 - DECOMPOSE (AI, small output)
  Model reads question, outputs a checklist of information needs:
    NEED: files in the encounter system
    NEED: symbols named encounter
    NEED: what calls generate_encounter
    NEED: what does encounter_generator.py do

Phase 2 - RESOLVE (fully deterministic, no model)
  Pattern router maps each NEED to a tool call and executes it:
    "files in X"          -> files_in_directory(X)
    "symbols named X"     -> search_symbols(X)
    "symbols in X.py"     -> symbols_in_file(X)
    "what calls X"        -> list_callers(X)
    "callers of X"        -> list_callers(X)
    "what does X.py do"   -> describe_file(X)
    "summary of X"        -> describe_file(X)
    "intent of X"         -> symbol_intent(X)
    "findings for X"      -> get_findings(X)
    "what do we know X"   -> get_findings(X)
    "brief for X"         -> symbol_brief(X)
  All matched tools execute; results collected as flat fact set.

Phase 3 - ASSEMBLE (AI, reading comprehension only)
  Model receives original question + all facts, writes plain English answer.
  No tool calls, no reasoning about what to look up.
```

The NEED checklist from Phase 1 is inspectable - if the answer is wrong,
you can see exactly what was and wasn't looked up. The resolver in Phase 2
is independently testable with no model dependency.

### Build order

1. [DONE 2026-06-20] `agent_tools.py` - all 12 tool functions verified
   against world_corpus.db. 31 regression tests passing.

2. [DONE 2026-06-20] `agent_prompt.py` - system prompt + tolerant tool call
   parser (handles lowercase, single quotes, backtick-wrapped JSON, missing
   args block, extra whitespace). 20 regression tests passing.

3. [DONE 2026-06-20] `local_agent.py` - ReAct loop built and smoke-tested
   (6 tests). Proved insufficient for llama3.2:3b - see architecture
   decision above. Loop shell stays; internals to be replaced with
   three-phase pipeline.

4. **[NEXT] Rebuild `local_agent.py` around three-phase pipeline:**
   - Phase 1 prompt: short, focused - "list what you need to answer this,
     one NEED: per line, extract any symbol/file names explicitly."
   - Phase 2 resolver: pattern-match NEED lines to tool calls, execute all,
     collect results. Pure Python, no model. Independently testable.
   - Phase 3 prompt: "here is the question, here are the facts, answer
     concisely." No tool call format needed - just reading comprehension.
   - Conversation history: append (question, fact-set, answer) triples so
     follow-up questions have context without re-running Phase 1/2.

5. Evaluation sessions against world_corpus.db with real questions.

### What this is not

- Not a code editor or code writer. It answers questions, it does not
  produce diffs or edits.
- Not a replacement for ingestion. It queries existing DBs; it does not
  re-ingest on the fly.
- Not a replacement for task.md generation. `symbol_brief` calls the
  existing generator; the agent doesn't reimplement it.
- Not persistent across sessions by design. The knowledge.db is the
  persistence layer; conversation history is intentionally volatile.

---

## 9. Developer intelligence interface (vision - 2026-06-21)

### Code-agnostic design (hard constraint)

The tool is corpus-agnostic by design. It has no knowledge of the game,
its domain, or its conventions. It works by ingesting any Python codebase
into a corpus DB and letting the agent query that DB. The game corpus is
the current test subject, but the tool should work identically on Flask,
SQLAlchemy, a medical records system, or anything else.

Consequences:
- Heuristics must be phrased in structural terms (callers, files, symbols,
  findings) not game terms.
- The knowledge.db findings layer is how domain knowledge enters the system -
  a human or prior session stores facts about THIS codebase, and future
  queries draw on them. That is the only domain-specific layer.
- The UI makes no assumptions about what the corpus contains. "Files",
  "symbols", "callers", "findings" are the universal vocabulary.
- When evaluating a new feature, ask: would this work on Flask too?
  If not, it belongs in the knowledge layer, not the tool itself.

### The primary interface

The analysis tool is headed toward becoming a standalone developer
workbench - the primary interface a developer uses to understand,
navigate, and plan work on ANY codebase. Everything built so far
(corpus ingestion, Truth Kernel, conversational agent, knowledge.db,
PICK validation, heuristics) is backend infrastructure that this
interface sits on top of.

"Primary interface" means: when Bart wants to know what to work on
next, how a system works, what calls what, what the findings say, or
how a pattern was implemented before - he opens this tool, not a
separate file browser or grep session.

### Separation from the game (hard boundary)

The tool is a separate application - separate process, separate UI,
no runtime dependency on the dungeon app. The game does not know the
tool exists. This boundary is permanent: the tool interrogates the
game's source as a corpus, it does not run inside the game or share
its runtime.

The only legitimate coupling points:
- The game may expose test hooks (inspection endpoints, state dumps)
  as part of its own testing infrastructure. The tool may query those
  hooks. The game exposes them for testing; the tool exploits them.
  The game never imports from tools/analysis/.
- Shared utility code (pure functions, data structures) may be copied
  into both codebases, not imported across the boundary.

### Query taxonomy and coverage (as of 2026-06-21)

Ten categories of question the interface must answer well:

1. Identity/definition - "what is X", "where is X defined"
2. Structure/composition - "what files are in X/", "what classes in X.py"
3. Relationships/dependencies - "who calls X", "what imports X", "compare X and Y"
4. Behavioral/trace - "how does X work", "trace X", "show me how X is used"
5. Survey/landscape - "tell me about the quest system", "architecture of X"
6. Evolutionary/history - "what changed in X", "when was X last modified" (GAP)
7. Development planning - "what should I work on", "how was X done elsewhere" (partial)
8. Ranking/complexity - "most complex file", "most tightly coupled" (partial)
9. Quality/issues - "findings for X", "what has TODOs", "what has no docstrings" (partial)
10. Pattern/convention - "how is X typically done here", "find similar to X" (GAP)

Categories 6 and 10 are currently unaddressed. Category 7 (dev planning)
is the highest-value gap: "what should I work on next" and "how was this
pattern implemented elsewhere" are the questions a co-developer asks most.

### UI interaction model (decided 2026-06-21)

Default mode is chat: plain text in, text out. But answers are typed,
and the type determines the renderer automatically - the user never
chooses a display format, the answer chooses it:

- File list answer -> browsable list with drill-down buttons per file
- Call relationship answer -> two-column card or inline graph
- Findings answer -> card per finding, grouped by kind
- Count/ranking answer -> sorted table
- Survey answer -> structured sections with live symbol names

**The answer IS the navigation.** Every symbol name, file name, or
system name appearing in an answer is a live button. Clicking it fires
the next query without typing. The chat input handles open-ended
questions; buttons handle structured follow-through. The user never
retypes a name they just saw in output.

**Agent-suggested follow-ups.** Every answer ends with 2-3 suggested
next queries rendered as buttons (e.g. "callers of X", "findings for X",
"compare X and Y"). The user can click or ignore and type something else.
This makes structured navigation feel conversational.

**Proactive badges.** When a symbol or file is displayed anywhere, the
UI shows passive badges without asking: "4 callers", "2 findings",
"no docstring". Gaps are visible at a glance rather than discovered
by querying.

**Exploration breadcrumb.** Drill-down is a tree. The UI keeps the
full path visible (WorldController -> SessionSystem -> __init__) so
the user knows how they arrived and can navigate back up any branch,
not just linear back.

**Display modes (planned):**
- Call graph: nodes = symbols, edges = calls, immediate neighborhood
  of any chosen symbol. Clickable nodes fire identity queries.
- File dependency tree: collapsible, rooted at any chosen file.
- Findings dashboard: all knowledge_artifacts by category
  (design_note / known_issue / file_purpose / future_plan),
  sortable and filterable, each card with drill-down buttons.
- Diff absorption panel: accept a git diff, re-ingest changed files,
  surface what changed and what it may break. Closes the loop:
  edit code -> tool tells you the impact.

### Build order

Phase A (near-term, low effort):
- "What should I work on" heuristic: pulls workflow_items + findings
  to produce a prioritized answer.
- "How was X done elsewhere" heuristic: uses callers + examples to
  show prior implementations of a pattern.
- Impact analysis trigger: "if I change X what breaks" -> task_generator
  ripple query (already exists, just needs a heuristic entry point).

Phase B (medium-term):
- Drill-down structured responses with follow-up prompt suggestions.
- Quality sweep heuristics: TODOs, missing docstrings, unfinished items.
- Git history heuristic: thin wrapper over git log for evolutionary queries.

Phase C (longer-term):
- Standalone UI application (separate from the dungeon app).
- Call graph and dependency tree renderers.
- Findings dashboard.
- Diff absorption pipeline.

---

## 10. Code editing and refactoring capability (vision - 2026-06-21)

### Goal

The tool can suggest, preview, apply, and verify simple code edits -
docstring additions, new functions/classes following an existing pattern,
symbol renames with caller updates. It never produces broken code and
never applies anything without explicit approval.

### The safety model: suggest -> diff -> approve -> apply -> verify

Every edit follows this sequence without exception:

1. **Suggest**: tool proposes the change in plain English, names every
   file that will be touched and why.
2. **Diff**: tool shows the complete unified diff across all affected
   files before touching anything. Multi-file changes are shown together,
   not one at a time.
3. **Approve**: human explicitly confirms. No auto-apply, no "applying
   in 3 seconds unless you say no."
4. **Apply**: tool writes the change to disk.
5. **Verify**: immediately after apply -
   - ast.parse() on every changed file (syntax check, free, instant)
   - re-ingest changed files into corpus DB
   - compare symbol tables before/after: report any symbol that
     disappeared unexpectedly or any new symbol not in the plan
   - check all known callers of renamed/moved symbols are accounted for
6. **Report**: "these symbols changed, these callers were updated, corpus
   is consistent" - or "PROBLEM: X is now broken, here is why" with a
   rollback offer.

### What the corpus enables

The corpus DB is what makes this safer than a naive editor:
- Before renaming X, we know every caller of X across the whole codebase.
  The rename suggestion includes all of them. Nothing is missed.
- After editing, re-ingestion gives a symbol table diff. If a function
  that existed before is gone after, the tool flags it rather than
  silently succeeding.
- Pattern-following edits: "add a system like QuestManager" -> tool
  finds QuestManager in the corpus, extracts its structure (class shape,
  __init__ signature, method names, registration pattern), generates a
  template following those conventions, shows the diff.

### What it will and will not do

Safe operations (single-file or fully-enumerated multi-file):
- Add/update a docstring on a function or class that lacks one
- Insert a new function or class following a pattern found in corpus
- Rename a symbol with full caller update across all files shown upfront
- Extract a block into a named function within the same file
- Add a parameter to a function with all call sites updated

Will not attempt automatically:
- Moving code across files (import chain updates are too error-prone
  without a proper type-aware tool)
- Changes touching more than ~5 files without step-by-step approval
  for each file group
- Editing files not yet in the corpus (no symbol table = no safety net;
  ingest first)
- Any change where ast.parse() fails on the result (hard stop, no apply)
- Semantic correctness (the tool verifies structure, not behavior;
  tests are the human's responsibility)

### Code-agnostic constraint applies here too

The edit/refactor capability works on any ingested Python codebase.
Pattern discovery ("follow the shape of X") uses the corpus, not
hardcoded game knowledge. The only domain-specific input is what the
human types in the suggestion request.

---

## 11. Git access: current state and the credential boundary

### Today: local-read-only, zero secrets

The tool's only git capability is `git_log_for` (agent_tools.py), which
shells out to `git log` on the already-present local repo. This is a
local filesystem read of `.git` - no network, no credentials. The same
is true of any future `git diff` / `git show` / `git blame` and even
local `git commit`: none of these need a secret.

The credential question only becomes real the day a tool talks to a
**remote** (fetch / pull / push). That does not exist yet and should
not be added without revisiting this section.

### When remote access is added (the rules)

Two distinct properties to preserve, by different mechanisms:

1. **Secret away from the AI (by architecture, not hiding).** The tool
   must never *handle* the token. Let the OS credential layer hold it -
   on Windows, Git Credential Manager backs to Windows Credential Manager
   (DPAPI, tied to the user account). The tool runs `git push`; git
   supplies the credential at the network call. The token never enters
   the tool's memory, a constructed `https://token@host` URL, any log,
   knowledge.db, or the AI's context window. You cannot leak what you
   never hold.

2. **AI can trigger but not perform the privileged action.** Even with
   the token invisible, a misbehaving/injected AI could still *invoke*
   push (wrong branch, force-push, garbage). So:
   - `git_push` is NOT in the agent tool-dispatch table. Pushing is not
     an agent capability. The local Ollama agent never gets it.
   - Push lives only in the human-controlled UI action layer: the AI
     produces a push-request artifact (branch, commits, diff); the human
     approves; the tool (not the AI) executes. This is the §10
     suggest -> diff -> approve -> apply -> verify model with push as the
     most-privileged "apply" step.
   - Guardrails: never `--force`, branch allowlist, refuse protected
     branches.

3. **Token hygiene.** Fine-grained PAT scoped to one repo, Contents
   read/write only, with expiry; or a per-repo SSH deploy key with a
   passphrase in ssh-agent. Optionally a dedicated bot account so
   tool-made pushes are independently revocable. Append-only audit log
   of every push the tool performs.
