Written at commit: 87ac266
# SESSION STATE - session 146 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 146, 2026-07-11)

### Commits this session [V]

- `3063da2` File RM43: canned reasoning lenses on top of clue board
- `87ac266` File RM44-RM48 and RM42 pass 2: analysis-to-code action arc

### Changes made [V]

**No code written this session.** Pure planning/design work.

**Design projection: analysis-to-action capability gap [V]**
Reviewed all open TRACKER items + current capabilities. Identified that Determined
has a solid floor for orientation, gap-finding, and design-violation detection, but
is entirely missing the transition from "found incomplete work" to "act on it."

Six new items filed to close that gap (all in TRACKER.md with full detail):

- RM43 (filed prior commit): Canned reasoning lenses on top of RM42 clue board.
  7 named lenses (next action, not ready, wiring gaps, template fill, blast radius,
  convergence check, open questions). Prompt templates in reasoning_lenses.py.
  Lens selector UI at bottom of RM42 panel. Dep: RM42 must ship first.

- RM44: Implementation ordering. Topo sort of all stubs + ABC gap methods into
  dependency-ordered waves using Kahn's algorithm over graph_edges. Pure DB query,
  no LLM. Reuses _get_abc_gap_set (agent_tools.py:1283) and list_stubs. ~80 lines.

- RM45: Completion contract. Single call returning: param types (param_types_json),
  return type (return_type column), callers + what they do with the return value,
  callees split into complete vs stub, behavioral contracts, design violations,
  and stub-callee blockers. Assembles existing data via _list_callers_raw,
  _list_callees_raw, _check_design_violations_core, gather_context. No new schema.

- RM46: Scaffold from pattern. Finds structurally similar complete functions using
  module-family match + embedding similarity (threshold 0.50, looser than find_duplicates).
  Extracts structural skeleton (first-stmt type, return shape, error handling) via AST.
  Synthesizes fill-in-the-blanks template with variation points called out. Extends
  _source_skeleton (agent_tools.py:540) and stub_projector.py. This is the inflection
  point: first tool that produces output (a template) rather than just analysis.

- RM47: Readiness gate. Five-tier deterministic check before starting an impl:
  (1) symbol exists and is incomplete, (2) callees not stubs, (3) param types resolvable,
  (4) no design violations above threshold, (5) no cycle in incomplete-stub subgraph.
  Returns READY or BLOCKED with specific blockers listed. No LLM. ~0.5 days.

- RM48: Design-to-code delta. Reads kind='requirement' design_note artifacts (already
  extracted by doc_extractor._MUST_RE). For each requirement, attempts three-level match:
  embedding similarity (level A), file-path keyword (level B), import graph (level C).
  Unmatched = GAP. Requires design docs ingested first. 1 day. NOTE: verify how 'kind'
  is persisted in knowledge_artifacts before implementing (may be in content JSON, not
  a separate column -- run SELECT to check).

- RM42 pass 2: Persist clue board cards to workflow_items (kind='investigation_clue',
  body=JSON blob). Three new API endpoints in ui_server.py (save/list/delete/clear).
  Four frontend hooks in console.html. No schema migration (body is already TEXT).
  0.5 days after pass 1 ships.

### Tests [V]
545 passed, 1 skipped, 18 deselected -- no code changed this session, count unchanged.

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1 | Module-qualified callee names break BFS | FIXED (sessions 142, 144) |
| 2 | dict-of-callables dispatch (TOOLS) | FIXED (session 142) |
| 3 | Thread(target=fn) implicit calls | FIXED (session 142) |
| 4 | @socketio.on / @app.route decorators | FIXED (session 142) |
| 7 | JS socket.emit -> Python handler | FIXED (session 143) |
| 8 | ABC/subclass polymorphic dispatch | FIXED (Item 20) |
| JS | DOM controls -> socket.emit | REVISED: no emit in dj2 (RM38) |
| DF | Data flow / return value chains | OPEN (RM39 Level 1 next) |
| TR | Target resolution collision (bare names) | OPEN (RM40) |
| HTTP | fetch/HTMX -> Flask route edges | OPEN (RM41) |
| INV | Investigation context panel | OPEN (RM42) |
| LNS | Canned reasoning lenses (clues -> answers) | OPEN (RM43) |
| ORD | Implementation ordering (topo sort stubs) | OPEN (RM44) |
| CTR | Completion contract (param/return/design summary) | OPEN (RM45) |
| SCF | Scaffold from pattern (skeleton from similar complete fns) | OPEN (RM46) |
| RDY | Readiness gate (is X safe to implement?) | OPEN (RM47) |
| DGP | Design-to-code delta (design says should exist, doesn't) | OPEN (RM48) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** 545 tests pass. Live LLM probe not re-run --
requires llama-server + loaded corpus. Low risk. Fold into RM39 Level 1 session.

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA are
separate stores -- both must be updated together.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**test_graph_viz.py fixture [?]:** still uses old schema. Fine until FQ-callee test needed.

**cross_language edges = 0 in dj2 [V]:** Not a bug -- no client-side socket.emit in dj2.

**RM48 schema check needed [V]:** Before implementing design_gaps, run:
`SELECT content FROM knowledge_artifacts WHERE kind='design_note' LIMIT 5`
against a corpus with ingested design docs. Verify whether 'requirement' kind is a
separate column or buried in the content JSON. Doc_extractor.py DesignRule.kind exists
in Python but may not be a separate DB column -- check persistence_engine.py ~line 428.

## NEXT SESSION -- start here

**Recommended order (from TRACKER):**

1. **RM40 (0.5 days) -- target resolution collision fix [HIGHEST PRIORITY]:**
   Add resolved_only=False param to bfs_callees/subgraph_around in
   determined/agent/graph_utils.py. Filter WHERE resolved=1 when True.
   Expose in agent_tools.py bfs_callees args. Add regression test verifying
   BFS from handle_connect with resolved_only=True excludes bestiary.get().
   This unblocks accurate BFS for RM39, RM44, RM47 (all depend on graph accuracy).

2. **RM44 (0.5 days) -- implementation ordering:**
   New function implementation_order(oracle, args) in agent_tools.py after
   frontier_priority (~line 1678). Algorithm: collect stubs + ABC gaps into set S,
   build subgraph of S->S edges from graph_edges, Kahn's topo sort, format as waves.
   Wire into TOOLS + tool_registry.py category "frontier". New test file.

3. **RM47 (0.5 days) -- readiness gate:**
   New function readiness_check(assessor, args) in agent_tools.py after completion_contract.
   Five-tier check (see TRACKER RM47 for exact queries). Wire into TOOLS + registry.

4. **RM45 (0.5 days) -- completion contract:**
   New function completion_contract(assessor, args) in agent_tools.py after symbol_context
   (~line 614). Assemble: param_types_json + return_type + _list_callers_raw +
   _list_callees_raw + _check_design_violations_core + behavioral_contracts + gather_context.
   Wire into TOOLS + registry category "understanding".

5. **RM39 Level 1 (2 days) -- data_flow edges:**
   Entry point: determined/ingestion/parse_ast.py Visitor.visit_Call.
   Emit edge_type='data_flow' when call arg is itself a call (fn_b(fn_a())).
   Also annotation-matched return-type -> param-type edges.

6. **RM42 (1 day) -- investigation context panel:**
   Entry point: determined/ui/templates/console.html.
   5th rail icon, clue card JS array, pin button on tool results,
   "Ask about this" button composing Ask bar query from card summaries.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
