# UI Evaluation — Against Canonical dj2 Use Cases

Written 2026-07-19. Persistent record of UI capability, gaps, and proposed improvements
evaluated against the six canonical probe questions for the dj2 corpus.

Replaces ephemeral per-session notes. Update in place as items are resolved.

---

## Evaluation frame

The six canonical questions (from CLOSURE.md Phase 2 / RM67):

1. **Entry points** — what are the roots of this codebase?
2. **Blast radius** — if I change X, what breaks?
3. **Feature shape** — how complete is a feature area?
4. **Stubs** — where are the unimplemented gaps?
5. **Design drift** — does this code match its stated design intent?
6. **Call chains** — how does control flow from A to B?

Evaluation criterion: can Bart answer each question *without typing into the chat bar*?
The chat bar is the last resort. If the answer requires it, that is a gap.

---

## Q1 — Entry points

**Current UI path:** Navigate rail → corpus map sidebar → Roots section.
Shows top ~8 entry points by fan-out with ↗ counts. Click any symbol → Spotlight panel.

**Works:** Top-N view is correct and fast. dj2 Roots correctly surfaces CharacterCreator.renderStep,
world.sendWorldCommand, generate_loot, init_session_and_dungeon as dominant EPs.

**Gaps:**
- No "show all 93" expansion. Only the top 8-10 are visible. There is no paginated or
  scrollable list of all entry points in the Navigate surface.
- HTTP routes vs inferred EPs are not visually distinguished in the Roots list.
  (dj2 has both; the type difference is lost in the flat display.)
- No filter by file/module. Can't ask "entry points in world/" from Navigate.

**Proposed fixes:**
- A1: "Show all →" link below the Roots section that opens a full EP list in the frontier tab
  filtered to EP-type (no stub filter, just the EP list). One click, no chat.
- A2: Route badge on HTTP entries (🌐) vs inferred (⚙). Already have `badge` in the
  payload; just not rendered in the map list items.
- A3: Module filter chip row above Roots: chips auto-generated from EP file prefixes.
  Click "world/" → filter Roots to that module.

---

## Q2 — Blast radius

**Current UI path:** Tools rail → Navigate section → "Show everything known about a symbol"
(symbol_context shortcut). Returns a structured result including callers.
Alternatively: Tools rail → Query section → "List every function that calls this one —
blast radius before you change it" (caller list shortcut).

**Works:** The Tools panel has a direct blast_radius path. result comes back as a
structured caller list via tryStructuredRender(). Clickable rows. Works.

**Gaps:**
- The label "List every function that calls this one" does not say "blast radius".
  Discoverability: a developer who knows to ask about blast radius won't find this by label scan.
- No risk badge on the result rows. The caller list shows names but not HOT/WARM/SAFE on the
  callers themselves — so you can't immediately see if the callers are themselves hot.
- No "upstream blast radius" vs "downstream blast radius" distinction in the UI.
  (blast_radius returns direct + extended; extended is shown as a count, not a list.)

**Proposed fixes:**
- B1: Rename shortcut label to "Blast radius — who calls this, risk before changing".
- B2: Show risk badge color on each caller row in the structured result.
- B3: Add a "extended impact: N symbols" expandable section that renders the extended
  impact list (currently just a count in the text output).

---

## Q3 — Feature shape

**Current UI path:** None. feature_shape and list_features have no direct UI surface.
The Shape tab (Corpus Shape) runs judgment-layer projections (file density, subsystem
verdicts, prerequisite map, concept ghost map) — related but different from feature_shape
BFS completeness.

To answer "how complete is world/", today you must: type in chat, or use Workbench tab
and type the tool name manually.

**This is the biggest gap.**

**Gaps:**
- No Navigate entry for list_features or feature_shape.
- Shape tab runs corpus_shape (RM69 judgment layer), not feature_shape (BFS completeness).
  These answer different questions. The tab label "Shape" conflates them.
- Workbench tab exists but requires knowing the tool name. Not discoverable.

**Proposed fixes:**
- C1: Add a "Feature areas" block to the Navigate sidebar. On corpus load, run list_features
  and render as a compact directory tree with stub counts. Each row clickable →
  feature_shape BFS result in a panel. No chat needed.
- C2: Split the Shape tab into "Corpus shape" (RM69 judgments) and "Feature map" (BFS
  completeness per directory). Or add "Feature map" as its own tab in the tab bar.
- C3: Workbench tool picker should show list_features and feature_shape in its tool list
  with inline parameter forms (feature_path input). Currently the tool picker is not
  consistently populated.

---

## Q4 — Stubs

