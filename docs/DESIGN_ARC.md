# Determined — Design Arc
_The map of what we are building, why, and how the pieces connect._
_Living document. Updated as the system evolves. Authoritative over session notes._

---

## The Objective

Determined is a developer intelligence tool. Its purpose is to help a developer
understand a codebase at any level of completion — from a blank architecture to
a fully realized system — and to close the gap between what exists and what should
exist by following the natural shape of the code.

The tool does not prescribe. It reveals. The developer sees the shape of what is
there, recognizes patterns, projects those patterns into what is missing, tests
the projections against design intent, and then realizes them — one node at a time,
following the paths the existing structure makes available.

This process is recursive. Every new node that gets realized brings its own
connected stubs. The frontier advances. The map extends.

---

## The Investigation Arc

The fundamental operation is a four-stage cycle that applies at any scale:

```
SEE          →    RECOGNIZE      →    PROJECT        →    TEST / REALIZE
(the shape)       (the pattern)        (what should        (candidate →
                                        exist)              judgment →
                                                            editor)
```

### SEE — Multiple Lenses, Convergence as Signal

No single view tells the whole story. The shape becomes apparent when multiple
lenses agree. Each lens reveals a different dimension of the same underlying
structure:

| Lens | What it reveals |
|---|---|
| Frontier graph | Spatial shape — done vs. not-done, where flows break |
| Call tree | Flow shape — how control moves through the system |
| Spotlight | Symbol shape — role, risk, constraints, pattern for one node |
| Knowledge tab | Intent shape — what the design says should exist |
| Doc health | Completeness shape — where documentation has drifted or gone missing |
| Gap analysis | Absence shape — what is missing relative to what is there |
| Corpus synthesis | Architectural shape — subsystems, their connections, structural gaps |

**Convergence is the signal.** When the frontier graph shows an amber node
(functional but calling stubs), the Spotlight shows COORDINATOR role, the
pattern match confirms the shape, and the design notes say coordinators must
not mutate state — that is actionable. One lens alone is noise; three agreeing
is a finding.

### RECOGNIZE — Pattern as Vocabulary

Patterns are the shared vocabulary between observation and action. They answer:
*"What kind of thing is this, and what do things of this kind need?"*

The current pattern vocabulary:
- **Wirfs-Brock RDD roles** — what a component IS (coordinator, controller,
  service-provider, information-holder, interfacer, structurer, pure-fabrication)
- **GRASP principles** — where responsibility BELONGS (information expert,
  creator, controller, protected variations, indirection, pure fabrication)
- **SOTS tenets** — how a component SHOULD BEHAVE (25 tenets from
  shapeofthesystem.com, ingested as design constraints)
- **GoF patterns** — structural/behavioral/creational forms (future)
- **Clean Architecture layers** — boundary detection (future)

When a pattern is recognized, it narrows the space of valid projections.
A COORDINATOR with stub callees should have SERVICE-PROVIDER stubs, not
INFORMATION-HOLDER stubs. The pattern vocabulary makes projections arguable.

### PROJECT — From Shape to Candidate

Projection takes what is recognized and generates what should exist. This is
not invention — it is inference from the available shape.

Current projection tools:
- `project_stub` — generates a candidate function body from calling context
- `match_structural_pattern` — names the pattern the neighborhood conforms to
- `gap_analysis` — brainstorms typed fills (extend/bridge/mirror/consolidate)
- `corpus_synthesis` — maps the whole system and finds structural gaps

The frontier graph is the natural entry point: pick an amber node (the boundary
between working and not-working), open its Spotlight, and all projection tools
are immediately available with context already loaded.

### TEST / REALIZE — Judgment to Editor

A candidate projection is not a fact until it is tested against constraints and
confirmed by the developer.

Current realization path:
1. Spotlight shows role + violations + pattern for the frontier node
2. `project_stub` generates a candidate body
3. `check_design_violations` scores it against design notes and SOTS tenets
4. Developer reviews in the Editor tab
5. Developer confirms, edits, saves — the stub becomes functional
6. `reingest_file` updates the corpus — the frontier advances

**Future realization path (MCTS):**
1. `build_eval_request` constructs candidate evaluation nodes
2. MCTS tree-searches over multiple candidate bodies
3. `execute_eval_request` scores each branch against constraints
4. Best-scoring candidate surfaces in the editor
5. Developer reviews and confirms

The `build_eval_request` / `execute_eval_request` split exists precisely for
this: MCTS can generate many candidates and score them without committing to
LLM calls until it has a promising branch.

