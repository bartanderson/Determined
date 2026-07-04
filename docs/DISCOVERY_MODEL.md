# Discovery Model — Determined Navigation & Analysis Architecture

_Created session 61, 2026-07-03. Updated session 61 (composability audit). Living document — update disposition fields in place._
_Companion to DESIGN_ARC.md (what the investigation arc does) and DESIGN.md (why things are built the way they are)._
_This document covers the richer conceptual layer: how analysis surfaces hidden structure, how it connects to planning, and how the UI makes it navigable._

---

## What this document is

During frontier graph work (session 61) a cluster of connected ideas emerged that are larger
than any single TRACKER item. This document stakes the conceptual territory, names the pieces,
maps their connections, and provides an exploration checklist per concept so findings are mined
systematically and their disposition is never lost.

Each checklist item has a **Disposition** line. Update it when the item is explored:
- `→ not explored` — default
- `→ finding: <what we learned>` — explored, produced a finding worth recording
- `→ filed: item N` — turned into a TRACKER item
- `→ implemented: <commit or session>` — done
- `→ deferred: <reason>` — explicitly not now
- `→ N/A: <reason>` — explored, turns out not applicable

---

## The Five Concepts

### 1. Topology

The *shape* of a program's incompleteness — not just "here are stubs" but "here is the
structural pattern of how this program is unfinished." Different topologies imply different
queries, different visualizations, and different fix strategies.

**Known shapes so far:**

| Shape | Description | Example in dj2 |
|---|---|---|
| Direct-call | Functional code calls a stub by name; edges exist in call graph | `validate_action`, `get_player_by_session` |
| ABC-interface | Abstract methods on a base class; no concrete override exists | `phases.py` InputPhase, IntentPhase, etc. |
| Orphaned-impl | Implemented function whose only callers are stubs or don't exist yet | TBD — need to detect |
| Chain | Stub calls another stub; incompleteness propagates through the graph | TBD — need to detect |
| Disconnected | Stubs with no callers and no callees — pure island stubs | May exist in dj2 |

**Exploration checklist:**

- [ ] **T1** — Complete the shape taxonomy. Are there shapes beyond the five above? Review dj2 stubs
  for patterns that don't fit any current category.
  Disposition: `→ not explored`

- [x] **T2** — Detect which shape(s) a given corpus exhibits. Write a `detect_topology()` query
  that returns a shape inventory (counts per shape) for the loaded corpus.
  Disposition: `→ implemented: session 69. detect_topology() in agent_tools.py. Five shape counts: direct-call (stubs with functional callers), ABC-interface (abstract methods with no concrete override), chain (stubs calling stubs), orphaned-impl (implemented fns with no non-stub callers), disconnected (stubs with no callers or callees). _dominant_shape() identifies the leading pattern. Wired into TOOLS + REGISTRY. 5 regression tests.`

- [ ] **T3** — A function can participate in multiple shapes simultaneously (e.g. a stub that is
  both direct-call AND part of a chain). Is multi-shape membership a stronger signal? Test
  against dj2.
  Disposition: `→ not explored`

- [ ] **T4** — UI representation. Should topology be a summary panel (a topology overview before
  drilling into any specific frontier), a selector that filters which frontier views are shown,
  or both? Decide before building.
  Disposition: `→ not explored`

- [ ] **T5** — Topology drift. Can git history be used to detect when a shape changes (e.g. a
  direct-call stub gets implemented — the frontier shrinks)? Would require comparing DB snapshots
  or re-ingesting on commit.
  Disposition: `→ not explored`

---

### 2. Frontier

The boundary between implemented and unimplemented code. The Frontier tab (session 61) covers
the direct-call shape. Each topology has its own frontier type.

**Exploration checklist:**

- [ ] **F1** — Validate direct-call frontier query across more programs. Does the suffix-match JOIN
  hold up? Are there false positives (common short names matching unrelated stubs)?
  Disposition: `→ not explored`

