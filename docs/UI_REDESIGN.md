UI Redesign — Shape-First Shell
================================

_Written 2026-07-19 (session 219), at the CLOSURE.md gate. Supersedes the
"delta" and "build order" sections of UI_VISION.md; the GOT metaphor and
surface inventory there remain authoritative. This is a sketch for pressure,
not a spec._

---

## Why now, and what the assessment found

CLOSURE.md's gate is fully checked. The gate text names the headline:
"the judgment layer outputs (corpus shapes) are the thing no other static
analysis tool shows." The session-219 assessment of the current UI against
the GOT criterion found:

1. **Frontier self-presents well** — default tab, auto-loads, actionable.
   The one surface that already behaves like the vision.
2. **Corpus map + gap summary regressed** — rendered on load but hidden,
   because `corpus_ready` auto-switches the sidebar to the Navigate rail
   section, which doesn't contain them. Two features that were each fine
   alone (rail sections; auto-switch) combined into a state-interaction bug.
3. **Editor opens empty** — "No file open." The nav hub is a dead end as a
   starting point.
4. **Shape (the headline) is least discoverable** — buried in the More
   overflow, blank until clicked.
5. The judgment projections are **deterministic and cheap** (DB + SetFit,
   no LLM — verified in corpus_projections.py). Nothing prevents them from
   self-presenting on load.

## Grounding (SOTS tenets live for this decision)

- **XXI Simplicity is the budget.** The current shell has 17 tabs, 5 rail
  sections, 3 modes, quick actions, and a guide layer — accreted tool-by-tool.
  The corpus-map bug was a state-interaction bug: the rail-section state
  machine had more states than the design needed. The redesign deletes
  shell states before adding any. Fewer states, not more guards.
- **XIV One source of truth.** Corpus stats currently render in two places
  (nav stats line + corpus map header) owned by two code paths. In the new
  shell every surface has exactly one owner region; every other appearance
  is a link to it, never a copy.
- **I Locality of reasoning**, applied to the user: what must Bart hold in
  his head to navigate? Today: which rail section holds which panel, which
  mode highlights which tabs, which tab is in the overflow. The GOT model
  is locality — everything reachable from what's visible, 1-2 clicks, no
  memorized topology.
- **XX Reversibility.** "Don't patch piecemeal" (redesign intent) pulls
  against the big-bang-rewrite trap. Resolution: the tab panels and their
  loaders (fgLoad_, shapeRun, knLoad, spotlight, editor internals) are
  sound modules — the **shell** (tab bar, rail sections, modes, on-load
  behavior) is what's being replaced. Strangler-fig: new shell, existing
  panel guts, phased and shippable at each step.

Tension named: XXI (delete surfaces) vs. the UI-CLI parity principle
(TRACKER: every capability reachable from UI). Resolution: parity means
*reachable*, not *prominent*. Workbench remains the 100%-coverage backstop;
the shell's job is the judgment story. Inputs here are self-controlled
(Bart is the user), so per SOTS the weighting favors cognitive load over
blast radius.

---

## The design in one sentence

On corpus load the UI answers, unprompted: **what is this system trying to
become, what's blocking it, what's dead, and where do I act** — and every
claim in that answer is a gear you can click to drill one level down.

## Three altitudes (the navigation spine)

The redesign organizes every surface by altitude. Navigation is vertical:
click a claim to descend; breadcrumb/trail to ascend.

- **Corpus** — shape verdicts, ghost map, corpus map, feature list, gaps.
- **Subsystem / feature** — subsystem verdict, feature_shape, module filter,
  prerequisite clusters.
- **Symbol** — spotlight, call tree, graph neighborhood, blast radius,
  editor at line, classification evidence.

Every judgment claim carries its evidence chain downward: subsystem verdict
→ the stubs that produced it → each stub's classification → its file/line
in the editor. That chain is the GOT gear train, and it already exists in
the tools — the shell just has to stop dropping it between panels.

## The shell

```
┌─ topbar ────────────────────────────────────────────────────────────┐
│ Determined · [corpus]   158 files · 56 hot · 13 stubs   [LLM] [⚙]  │
└─────────────────────────────────────────────────────────────────────┘
┌─ structure column ─┐ ┌─ main stage ──────────────────────────────────┐
│ (narrow, fixed —   │ │ Shape ▸ | Frontier | Map | Editor | Knowledge │
│  no section        │ │ | Workbench | ⌕                               │
│  switching)        │ │                                                │
│                    │ │ [trail bar: corpus ▸ world/ ▸ WorldAI.__init__]│
│ CORPUS MAP         │ │                                                │
│  Roots / Core      │ │ ┌─ SHAPE (home, auto-runs on load) ─────────┐ │
│  module chips      │ │ │ VERDICT STRIP (one line per live finding) │ │
│  risk badges       │ │ │ · world/ dead-concept dominant (6/10)     │ │
│                    │ │ │ · CombatFSM [GHOST] — 4 stubs reference it│ │
│ GAPS               │ │ │ · 6 stubs actionable → Frontier           │ │
│  docs 43%          │ │ │ ├──────────────┬──────────────┤           │ │
│  distilled 0%      │ │ │ │ File shape   │ Subsystem    │           │ │
│  1 design note     │ │ │ │ (density,    │ shape        │           │ │
│                    │ │ │ │  dominant)   │ (verdicts)   │           │ │
│ ORACLE             │ │ │ ├──────────────┼──────────────┤           │ │
│  last verdict      │ │ │ │ Prereq map   │ Ghost map    │           │ │
│  (cached) [Run]    │ │ │ │ (build order)│ (dead/live)  │           │ │
│                    │ │ │ └──────────────┴──────────────┘           │ │
│                    │ │ └───────────────────────────────────────────┘ │
│                    │ │            [spotlight — right overlay, kept]  │
└────────────────────┘ └───────────────────────────────────────────────┘
```