---

## The Node Model

Every artifact in the system — a function, a tool, a UI panel, a design
principle — exists in one of these states:

```
STUB          →    PARTIAL        →    FUNCTIONAL     →    COMPLETE
(placeholder,      (exists but         (works for           (full form,
 not working)       incomplete)         core cases)          own stubs
                                                             realized)
```

**COMPLETE does not mean finished.** A complete node has its own connected
stubs — the next ring of the frontier. Completion is local. The map always
extends.

**The frontier is always the boundary between FUNCTIONAL and STUB nodes.**
This is what the frontier graph shows. An amber (frontier) node is FUNCTIONAL
but calls at least one STUB callee. It is where the work is.

### Node States Applied to the Tool Itself

Determined analyzes codebases but is also itself a codebase subject to the
same model. Its own development follows the same arc:

| Layer | State | Notes |
|---|---|---|
| Corpus ingestion | COMPLETE | parse_ast, scan_project_files, reingest_file working |
| Graph construction | COMPLETE | call edges, import edges, subgraph queries |
| Knowledge layer | FUNCTIONAL | design_notes, SOTS, findings, semantic summaries |
| Evaluate kernel | FUNCTIONAL | build/execute split done; ready for MCTS |
| Role inference | FUNCTIONAL | Wirfs-Brock RDD, infer_behavior_batch, cached |
| Design violation check | FUNCTIONAL | SOTS + design_notes, score-filtered |
| Trace data flow | FUNCTIONAL | mutation annotation, role evidence wired |
| Match structural pattern | FUNCTIONAL | subgraph → pattern library |
| Frontier graph | STUB | data exists; UI not yet built |
| Spotlight (extended) | PARTIAL | role + violations added; data flow/pattern on-demand |
| MCTS reasoning | STUB | build_eval_request ready; tree-search not built |
| Self-review | PARTIAL | ran against own corpus; findings filed |
| GRASP vocabulary | STUB | planned; SOTS covers overlap |
| GoF patterns | STUB | future |
| Goal intake | FUNCTIONAL | generates navigation plan from developer goal |
| Corpus synthesis | FUNCTIONAL | 2-pass architectural analysis |
| Gap analysis | FUNCTIONAL | on-demand brainstorm, stores as backlog |
| Editor (read/write) | FUNCTIONAL | open, edit, save, intent analysis |
| Doc health tab | FUNCTIONAL | missing + stale + proposals |
| Bag system | FUNCTIONAL | accumulates findings across session |

---

## The Pipeline — How the Arc Walks in Practice

The complete walkable flow from first look to realized stub:

```
1. ORIENT
   corpus_synthesis → project_status → knowledge_status
   "What is this codebase? What is its shape at the macro level?"

2. FIND THE FRONTIER
   frontier_graph (scoped to a subsystem)
   "Where does working code call non-working code?"

3. PICK A NODE
   Click an amber node → Spotlight opens
   Sections load: intent, risk, role, violations, callers, callees, findings

4. RECOGNIZE THE SHAPE
   Role section: COORDINATOR (85%)
   Pattern section: auto-triggered for COORDINATOR → "pipeline-stage chain"
   Violations section: SOTS XI flagged → ⚑ store

5. PROJECT
   "trace data flow" button → see where the mutation chain breaks
   "project stub" → candidate body generated from calling context

6. TEST
   [future MCTS] → score candidate against pattern + violations
   Editor tab → review candidate, edit, confirm

7. REALIZE
   Save → reingest_file → corpus updated
   Frontier advances → new amber nodes appear
   Repeat from step 2
```

This loop is the core workflow. Every tool in the system exists to serve one
of these seven steps.

---

## The Extension Model

When a new piece is needed — a new tool, a new UI panel, a new analysis
capability — the question is: which step of the arc does it serve?

**Adding a new tool:**
1. Identify which arc step it belongs to (SEE / RECOGNIZE / PROJECT / TEST)
2. Implement the core function (this starts as a stub)
3. Wire into `agent_tools.py` TOOLS dict and `tool_registry.py` REGISTRY
4. Wire into `agent_resolver.py` so the chat agent can invoke it
5. Add to Spotlight if it operates on a single symbol
6. Add to the appropriate tab if it operates on the whole corpus
7. Write regression tests

**Adding a new lens (UI view):**
1. Identify what dimension it reveals (spatial / flow / constraint / absence...)
2. Determine scope: per-symbol (→ Spotlight section) or corpus-level (→ tab)
3. Define the backend socket event and the data shape it returns
4. Build the frontend rendering
5. Wire result → action: what does seeing this make you want to do next?
   That next action should be one click away.