- [ ] **F2** — ABC frontier (filed as TRACKER item 29): find abstract methods with no concrete
  override. Requires class hierarchy data not currently in schema.
  Disposition: `→ filed: item 29`

- [ ] **F3** — Orphaned-implementation detection: find functional code whose only callers are stubs
  or missing. These are implementations written ahead of their interfaces.
  Disposition: `→ not explored`

- [x] **F4** — Chain-of-stubs detection: find stubs that call other stubs. The chain length is a
  measure of how far a subsystem is from being runnable.
  Disposition: `→ implemented: session 68. _frontier_rows(conn, mode) in ui_server.py — 'chain' passes caller_stub=1 to the WHERE clause, 'all' unions both. Frontier tab toolbar has Direct/Chain/All/ABC dropdown; fgMode drives the socket event. Verified in browser (dj2 corpus).`

- [ ] **F5** — Composite frontier signal: a function appearing in multiple frontier types
  simultaneously is high priority. Build a query that scores stubs by how many shape-frontiers
  they appear in.
  Disposition: `→ not explored`

- [ ] **F6** — Frontier coverage metric: what percentage of the corpus is "behind the frontier"
  (reachable only through at least one unimplemented stub)? Useful as a project health indicator.
  Disposition: `→ not explored`

- [ ] **F7** — UI: the current Frontier tab shows one graph per load. Should it support switching
  between frontier types (a toolbar selector: Direct / ABC / Orphan / Chain)?
  Disposition: `→ not explored`

---

### 3. Implementation Queue

The frontier ranked by *unblocking value* — which stub, when implemented, enables the most
downstream progress. This is where MCTS enters: `evaluate()` is already the evaluator node;
the implementation graph is the search tree.