**Current UI path:** Frontier tab. Loads automatically. Shows stubs by type (Direct,
Chain, ABC, Orphan). Design mode and Trace mode both route here. Works.

**Works best of all six questions.** The stub surface is complete:
- Direct stubs: caller→stub edges, ranked by caller count
- Chain stubs: stub→stub dependency
- ABC gaps: interface incomplete
- Orphan: disconnected
- Corpus Shape tab adds judgment-layer classification (RM69)

**Gaps:**
- Stub judgment (classify_stub output) is visible only via Spotlight "Score" button or
  Corpus Shape tab. Not shown inline in the Frontier stub list rows.
- No "bulk classify" button — can't run classify_stub on all visible frontier stubs at once.
- The "Generate implementation sketch" (Project ↵) button is hidden until a stub is selected.
  New users don't know it exists.

**Proposed fixes:**
- D1: Show stub classification label inline in frontier stub rows if already computed
  (from corpus_shape data). Gray "?" if not yet classified.
- D2: "Classify all" button in frontier toolbar → batch classify_stub on visible stubs,
  update row labels. (LLM cost: acceptable for small stub sets like dj2's 13.)
- D3: Show "Project ↵" and "Reason ↵" buttons in the stub list header (not just when
  selected), with tooltip "select a stub first".

---

## Q5 — Design drift

**Current UI path:** Design mode → sidebar nav "violations" item fires chat query
"check design violations". But check_design_violations requires a symbol name — the
bare chat query arrives without one and returns an error.

**Currently broken for Design drift question.** The design mode action misfires.

**Gaps:**
- Design mode nav action "violations" submits "check design violations" to chat.
  The tool requires `symbol` arg. The chat query has no symbol. Fails silently
  (returns error in chat result).
- No direct symbol-targeted violation check UI outside chat.
- Without ingested design_notes (ingest_design_docs not run on dj2), the tool
  returns "No layer rules defined" even when a symbol is given. The UI doesn't
  guide users to run ingest_design_docs first.

**Proposed fixes:**
- E1: Change the Design mode "violations" action from a bare chat submit to a
  prompted inline form: "Check violations for: [symbol input] [Run]". Same pattern
  as the Tools panel shortcuts.
- E2: On Design mode activation, if design_note_count == 0, show a prominent hint:
  "No design rules loaded. Run ingest_design_docs to extract rules from your docs."
  Already have the design_doc_hint mechanism — wire it to Design mode banner.
- E3: After ingest_design_docs, auto-run check_design_violations on the top 3 HOT
  symbols and show a digest in the Design mode sidebar. Surfaces real findings
  without requiring the user to know which symbol to check.

---

## Q6 — Call chains

**Current UI path:** Two surfaces.
- Call tree tab: enter symbol, toggle callers/callees, expand nodes. Works.
- Graph tab: enter symbol, set hops, renders Cytoscape neighborhood. Works.
  Click node → spotlight. Works.

**Works:** Both paths functional for the primary question (trace from a symbol).

**Gaps:**
- No "find path from A to B" UI (graph_path src/dst). The Graph tab shows a
  neighborhood, not a directed path. If you want "how does dungeon_enter reach
  _register_world_tools", you need chat or walk_call_chain via Workbench.
- walk_call_chain is broken for TS/JS corpora (FQN mismatch — known issue).
  For dj2 (Python) it works, but there's no direct UI shortcut.
- The trail bar shows breadcrumb history but doesn't let you "trace between two
  trail stops" — you navigate manually, you don't get the path visualized.

**Proposed fixes:**
- F1: Add a "Path from → to" input pair in the Graph tab toolbar:
  [src input] → [dst input] [Find path]. Calls graph_path, highlights the path
  in the existing Cytoscape graph (or renders a minimal path-only graph).
- F2: Trail "connect" action: right-click a trail stop → "Trace path to here from [prev stop]".
  Fires graph_path between the two trail breadcrumbs.
- F3: Call tree "depth" control: currently shows 1 level at a time. Add a "expand to depth N"
  option (1-5) so a walk_call_chain chain is visible without clicking every node.

---

## General UI gaps (cross-cutting)

### G1 — Workbench is the escape hatch but isn't discoverable

The Workbench tab is where you can run any tool ad hoc. But:
- It's in the "More tabs" overflow — not visible by default.
- The tool picker doesn't have all tools with inline parameter forms.
  Many tools require knowing the exact name and args.
- No tool documentation visible in the picker (just a name and description snippet).

**Fix:** Promote Workbench to the primary tab bar (remove from overflow).
Add inline parameter forms for every tool in the registry, grouped by category.
Show parameter names, types, and a one-line description on expand.

### G2 — Spotlight is unreachable without first finding the symbol

The Spotlight panel is the richest surface in the UI — declaration, risk, callers,
callees, design frame, findings, source link. But it only opens when:
- You click a symbol in a chat result
- You click a node in the Graph
- You click a symbol in the Call tree

There's no "open spotlight for symbol X" search box at the top level. The symbol_context
tool shortcut in the Tools panel is the closest — it fires the query — but the result
renders in chat prose, not the Spotlight panel.

**Fix:** Add a global symbol search box (⌘K style) that opens spotlight directly.
Keyboard shortcut or persistent input at top of sidebar. Type 3 chars → autocomplete
from functions table → click → Spotlight opens. No chat, no navigation first.

### G3 — Corpus switch reloads the page but loses investigation context

Switching corpus reloads the page (by design — switched=True flag). The trail,
clue pins, and bag are cleared. If you're mid-investigation on Determined and switch
to dj2 to look something up, you lose the Determined context.

**Fix (architectural):** Session snapshots — before switching, serialize current
trail+clues+bag to a named slot. On return, restore. Low cost: the data is small.
Or: corpus-scoped session storage (localStorage keyed by db_path).

### G4 — No "why did this answer come from this tool?" transparency on non-chat tool calls

The pipeline trace (item 8, DONE) shows trace for chat queries. But direct tool
calls from the Tools panel or mode actions don't show any trace. If a tool returns
unexpected output, there's no way to see what arguments were actually sent.

**Fix:** Show a collapsed "Tool: blast_radius({target: 'X', limit: 10})" line above
every tool result, not just chat-routed ones.

---

## Where a capable cloud LLM would help (vs local 8B)

The local Qwen3-8B model handles factual tool calls well (symbol lookup, blast radius,
stub listing). It struggles with:

**L1 — Multi-step reasoning across findings**
"Given these 5 stubs, what is the most likely build order?" requires holding multiple
classification results, cross-referencing the graph, and reasoning about prerequisites.
The 8B model produces plausible-sounding but sometimes wrong orderings.
A Claude 3.5+ model would give a significantly better answer here.
**Proposal:** Route multi-hop questions (goal_intake, reason_about, Design Oracle
CRITICAL/OPPORTUNITY/FOREWARNING) to a cloud model via an optional API key setting.
Local handles factual lookups; cloud handles synthesis.

**L2 — Docstring generation quality**
"Propose a docstring for _register_world_tools" from the 8B model produces correct
but often generic docstrings. The semantic nuance of what the stub is supposed to do
(based on its call context) is underweighted.
**Proposal:** Docstring proposals (Doc Health tab) should optionally call a cloud model.
Show a "High quality ✨" option next to "Propose" that uses the cloud route.

**L3 — Design violation reasoning**
check_design_violations embeds the symbol against design_notes and surfaces raw
cosine scores. The 8B model is not asked to reason about whether the code actually
violates the note — it just surfaces the notes with high similarity.
A capable model could read the function body + design note + call context and give
a verdict with evidence.
**Proposal:** check_design_violations gets a two-tier output: (a) fast: cosine-ranked
design notes [local 8B, existing behavior], (b) deep: verdict per note with evidence
and suggested fix [cloud model, opt-in per session].

**L4 — Discovery narration**
The Discovery tab runs 6 tools in sequence and narrates findings. The narration
quality from the 8B model is adequate for factual reporting but weak at identifying
the non-obvious pattern across findings ("the three AI-layer stubs all depend on the
same missing service layer — this is a design skeleton, not random incompleteness").
**Proposal:** Discovery synthesis step uses cloud model if API key is set.

---

## Summary: priority order for fixes

| # | Fix | Impact | Cost |
|---|-----|--------|------|
| E1 | Design mode violations → inline symbol form | Unblocks Q5 | Low |
| C1 | Feature areas block in Navigate sidebar | Unblocks Q3 | Medium |
| A1 | "Show all EPs" expansion from Roots | Completes Q1 | Low |
| G2 | Global symbol search → Spotlight | High leverage | Medium |
| F1 | Path-from-to in Graph tab | Completes Q6 | Medium |
| B1 | Rename blast radius shortcut label | Discoverability | Trivial |
| D1 | Stub classification inline in frontier rows | Reduces Q4 clicks | Low |
| E2 | Design mode → ingest_design_docs hint | Guides new users | Low |
| G1 | Promote Workbench, add full tool forms | Full tool access | High |
| L1 | Cloud model route for synthesis | Quality leap | Architectural |

Items E1, A1, B1, E2 are trivial or low cost and unblock visible gaps.
C1, G2, F1 are medium — each is a new surface, ~1-2 hours of UI work.
G1 and L1 are architectural.
