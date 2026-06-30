UI Vision — Determined Dev Console
=====================================

_Written 2026-06-30. Authoritative design intent for the UI layer.
For backend architecture, see DESIGN.md. For open items, see TRACKER.md._

---

## The GOT metaphor (the design north star)

The Game of Thrones title sequence: a mechanical clockwork map where
interconnected gears, wheels, and levers reveal a world. Every location
is a mechanism. Every mechanism connects to others. You navigate by
moving through the world, not by typing its name into a search box.

Applied to this tool: the codebase is the world. Functions, files,
modules, findings, design notes, risk scores, call chains — these are
the gears. The UI's job is to make those gears visible and let Bart
turn them, feel the resistance, and see what moves.

**What this is NOT:** a query interface. A query interface is the
degraded fallback when the system doesn't know enough about its own
surfaces to present them naturally. The chat input stays — it handles
open-ended questions — but it should be hidden by default and revealed
only when natural navigation doesn't answer the question.

---

## Surfaces — what exists in the system

These are the named, queryable surfaces the backend already provides.
Each one is a gear. The UI's job is to expose every gear directly,
not just through typed queries.

### Structural surfaces (deterministic, no LLM)
- **Symbol** — declaration, type, file, line, risk (HOT/WARM/SAFE), docstring
- **Call edge** — caller → callee, file, line, resolved flag
- **File** — path, role, hot flag, stub flag, import list, symbol list
- **Import graph** — file-level dependency structure
- **Class attributes** — self.x assignments with inferred types
- **Contract violations** — drift signals, lifecycle state per symbol
- **Stubs** — defined but unimplemented symbols

### Semantic surfaces (LLM-derived, cached)
- **Distilled summary** — one-sentence compression per file
- **Semantic summary** — full LLM description per file
- **Design notes** — extracted invariants, authority rules, forbidden patterns
- **SOTS tenets** — 25 Shape of the System principles, cosine-searchable
- **Knowledge artifacts** — findings, strategy decisions, known issues

### Analysis surfaces (computed, hybrid)
- **Risk profile** — HOT/WARM/SAFE per symbol with reasons
- **Design frame** — SOTS tenets that apply to this symbol (cosine match)
- **Design violations** — code behavior vs. documented constraints
- **Goal intake plan** — navigation plan for a stated developer intent
- **Gap summary** — docstring/distillation/design note coverage by module
- **Docstring proposals** — LLM-proposed fills for missing/stale docstrings
- **Gap analysis** — brainstormed fills for structural gaps (idea mode)
- **Concept search** — cross-surface semantic search (symbols, docs, notes)
- **Symbol context** — unified single-call view: declaration + risk + callers
  + callees + class attrs + design frame + findings

### Navigation surfaces
- **Call tree** — recursive caller/callee expansion per symbol
- **Symbol graph** — N-hop neighborhood around a symbol (Cytoscape)
- **Import graph** — file-level dependencies (Cytoscape)
- **Corpus map** — entry points (Roots) + most-called (Core) with risk badges
- **Trail** — breadcrumb history of visited symbols
- **Bag** — accumulated session context (symbols, files, edges, findings)
- **Workflow queue** — next_up and backlog items from tools

### Edit surfaces
- **Editor** — file viewer with symbol sidebar, line navigation, edit mode
- **Docstring write-back** — accept a proposal → write to source file
- **Save** — in-place file edit
- **Intent analysis** — describe intent on a file, populate bag

---

## Current UI vs. vision: the delta

### What works well
- Spotlight panel: click any symbol anywhere → rich detail panel opens.
  Risk badge, callers, callees, findings, source view, action buttons. This
  IS the GOT gear model working locally. The problem is it's only reachable
  by clicking a symbol that appeared in a chat answer.
- Call tree tab: directly navigable, expandable, works.
- Graph tab: Cytoscape, clickable nodes → spotlight. Works.
- Imports tab: file-level graph, clickable. Works.
- Editor tab: file open, symbol sidebar, line scroll. Works.
- Doc health tab: proposals with accept/dismiss. Works.