**Adding a new pattern vocabulary:**
1. Define the pattern set as a fixed taxonomy (not ad-hoc)
2. Store patterns as `kind='pattern'` in `knowledge_artifacts`
3. Seed via `_ensure_pattern_library` on first use
4. Wire into `infer_behavior` / `match_structural_pattern` as a new surface
5. Add to `check_design_violations` surfaces if patterns carry constraints

**The path can extend linearly from any node along available paths, or along
a new path that needs to exist.** New paths are legitimate when no existing
path serves the required function. The test: "does this serve a step in the
arc that is currently unserved?" If yes, build it. If the existing path
almost serves it, extend the existing path rather than branching.

---

## Open Paths — Where the System Points Next

Ordered by proximity to the current frontier:

### Immediate (next 1-2 sessions)
- **Frontier graph** — the missing visual entry point to the arc. Data exists;
  needs a new socket event `frontier_graph` and a graph toggle in the UI.
  This is the highest-leverage UI addition: it makes the arc walkable from
  its first step.

### Near-term (3-5 sessions)
- **MCTS reasoning wrapper** — tree-search over `evaluate()` using
  `build_eval_request` / `execute_eval_request`. Enables multi-step
  hypothesis testing. The kernel is ready; the search wrapper is not.
- **GRASP vocabulary** — add Information Expert, Creator, Protected Variations,
  Controller, Pure Fabrication, Indirection as named constraints in
  `check_design_violations`. Makes violation findings arguable by name
  rather than by similarity score alone.
- **Spotlight → Editor flow** — when `project_stub` generates a candidate,
  it should land directly in the Editor tab at the right line, ready to
  accept or modify. The stub projection already opens source; needs to
  pre-fill the edit textarea.

### Medium-term (6-10 sessions)
- **Standards-grounded self-review (ongoing)** — run Determined against itself
  each time a major capability is added. Findings feed back as design notes.
- **GoF pattern library** — structural (adapter, facade, proxy), behavioral
  (strategy, observer, command), creational (factory, builder). Cross-reference
  with Wirfs-Brock roles to deepen recognition vocabulary.
- **Dj2 design validation** — use Determined's full capability against the
  game codebase. The Architectural Constitution already embodies GRASP without
  naming it. Determined should be able to confirm and annotate those boundaries.

### Long-term
- **Full MCTS realization** — adaptive investigation: the agent pursues a
  violation thread across multiple symbols without the developer directing
  each step. Same UI, smarter reasoning underneath.
- **Projection confidence scoring** — when `project_stub` generates a candidate,
  score it against the pattern library and design constraints automatically.
  Surface confidence alongside the suggestion.
- **Cross-codebase pattern transfer** — when a pattern is recognized in one
  corpus, it can seed the pattern library for another. Determined's knowledge
  of dj2 informs analysis of a new project with similar architecture.

---

## Design Principles (Governing Decisions)

When a judgment is needed about a new piece, these principles govern:

1. **Every tool serves a step in the arc.** If it doesn't clearly serve SEE,
   RECOGNIZE, PROJECT, or TEST, it doesn't belong in the core system.

2. **Lenses compose; they don't duplicate.** A new lens reveals a dimension
   not covered by existing lenses. Adding a third call-graph view when two
   already exist is not a lens — it's noise.

3. **Results are actionable.** Every finding should have a natural next step
   one click away. A finding that just sits in the UI without a path forward
   is incomplete.

4. **The frontier advances, it doesn't reset.** Each realized stub reveals
   new stubs. The map extends. A session that doesn't advance the frontier
   (even by one node) has not completed the arc.

5. **The kernel stays thin.** `evaluate()` / `build_eval_request()` /
   `execute_eval_request()` are the fundamental reasoning primitives.
   Everything else composes from them. Do not embed reasoning logic in
   higher layers.

6. **Patterns must be sourced.** Any classification scheme or taxonomy used
   by the tool must trace to a documented, general-purpose source (Wirfs-Brock,
   GRASP, SOTS, GoF, Clean Architecture). Project-specific taxonomies rot.

7. **The UI shows the shape; the agent follows it.** The UI's job is to make
   the shape visible and the next step obvious. The agent's job is to do the
   reasoning. Neither should do the other's job.

---

_Last updated: 2026-07-03 (session 60)_
_Update this document when: a new capability is added, a design decision is
made, an open path is realized or abandoned, or the arc changes shape._
