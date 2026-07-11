Written at commit: 88a44a3
# SESSION STATE - session 145 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 145, 2026-07-11)

### Commits this session [V]

- `30b3dac` RM39 prerequisite: dj2 path analysis complete
- `88a44a3` File RM40/RM41/RM42 from dj2 path analysis gaps

### Changes made [V]

**Regression baseline confirmed [V]:**
545 passed, 1 skipped, 18 deselected -- same count as session 144 handoff.

**RM39 prerequisite -- dj2 path analysis [V]:**
Re-ingested dj2 corpus (153 files, 1321 fns, 8199 edges, edge types: static=8098,
decorator=100, thread=1). BFS from all 7 socket handlers and top HTTP route handlers.

Key findings (all verified from source + DB):
- handle_disconnect: isolated -- body calls no project functions
- All other socket handlers reach depth 3-4 (10-18 nodes) but chains converge on
  dnd_data.get() / bestiary.get() -- this is the RM40 target resolution bug (confirmed)
- handle_connect verified in source: calls auth.get() + request.cookies.get() (dict
  methods), NOT bestiary.get(). Bug confirmed.
- HTTP routes are the real action: execute_mutation_phase (depth 5, 30 nodes),
  move/move_character (depth 4, 19-26 nodes), create_character (depth 3, 25 nodes)
- State carriers (annotated): DungeonStateNeo (4 fns), Character (3 fns), PlayerAction (1)
- Return-value priority targets for RM39 Level 1: process()->Dict (adjudication_engine,
  30 callers), execute()->Any (tool_system, 46), generate()->str (llm_client, 21 x2),
  get_session()->SessionState (21), move_party()->dict (21)
- fn_b(fn_a()) nested-call pattern less common than result=fn(); use(result). Level 1
  captures some; Level 2 (variable binding) needed for full coverage.

**RM38 scope revised [V]:**
dj2 has NO client-side socket.emit. Socket is server-to-client push only (world.js uses
socket.on only). Client communicates via HTMX hx-post/get + fetch(). RM38 reframed as:
map DOM controls -> fetch/HTMX -> HTTP route handler.

**Three new TRACKER items filed [V]:**
- RM40: Target resolution collision -- bare names (get, all, emit) resolve to wrong
  project functions in BFS. Fix: resolved_only filter in graph_utils.py using existing
  resolved column (Item 20). Effort: 0.5 days.
- RM41: HTTP fetch/HTMX -> Flask route cross-language edges. Extends Gap 7 to HTTP
  boundary. Same extractor pattern as dynamic_edges.py. Effort: 1 day.
- RM42: Investigation context panel ("clue board"). Accumulate tool outputs as named
  cards; "Ask about this" reasons across the whole board. Session-only JS storage
  in pass 1. Effort: 1 day.

### Tests [V]
545 passed, 1 skipped, 18 deselected (confirmed at session start; no code changed
this session).

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

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Regression passed (545). Live LLM probe not re-run --
requires llama-server + loaded corpus. Low risk. Fold into RM39 Level 1 session when
server is already running.

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA are
separate stores -- both must be updated together.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**test_graph_viz.py fixture [?]:** still uses old schema. Fine until FQ-callee test needed.

**cross_language edges = 0 in dj2 [V]:** Not a bug -- no client-side socket.emit in dj2.

## NEXT SESSION -- start here

1. **RM40 (0.5 days) -- target resolution collision fix:**
   Add resolved_only=False param to bfs_callees/subgraph_around in
   determined/agent/graph_utils.py. Filter WHERE resolved=1 when True.
   Expose in agent_tools.py bfs_callees args. Add regression test verifying
   BFS from handle_connect with resolved_only=True excludes bestiary.get().

2. **RM39 Level 1 (2 days) -- data_flow edges:**
   Entry point: determined/ingestion/parse_ast.py Visitor.visit_Call.
   Emit edge_type='data_flow' when call arg is itself a call (fn_b(fn_a())).
   Also: annotation-matched return-type -> param-type edge.
   Priority targets: process(), execute(), generate(), get_session().

3. **RM42 (1 day) -- investigation context panel:**
   Entry point: determined/ui/templates/console.html.
   5th rail icon, clue card JS array, pin button on tool results,
   "Ask about this" button composing Ask bar query from card summaries.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