### What's broken or missing

**1. Search is the primary interface — it should be the last resort.**
The chat input is always visible and the sidebar shortcuts are just
canned chat queries. The system knows its own surfaces; it should
present them without waiting to be asked.

**2. No direct entry to most tools.**
`goal_intake`, `concept_search`, `gap_analysis`, `ingest_design_docs`,
`reingest_file`, `distill_corpus` — none have a UI surface. You reach
them only by hoping the right natural-language phrase triggers the right
pattern in detect_pattern. That's fragile and invisible.

**3. The editor is not a navigation surface.**
Opening a file shows you the code. But clicking a function call in the
code does nothing. The editor is a viewer, not a navigator. You cannot
move from a call site to the called function. The symbol sidebar scrolls
to a line but doesn't open the spotlight or seed the call tree.

**4. The chat answer is the end of the road.**
Every query result is a text block. Symbol names in the result are
clickable (they open the spotlight) — this is good. But structured data
(call lists, file lists, finding lists) comes out as prose and loses
its structure. There's no way to see a caller list as a navigable list
of items, each with its own drill-down.

**5. No knowledge layer browser.**
`knowledge_artifacts` (design notes, findings, SOTS tenets) cannot be
browsed directly. You can search them via concept_search through chat,
but you can't open a panel and see "all design notes for this module" or
"all findings provenance=human-confirmed." This is the most important
surface for design governance and it has no UI at all.

**6. No workflow queue UI.**
The `workflow_items` table accumulates next_up and backlog proposals from
docstring_health, gap_analysis, and goal_intake. The Doc health tab shows
docstring proposals. But the general workflow queue — backlog items,
gap proposals — has no UI. Items accumulate invisibly.

**7. Context switches are not intuitive.**
The trail breadcrumb helps (symbol → symbol → symbol) but it's one-
dimensional. There's no way to switch between "I'm in the context of
module X's design" and "I'm tracing a specific call chain" and "I'm
reviewing gap proposals" as distinct modes that each present the right
surfaces.

**8. No transparency in the query pipeline.**
When you ask a question via chat, you don't see: which pattern matched,
which tools ran, what they returned, what the 3B model synthesized. If
the answer is wrong, there's no way to know where it went wrong.

---

## The desired navigation model

### Primary navigation: surfaces present themselves

On corpus load, the UI should immediately show:
- Corpus map (already done — Roots/Core with risk badges)
- Gap summary (DB-only, fast) embedded in the sidebar
- Workflow queue count (how many next_up items pending)

Every element on screen should have implied affordances:
- **Hover** → quick preview (file: distilled summary; symbol: docstring +
  risk + caller count; finding: content preview)
- **Single click** → open detail panel (spotlight for symbols, file panel
  for files, artifact card for findings)
- **Double click / expand** → navigate into (open file in editor, expand
  call tree node, show full artifact)
- **Right click / long press** → context menu with typed actions:
  "trace callers", "find similar", "check design violations",
  "add to bag", "store finding"

### Editor as navigation hub

The editor should be the primary way to explore code:
- Every function/class name in the code is a clickable link
- Clicking a function call in the code navigates to that function's
  definition (open file, scroll to line) and opens the spotlight
- The symbol sidebar in the editor seeds the call tree and graph on click
- "Analyze intent" result opens a structured panel, not just a chat block
- Risk badges appear inline in the gutter next to HOT/WARM symbols

### Structured result panels (not prose)

When a tool returns a list — callers, files, findings, gap proposals —
the UI should render it as a navigable list, not folded into prose:
- Each item in a caller list is a row: caller name (clickable → spotlight),
  file (clickable → editor), line number, resolved flag
- Each finding is a card: kind badge, subject link, content, provenance badge
- Each gap proposal is a card: proposed fill, confidence, accept/dismiss

### Knowledge layer panel (new)

