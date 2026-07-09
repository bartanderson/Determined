# Determined — Analysis Model

_Consolidated from DESIGN_ARC.md, DISCOVERY_MODEL.md, REASONING_MODEL.md (session 124, 2026-07-08)._
_Authoritative over session notes. Update when capabilities change shape._

---

## The Objective

Determined is a developer intelligence tool. Its purpose is to help a developer understand a
codebase at any level of completion — from a blank architecture to a fully realized system —
and to close the gap between what exists and what should exist by following the natural shape
of the code.

The tool does not prescribe. It reveals. The developer sees the shape of what is there,
recognizes patterns, projects those patterns into what is missing, tests the projections
against design intent, and then realizes them — one node at a time.

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

No single view tells the whole story. Convergence is the signal — when multiple lenses
agree, that is a finding.

| Lens | What it reveals |
|---|---|
| Frontier graph | Spatial shape — done vs. not-done, where flows break |
| Call tree | Flow shape — how control moves through the system |
| Spotlight | Symbol shape — role, risk, constraints for one node |
| Knowledge tab | Intent shape — what design says should exist |
| Doc health | Completeness shape — where documentation has drifted |
| Gap analysis | Absence shape — what is missing relative to what is there |
| Discovery mode | Architectural shape — subsystems, connections, structural gaps (AI-narrated) |

### RECOGNIZE — Pattern as Vocabulary

Patterns answer: *"What kind of thing is this, and what do things of this kind need?"*

- **Wirfs-Brock RDD roles** — what a component IS (coordinator, controller, service-provider,
  information-holder, interfacer, structurer, pure-fabrication)
- **GRASP principles** — where responsibility BELONGS (information expert, creator, controller,
  protected variations, indirection, pure fabrication)
- **SOTS tenets** — how a component SHOULD BEHAVE (25 tenets, ingested as design constraints)
- **GoF patterns** — structural/behavioral/creational forms (future)
- **Clean Architecture layers** — boundary detection (future)

### PROJECT — From Shape to Candidate

Current projection tools: `project_stub`, `match_structural_pattern`, `gap_analysis`, Discovery mode.

### TEST / REALIZE — Judgment to Editor

1. Spotlight shows role + violations + pattern for the frontier node
2. `project_stub` generates a candidate body
3. `check_design_violations` scores it against design notes and SOTS tenets
4. Developer reviews, edits, saves
5. `reingest_file` updates the corpus — the frontier advances

---

## The Node Model

Every artifact in the system exists in one of these states:

```
STUB          →    PARTIAL        →    FUNCTIONAL     →    COMPLETE
(placeholder,      (exists but         (works for           (full form,
 not working)       incomplete)         core cases)          own stubs realized)
```

**COMPLETE does not mean finished.** A complete node has its own connected stubs — the next
ring of the frontier. Completion is local. The map always extends.

**The frontier is the boundary between FUNCTIONAL and STUB nodes.** An amber (frontier) node
is FUNCTIONAL but calls at least one STUB callee. It is where the work is.

---

## The Five Navigation Concepts

These concepts form the navigation layer of Determined. They connect the arc steps to
concrete queries, UI views, and planning decisions.

### 1. Topology

The *shape* of a program's incompleteness. Different topologies imply different queries and
fix strategies.

| Shape | Description |
|---|---|
| Direct-call | Functional code calls a stub by name; edges exist in call graph |
| ABC-interface | Abstract methods on a base class; no concrete override exists |
| Orphaned-impl | Implemented function whose callers are all stubs or missing (anticipatory vs. stranded) |
| Chain | Stub calls another stub; incompleteness propagates (head/middle/tail have different priorities) |
| Disconnected | Stubs with no callers and no callees |
| Conditional-stub | Non-stub function with `raise NotImplementedError` inside a branch |

Tool: `detect_topology()` returns shape inventory. `frontier_priority()` composites multi-shape scoring.

### 2. Frontier

The boundary between implemented and unimplemented code. Each topology has its own frontier type.
The frontier tab supports Direct / Chain / All / ABC modes.

Tool: `frontier_coverage()` — reports stub-gated count, orphaned count, pressure signal (HIGH/MODERATE/LOW).

### 3. Implementation Queue

The frontier ranked by unblocking value — which stub, when implemented, enables the most
downstream progress.

- `list_stubs()` ranks by caller in-degree + chain depth (recursive CTE)
- `score_stub()` adds evaluate() semantic verdict + confidence
- `frontier_to_queue` socket event pushes ranked stubs into `workflow_items`