Every panel gets the focus/popout treatment the editor already has
(redesign notes: controllable panels, focus/popout surfaces, narrow
peripheral controls). The structure column is the only always-visible
peripheral; it never switches sections.

## Tab consolidation (17 → 7)

| New tab | Absorbs | Notes |
|---|---|---|
| **Shape** (home) | Shape + verdict strip + Design Oracle result | Auto-runs on load (deterministic). Progressive per-quadrant fill. |
| **Frontier** | Frontier + Build queue + Doc health | All three are "work to do" lenses over the same intent. Lens selector inside the tab. |
| **Map** | Graph + Imports + Call tree + Topology | All graph views over the same corpus; one surface, view selector, seeded by trail context. |
| **Editor** | Editor (+ file tree) | Opens with a file tree / recent-files list from the DB so it self-presents. Stays the symbol-level nav hub. |
| **Knowledge** | Knowledge + Pins + Bag | Accumulated-context surfaces: artifacts, pinned clues, session bag. |
| **Workbench** | Workbench | Parity backstop — every tool, grouped forms. Unchanged. |
| **⌕ (Ask)** | Chat | Hidden-by-default query bar per the vision; icon tab, not a word. |

Dissolved entirely: rail sections (single fixed structure column), the
three modes (Design/Trace/Review — redundant once altitude + consolidation
land; their highlight sets map onto Shape/Map/Frontier respectively),
Tour + Discovery + Logs move behind the ⚙ utility menu (Tour is
Commonplace-scoped; Logs is diagnostics; neither is corpus navigation).

Deletion candidates are the point, not a side effect (XXI): mode CSS,
rail-section state machine, `_startupFiredFor` auto-switch logic, the
duplicated stats line, quick-actions block (its five entries become links
in the surfaces that own them).

## The on-load contract (the gate criterion, made structural)

`corpus_ready` produces, with zero user action, in order of paint:

1. Structure column populates: corpus map (Roots/Core/chips), gaps, cached
   oracle verdict. No auto-switch — there is nothing to switch.
2. Shape home fires `shape_run` automatically; quadrants fill as each
   projection returns; verdict strip synthesizes deterministically from
   the four results (no LLM).
3. Frontier tab shows its count badge (stubs actionable) without being
   opened.
4. Editor preloads the file tree (DB `files` table — no scan).

There is exactly one layout state on load. The corpus-map regression class
of bug — "rendered but hidden by a sibling state machine" — becomes
unrepresentable because the shell no longer has hidden-section states (III
applied to UI state).

## What is explicitly kept

- **Spotlight** — the symbol-level gear that already works. Unchanged.
- **Frontier auto-load** — the pattern the rest of the shell is being
  brought up to.
- **A3 module chips, B3 blast radius render, G1 workbench forms** — recent
  wins carry over into their new homes.
- **Corpus loading flow** (UI_VISION session-123 section) — unchanged.

## Phasing (each step shippable, XX)

- **Phase A — Shape-first home + one sidebar.** Move Shape to first
  position, auto-run on load, add verdict strip. Collapse rail sections
  into the fixed structure column; delete the auto-switch. Kill the
  duplicate stats line. _This alone meets the gate criterion._
- **Phase B — Consolidation.** Merge Frontier/Build queue/Doc health;
  merge the four graph views into Map; fold Pins+Bag into Knowledge;
  delete modes; move Tour/Discovery/Logs behind ⚙.
- **Phase C — Editor self-presentation + gear polish.** File tree on open;
  evidence-chain drill-down from verdict strip to editor line; panel
  focus/popout generalized.

Phase A is small (shell wiring, no new backend). Phase B is the bulk
(HTML/JS moves, one new lens selector, no engine changes). Phase C touches
one new server query (file tree) and the drill-down plumbing.

## Open questions (for pressure before Phase A)

1. Verdict strip synthesis: deterministic template over the four projection
   outputs, or is a one-shot LLM summary worth the latency/dependency?
   (Sketch assumes deterministic; LLM adds a narrative layer later.)
2. Frontier/Doc-health merge: doc proposals are accept/dismiss workflow,
   stubs are navigate-and-implement. Same tab, or does Doc health belong
   under Knowledge instead?
3. Does the Design Oracle stay in the structure column (cached verdict +
   Run) or become a fifth card on the Shape home?
4. Map merge: Call tree is a tree widget, not Cytoscape — merging it into
   Map may cost more than the tab it saves. Keep as its own view or leave
   Call tree standalone?