A dedicated panel (sidebar section or new tab) that lets Bart browse:
- Design notes by module — expandable tree
- Knowledge artifacts by kind (file_purpose / design_note / known_issue /
  strategy_decision) — filterable list
- SOTS tenets — all 25, with "find code that touches this" button per tenet
- Workflow queue — next_up and backlog items, with accept/dismiss/defer

### Query transparency panel

When a chat query runs, show alongside the answer:
- Which pattern matched (or "no pattern — LLM synthesis")
- Which tools were called, in order
- Whether each tool returned results or was empty
- Elapsed time per tool

This makes the black box visible and lets Bart see when a query is going
through the wrong path.

---

## Proposed surface layout (revised shell)

```
┌─ topbar ──────────────────────────────────────────────────────────┐
│  Determined  —  [db-badge]              [model]  [queue-badge]    │
└───────────────────────────────────────────────────────────────────┘
┌─ sidebar ────────┐ ┌─ main panel ─────────────────────────────────┐
│                  │ │                                               │
│  [Corpus map]    │ │  [tab bar]                                    │
│  Roots / Core    │ │  Chat | Call tree | Graph | Imports |         │
│  with risk       │ │  Bag | Editor | Doc health | Knowledge        │
│                  │ │                                               │
│  [Gap summary]   │ │  [trail bar]                                  │
│  module gaps     │ │  Symbol A → Symbol B → Symbol C   [clear]    │
│  at a glance     │ │                                               │
│                  │ │  [active tab panel]                           │
│  [Workflow]      │ │                                               │
│  N next_up       │ │                                               │
│  M backlog       │ │                                               │
│                  │ │                                               │
│  [Quick actions] │ │                                               │
│  work queue      │ │                                               │
│  dead code       │ │                                               │
│  unexplored      │ │                                               │
│  discover        │ │                                               │
│  docstrings      │ │                                               │
│  todos           │ │                                               │
│                  │ │                                               │
│  [Ask ▾]         │ │  [spotlight panel — right overlay]            │
│  (hidden query   │ │  symbol name  [HOT]  ✕                        │
│   bar)           │ │  [full brief] [trace] [violations] [source]  │
│                  │ │  Risk / Intent / Callers / Calls / Findings   │
└──────────────────┘ └───────────────────────────────────────────────┘
┌─ statusbar ────────────────────────────────────────────────────────┐
│  ● connected  ·  [db-name]  ·  [pipeline trace: last query]       │
└────────────────────────────────────────────────────────────────────┘
```

---

## Build order (toward the vision)

These are in priority order — each one is self-contained and improves
navigability independently.

**1. Editor as navigator (highest leverage)**
Wire function-call tokens in the code view to their definitions.
Click a name in code → navigate to that symbol (open file, scroll to
line, open spotlight). The editor already has the symbol list; use it
to annotate the rendered code with links.

**2. Structured result rendering**
When agent_tools returns a list (callers, files, findings), render it
as an interactive list in the chat panel, not prose. Each item is a row
with click affordances.

**3. Knowledge panel (new tab)**
Browse knowledge_artifacts, design_notes, workflow_items directly.
Filterable by kind, scoped by module. "Find code that touches this"
button per design note (fires concept_search).

**4. Direct tool access panel**
Replace the "Ask ▾" toggle with a structured tool picker:
tools grouped by category, each with an inline parameter form.
No natural-language required for named tools.

**5. Query transparency**
Show pipeline trace alongside every chat answer: pattern matched,
tools called, results per tool. One click to expand.

**6. Sidebar gap summary auto-display**
Run _gap_summary_block() on corpus load and show inline in sidebar.
No query needed.

**7. Workflow queue in sidebar**
Count badge on queue items, click to expand list, accept/dismiss inline.

---

## What this document is for

Use it to evaluate every UI change: does this make a surface more
directly reachable, or does it add another layer of indirection?
The test is: can Bart navigate from any surface to any related surface
in one or two clicks, without typing? If not, the connection is missing.