**The MCTS connection explicitly:**
- Tree nodes = stubs
- Edges = "implementing A unblocks B" (A calls B, or A is a prerequisite for B's callers)
- Leaf value = caller count + chain depth + evaluate() judgment ("if this were implemented, what becomes possible?")
- Tree search = sequenced build plan

This is not a future speculation — `evaluate()` with a stub as subject and its callers as
evidence is a direct, concrete use of the existing kernel for planning purposes.

**Exploration checklist:**

- [x] **Q1** — Rank stubs by caller in-degree (number of functional callers). Verify against dj2
  frontier results (validate_action=5, get_player_by_session=4 are the predicted top two).
  Disposition: `→ finding: list_stubs() in agent_tools.py already does this — suffix-match JOIN on callee column, ranks by caller count. validate_action and get_player_by_session confirmed as top two. NOTE: list_stubs uses 'callee' column; frontier query uses 'target_id'. These are parallel implementations of the same lookup — should converge into one canonical function (see A1 notes).`

- [ ] **Q2** — Define "unblocking value": implementing stub X removes N frontier edges. If X also
  calls stubs Y and Z, those must be counted too. Is this the right metric, or should it be
  purely in-degree?
  Disposition: `→ finding: depends on F4 (chain detection) being built first. In-degree alone (Q1) is already meaningful and available. Full unblocking value needs chain depth added to in-degree — defer until F4 exists.`

- [x] **Q3** — Wire `evaluate()` to score a stub for implementation priority. Prompt shape:
  subject = stub function, evidence = its callers + its docstring + its stub body, question =
  "what becomes possible if this is implemented, and how central is it to the system?"
  Disposition: `→ implemented: score_stub() in agent_tools.py:3285. Chains gather_context() -> collect_symbol_context() -> retrieve_evidence() -> evaluate(). Returns structural rank (caller count), semantic verdict + confidence %, reasoning, callee list, file location. Wired into TOOLS (line 3472) and tool_registry.py. Falls back to structural-only when no design_note evidence available.`

- [ ] **Q4** — Tree search over the frontier: given the current stub set, what is the optimal
  implementation sequence to make the largest runnable subset of the program available soonest?
  This is MCTS on the implementation graph. Expensive but worth profiling on dj2's 47 stubs.
  Disposition: `→ deferred: blocked on Q3 (evaluate() scoring per stub) and F4 (chain detection). Do after those prove out. The evaluate() kernel split (build_eval_request / execute_eval_request) from session 60 already makes this composable when ready. See REASONING_MODEL.md — R1/R2/R3 (Decomposer/Router/Synthesizer) is the concrete design for Q4's evaluator node. RM9 is the explicit connection item.`

- [x] **Q5** — UI: a sortable queue table. Columns: stub name, file, caller count, chain depth,
  evaluate() score (on demand), disposition (not started / in progress / done). This is the
  primary game-work planning view once the tool is mature enough.
  Disposition: `→ implemented (bridge): session 68. frontier_to_queue socket event (ui_server.py:1161) calls list_stubs() then store_workflow_item() for each result ranked by caller count. "→ Queue" button in Frontier toolbar fires it. prioritize_work() now sees frontier data automatically. Full sortable queue tab (Tier 3 UI item 6) still outstanding.`

- [x] **Q6** — Implementation scaffold: given a stub + its callers as context, generate a partial
  implementation (parameter handling, return type, likely logic sketch) using the quality-tier
  LLM. Not a full implementation — a starting skeleton. Saves the jump-start cost.
  Disposition: `→ implemented: session 68. stub_projector.py (gather_context + _build_prompt + project_stub) wired into Frontier tab via project_stub_request socket event (ui_server.py:1059). Selecting a red stub node reveals "Project ↵" button; result renders in fg-projection panel below the graph. Verified in browser (dj2 corpus).`

---

### 4. Access Paths

A single function can be reached via multiple *methods of travel*: direct name call, import alias,
`self.method()` resolved to `ClassName.method`, type annotation, runtime binding, module prefix,
inheritance. The tool currently treats each path as a separate thing; they should collapse to one
node with paths as properties.

**Known resolution methods:**
1. Direct bare-name call (`fetch_data()`)
2. Module-prefixed (`stubs.fetch_data()`)
3. Import alias (`from stubs import fetch_data as fd; fd()`)
4. Self-method (`self.fetch_data()` → `MyClass.fetch_data`)
5. Type-annotation-resolved (`def f(x: Fetcher): x.fetch_data()`)
6. Runtime binding (assigned via `self.fetcher = Fetcher(); self.fetcher.fetch_data()`)
7. Inherited method (subclass calls parent's method via `super()` or direct name)
8. Chained attribute (`self.subsystem.fetcher.fetch_data()`)

The frontier query's suffix-match JOIN is a partial fix for paths 1-2. The others remain untracked
or tracked inaccurately.

**The `resolved` flag problem:**
Currently `graph_edges.resolved = 1` means "this edge was annotation-derived" (method 5 above),
NOT "this callee is a project function." This was the root cause of the original frontier query
failure. Separating these two meanings would lift graph accuracy across all features.

**Exploration checklist:**

- [ ] **A1** — Audit the `resolved` flag: rename or add a column. Proposal: keep `resolved` for
  annotation-derived (its current correct use), add `is_project_call BOOLEAN` that is true
  whenever the callee matches any project function name (by any path). Requires a migration.
  Disposition: `→ finding: confirmed needed. 'resolved=1' means annotation-derived (correct use), NOT 'is a project function' (wrong assumption in original frontier design). list_stubs() joins on 'callee' column; frontier query joins on 'target_id' — parallel implementations of same lookup. Convergence + is_project_call flag would lift accuracy across all graph features. Schema migration required. Not Tier 1 — do after other connections are validated.`

- [ ] **A2** — Build an `access_paths(symbol)` query: given a function name, return all known
  names/paths by which it is referenced in the corpus. Output: list of (path, resolution_method,
  caller_file, count).
  Disposition: `→ not explored`

- [ ] **A3** — Collapse the graph: when two edges point to the same destination via different paths,
  merge them into one edge with a `path_count` property. This de-duplicates the graph and makes
  connectivity counts accurate.
  Disposition: `→ not explored`

- [ ] **A4** — UI: the universal sub-menu. Anywhere a symbol name appears (call tree, frontier
  graph, Spotlight, editor symbol list, search results), a secondary action reveals:
  - All access paths to this symbol
  - Which frontier types it participates in
  - Its queue priority
  - Pin as waypoint
  This is the primary navigation hook that connects all views.
  Disposition: `→ finding: backbone is symbol_context() — already returns role, risk, callers, callees, class, docstring, design frame, findings. Sub-menu is symbol_context() rendered as a hover popover on any element with data-sym attribute. No new backend code needed; only CSS + JS popover + socket event wiring. Depends on A2 (access paths query) for the 'also known as' section.`

- [ ] **A5** — Method 8 (chained attribute calls like `self.subsystem.fetcher.fetch_data()`) is
  currently unresolvable without runtime type information. Determine whether class_attributes
  table has enough data to do a static multi-hop type trace. If yes, this unlocks resolution
  for a large class of currently-unresolved edges.
  Disposition: `→ not explored`

---

### 5. Waypoints

Pinned discoveries that carry their *discovery context* — not just "I pinned this function" but
"I found this function via the frontier graph as a stub with 5 callers, arriving from the
Topology view." The trail has value; the destination alone does not.

A waypoint is: `{name, view_origin, context_data, timestamp, note, trail}`

- `name` — the symbol or object pinned
- `view_origin` — which tab/view it was found in (frontier, call_tree, spotlight, etc.)
- `context_data` — the state of the view at pin time (e.g. which frontier type, which root node)
- `timestamp` — when pinned
- `note` — user annotation
- `trail` — ordered list of prior waypoints that led here (the journey)

A collapsed waypoint shows only the name. Expanded: the full trail with view labels.

**Journey vs. destination question:**
For navigation, you usually want the destination (jump back to this symbol). For understanding,
you want the journey (how did I conclude this was important?). Both are valid. The UI should
support both: single click = navigate to destination, expand = reveal journey.

**Exploration checklist:**

- [x] **W1** — Define waypoint schema formally. Where do waypoints live? Options: (a) corpus DB
  as a new `waypoints` table, (b) knowledge_artifacts with kind='waypoint', (c) a separate
  user-state file outside the DB. The right answer depends on whether waypoints are
  corpus-specific or user-global.
  Disposition: `→ implemented: session 69. knowledge_artifacts with kind='waypoint'. Content is JSON {name, view_origin, note, verdict, confidence, trail}. Added 'waypoint' to VALID_KINDS in knowledge_artifact.py. Corpus-scoped (lives in corpus DB alongside other artifacts). Survives re-ingest since knowledge_artifacts is not rebuilt by re-ingest.`

- [x] **W2** — Persistence model: should waypoints survive a re-ingest? Probably yes, since they
  represent analytical conclusions, not structural facts. This argues for knowledge_artifacts
  or a separate user-state store, not a corpus-derived table.
  Disposition: `→ implemented (by W1 decision): knowledge_artifacts is not touched by reingest_file() or ingest pass — only structural tables (symbols, graph_edges, etc.) are rebuilt. Waypoints survive re-ingest automatically.`

- [x] **W3** — UI: waypoint panel. A collapsible sidebar section or a dedicated tab showing all
  pinned waypoints, grouped by session or by view_origin. Each entry: symbol name + view badge
  + trail depth indicator.
  Disposition: `→ implemented: Pins tab in console.html (panel-waypoints). get_waypoints socket event (ui_server.py:1799) queries kind='waypoint'. Cards show name, view badge, note, trail, provenance, timestamp. sym-link click opens spotlight. Already wired as tab button data-tab='waypoints'.`

- [ ] **W4** — Trail rendering: a collapsed waypoint shows `[frontier] → validate_action`. Expanded:
  full chain of how we got here. Consider a breadcrumb strip rather than a nested tree.
  Disposition: `→ not explored`

- [ ] **W5** — Waypoint sharing / export: a waypoint (or trail) exported as a small JSON blob
  that, when imported, restores the view+context so another session (or another user of the
  same corpus) lands in the same place with the same understanding. Useful for async
  collaboration or session handoff.
  Disposition: `→ not explored`

- [x] **W6** — Auto-waypoint: should the tool automatically create a waypoint when a finding is
  confirmed via check_design_violations or evaluate()? The finding already has a subject and
  context — a waypoint is nearly free to generate alongside it.
  Disposition: `→ implemented: session 69. Auto-waypoint wired into evaluate_claim() (agent_tools.py) and score_stub(). When verdict not in {UNRELATED, UNCERTAIN}, adds kind='waypoint' artifact to knowledge DB with view_origin, note=reasoning, verdict, confidence. Best-effort (exception-swallowed) so it never breaks the primary tool. Surfaces automatically in Pins tab on next refresh.`

---

## Connection Map

```
Topology
  └─ determines which Frontier views apply
       └─ Frontier (per shape)
            └─ populates Implementation Queue
                 └─ Queue nodes evaluated by evaluate() / MCTS
                      └─ produces a sequenced Build Plan
                           └─ each step navigable via Access Paths
                                └─ navigation creates Waypoints
                                     └─ Waypoints reference Topology + Frontier context
                                          └─ (loop: revisiting a waypoint re-enters the map)
```

MCTS sits at the Queue → Build Plan transition. It is not a separate system — it is
`evaluate()` called iteratively over the frontier graph, with backpropagation determining
which stub to implement next for maximum unblocking value.

Access Paths is the horizontal connector: it links any node in any view to any other view.
It is the universal translation layer between "name as it appears in code" and "name as it
lives in the DB."

Waypoints is the memory layer: it makes the map navigable across sessions, not just within one.

---

## Interface Implications

**The universal sub-menu** (access via any visible symbol name, right-click or hover):

```
validate_action
  ├─ Inspect → [opens Spotlight]
  ├─ Topology role  → stub · direct-call shape · 1 chain hop
  ├─ Frontier role  → stub (5 callers)
  ├─ Queue priority → #1 of 47 stubs by caller count
  ├─ Access paths   → AuthoritySystem.validate_action
  │                    authority_system.ValidatedAction
  │                    app.world_controller.authority_system.validate_action
  └─ Pin waypoint   → [pins with current view context]
```

**Naming principles** (names must be legible without reading docs):

| Concept | UI label | Why |
|---|---|---|
| Topology | Shape | One syllable, visual, doesn't require knowing the term |
| Frontier | Frontier | Already in use, works |
| Implementation Queue | Build queue | Concrete action word |
| Access Paths | Known as | Conversational; "also known as" is instantly clear |
| Waypoints | Pins | Familiar from mapping apps; "trail" for the journey view |

---

## Composability Audit (session 61)

What exists, what connects to what, and how much new code each tier needs.

### Already built — ready to connect

| Tool / module | What it does | Connects to |
|---|---|---|
| `list_stubs()` | Ranks stubs by caller count, suffix-match JOIN | Q1 done; feed output into workflow_items for Q5 |
| `stub_projector.py` | gather_context + build_prompt + LLM call | Q6 done; wire into frontier UI as "Project" button |
| `project_stub` tool | Agent-facing wrapper for stub_projector | Q6 agent access done; needs UI socket event |
| `evaluate_claim()` | Observe->Situate->Evaluate kernel | Q3 backbone; needs stub-specific prompt + gather_context feed |
| `gather_context()` | Callers + contracts + sibling callees for a stub | Q3 context; feeds directly into evaluate_claim() |
| `prioritize_work()` | Reads workflow_items, returns ranked recommendation | Q5 planner; needs frontier ranking as input |
| `store_workflow_item()` | Writes to workflow_items backlog | Q5 bridge; call with list_stubs() output |
| `knowledge_artifacts` + `store_finding()` | Generic artifact store | W6 backbone; kind='waypoint' is all that's needed |
| `symbol_context()` | Everything known about a symbol in one call | A4 backbone; render as inline popover, no new backend |

### Tier 1 — connect existing pieces [ALL DONE, session 68]

1. **[DONE] Frontier + project_stub**: `project_stub_request` socket event (ui_server.py:1059);
   "Project ↵" button appears on red stub node selection. Result renders in `fg-projection` panel.

2. **[DONE] F4 chain toggle**: `_frontier_rows(conn, mode)` (ui_server.py:922) parameterizes
   the WHERE clause; toolbar dropdown has Direct/Chain/All/ABC options. fgMode drives the emit.

3. **[DONE] Frontier -> build queue**: `frontier_to_queue` socket event (ui_server.py:1161);
   "→ Queue" button in toolbar. Calls `list_stubs()` -> `store_workflow_item()` per stub ranked
   by caller count. `prioritize_work()` now sees frontier data automatically.

### Tier 2 — new prompt on existing kernel (~30 lines)

4. **Stub scorer** (`score_stub` tool): `gather_context(stub)` -> format as claim ->
   `evaluate_claim(claim, question="how central is implementing this to making the system runnable?")`.
   Returns verdict + confidence as a stub priority score. Adds an optional "Score" column to
   the build queue.

### Tier 3 — new rendering of existing data (UI only, no new backend)

5. **Sub-menu popover**: hover any `<span data-sym="X">` -> emit `symbol_context` -> render
   subset as a floating panel. Backend: `symbol_context()` already exists. Frontend: ~40 lines
   JS + CSS.

6. **Build queue tab**: new tab reading `workflow_items WHERE kind='next_up'`, rendered as a
   sortable table. Same data `prioritize_work()` reads, different presentation.

7. **Waypoints panel**: new tab reading `knowledge_artifacts WHERE kind='waypoint'`. Collapsed
   list with expand-to-trail. `store_finding()` already writes; just need a reader UI.

### Tier 4 — foundational accuracy (schema migration, unlocks everything)

8. **A1 resolved flag**: add `is_project_call BOOLEAN` to graph_edges. Converge `list_stubs`
   and frontier query onto one canonical lookup. All graph features get more accurate edges.
   Do after Tier 1-3 validate the concepts.

---

## Mining Priority

Updated after composability audit (session 61). Earlier ranking assumed everything needed
building from scratch — composability audit shows most pieces exist and need connecting, not building.

**Tier 1 — connect existing pieces [DONE session 68]:**
1. ~~Frontier + project_stub UI connection (Q6 surface)~~ — done
2. ~~F4 chain toggle in Frontier tab~~ — done
3. ~~Frontier -> build queue bridge (Q5 backbone connection)~~ — done

**Tier 2 — new prompt on existing kernel:**
4. **Q3** — Stub scorer tool (gather_context -> evaluate_claim)

**Tier 3 — new UI rendering of existing data:**
5. **A4** — Sub-menu popover (symbol_context rendered inline)
6. **Q5** — Build queue tab (workflow_items as table)
7. **W3** — Waypoints panel (knowledge_artifacts kind='waypoint')

**Tier 4 — new queries (build on Tier 1 results):**
8. **T2** — detect_topology() (composes F4 + F3 + existing frontier)
9. **F3** — Orphaned implementation detection
10. **F5** — Composite frontier signal (multi-shape scoring)
11. **Q2** — Full unblocking value (in-degree + chain depth, needs F4)

**Tier 5 — foundational schema (do last, after concepts validated):**
12. **A1** — Fix resolved flag + converge callee/target_id lookup
13. **A5** — Multi-hop type trace for chained attribute calls

**Deferred (needs prerequisites):**
- **Q4** — MCTS tree search (needs Q3 + F4 + Q2)
- **W1/W2** — Waypoints persistence design (needs W3 UI to validate the concept first)
- **T1** — Complete topology taxonomy (do during F3 + chain work, emerges naturally)
- **F2** — ABC frontier (TRACKER item 29, needs class hierarchy schema)