**The MCTS connection:** tree nodes = stubs; edges = "implementing A unblocks B"; leaf value =
caller count + chain depth + evaluate() judgment. `build_eval_request` / `execute_eval_request`
already split for this. Q4 (tree search) deferred pending RM9.

### 4. Access Paths

A single function can be reached via multiple methods of travel: direct name call, module prefix,
import alias, self-method, type annotation, runtime binding, inheritance, chained attribute.

The frontier query's suffix-match JOIN is a partial fix. `is_project_call` column on `graph_edges`
(not yet added) would lift accuracy across all graph features. `symbol_context()` is the backbone
for any UI sub-menu showing "also known as" paths.

### 5. Waypoints

Pinned discoveries that carry their discovery context — not just "I pinned this" but "I found
this via the frontier graph as a stub with 5 callers, arriving from Topology."

Schema: `knowledge_artifacts` with `kind='waypoint'`, content = JSON `{name, view_origin, note,
verdict, confidence, trail}`. Survives re-ingest. Auto-waypoint fires on confirmed evaluate()
findings. Surfaces in Pins tab.

---

## The Reasoning Architecture

For architectural decisions too complex for a single evaluate() call, the pipeline decomposes
the question into sub-questions, answers each deterministically or with focused LLM calls,
and synthesizes the results.

```
Goal / architectural question
        |
        v
[Decomposer] (8B, one call)
  "What sub-questions do I need to answer this?"
        |
        v
Ordered sub-question list + routing hints (db | evaluate)
        |
        v
For each sub-question:
  [Router] (deterministic code)
    ├─ DB query → answer (deterministic, no LLM)
    └─ evaluate() call → verdict + confidence (3B, focused)
        |
        v
Assembled findings: [(question, answer, source, confidence), ...]
        |
        v
[Synthesizer] (8B, one call)
  "Given these N concrete findings, what is the recommendation?"
        |
        v
Recommendation + confidence + reasoning + provenance
```

Most reasoning is done by DB queries. Models provide judgment at two narrow points: decomposing
the question and synthesizing findings. Neither requires understanding the whole codebase.

Implemented as `reasoning_engine.py` (R1/R2/R3) + `reason_about` agent tool (R4) + Reason button
in Frontier tab (R5). Reasoning chains persisted as `kind='reasoning_chain'` in `knowledge_artifacts`.

---

## The Extension Model

**Adding a new tool:**
1. Identify which arc step it belongs to (SEE / RECOGNIZE / PROJECT / TEST)
2. Implement core function (starts as a stub)
3. Wire into `agent_tools.py` TOOLS dict and `tool_registry.py` REGISTRY
4. Wire into `agent_resolver.py` for chat invocation
5. Add to Spotlight if per-symbol; add to appropriate tab if corpus-level
6. Write regression tests

**Adding a new lens (UI view):**
1. Identify what dimension it reveals (spatial / flow / constraint / absence...)
2. Determine scope: per-symbol (→ Spotlight section) or corpus-level (→ tab)
3. Define the backend socket event and data shape
4. Build frontend rendering
5. Wire result → action: what does seeing this make you want to do next? One click away.

**Adding a new pattern vocabulary:**
1. Define as a fixed taxonomy (not ad-hoc)
2. Store as `kind='pattern'` in `knowledge_artifacts`
3. Seed via `_ensure_pattern_library` on first use
4. Wire into `infer_behavior` / `match_structural_pattern`
5. Add to `check_design_violations` if patterns carry constraints

---

## Design Principles

1. **Every tool serves a step in the arc.** If it doesn't clearly serve SEE, RECOGNIZE,
   PROJECT, or TEST, it doesn't belong in the core system.

2. **Lenses compose; they don't duplicate.** A new lens reveals a dimension not covered
   by existing lenses. A third call-graph view is not a lens — it's noise.

3. **Results are actionable.** Every finding should have a natural next step one click away.
   A finding that sits in the UI without a path forward is incomplete.

4. **The frontier advances, it doesn't reset.** Each realized stub reveals new stubs. A
   session that doesn't advance the frontier (even by one node) has not completed the arc.

5. **The kernel stays thin.** `evaluate()` / `build_eval_request()` / `execute_eval_request()`
   are the fundamental reasoning primitives. Everything else composes from them.

6. **Patterns must be sourced.** Any classification scheme must trace to a documented,
   general-purpose source (Wirfs-Brock, GRASP, SOTS, GoF, Clean Architecture).
   Project-specific taxonomies rot.

7. **The UI shows the shape; the agent follows it.** The UI makes shape visible and the
   next step obvious. The agent does the reasoning. Neither should do the other's job.
