Written at commit: 49bacd3
# SESSION STATE - session 144 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 144, 2026-07-11)

### Commits this session [V]

- `ebbc918` Two-tier naming audit: fix traversal to use source_id/target_id
- `59f969b` Fix callee-surface-column traversal in graph_viz and agent_tools
- `49bacd3` Add RM38 + RM39 to TRACKER

### Changes made [V]

**Two-tier naming contract -- full audit and fix:**

The naming contract (source_id/target_id = canonical bare names for traversal;
caller/callee = raw surface names for display) was documented but incompletely
enforced. This session completed the enforcement.

`determined/agent/graph_utils.py`:
- Added `_has_id_columns(conn)` helper: PRAGMA-based schema check for backward compat
- Module header added: 25-line contract documentation
- `bfs_callees`, `most_connected`, `subgraph_around`, `find_clusters`: all now use
  source_id/target_id with _has_id_columns fallback for old test fixtures

`determined/agent/agent_tools.py`:
- `_list_callers_raw`: now queries `target_id` (with _has_id_columns fallback)
- `find_primitive_gaps`: uses source_id/target_id instead of callee NOT LIKE filter
- `report_stub_status` callee_set/caller_set: uses target_id/source_id

`determined/agent/graph_viz.py`:
- `to_text_tree`: uses source_id/target_id for BFS walk (was querying raw callee surface
  column -- broke multi-hop traversal when callees were stored as FQ names)

`determined/persistence/persistence_engine.py`:
- Schema comment updated with explicit two-tier contract

Test fixtures updated:
- `test_agent_tools.py`: fixed target_id in graph_edges fixture (was FQ, should be bare)
- `test_discovery_agent.py`: added source_id/target_id columns
- `test_agent_resolver.py`: schema upgraded (no edges inserted, consistency only)
- `test_pattern_executor.py`: schema upgraded (no edges inserted, consistency only)

**Fixture audit -- justifications:**
- `test_claim_verifier.py`: old schema correct -- claim_verifier queries surface
  caller/callee by design (verifying literal source-text names, not traversal)
- `test_find_primitive_gaps.py`: old schema correct -- function queries callee surface
  column; that function needs fixing separately, test matches current behavior
- `test_find_duplicates.py`: bare-name edges only; upgrading adds no coverage without
  a FQ-callee test case; leave until such a test is written

**Stub queries NOT changed [V]:**
`ge.callee = f.name OR ge.callee LIKE '%.' || f.name` in list_stubs, detect_topology,
find_abc_gaps etc. already handles FQ callees correctly via LIKE. Not broken.

**New TRACKER items [V]:**
- RM38: JS/HTML event chain analysis (DOM controls -> events -> socket emissions)
- RM39: Data flow tracking (parameter-passing + return-value edges)

### Tests [V]
545 passed, 1 skipped, 18 deselected (confirmed on final run after all changes)

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1 | Module-qualified callee names break BFS | FIXED (session 142, hardened 144) |
| 2 | dict-of-callables dispatch (TOOLS) | FIXED (session 142) |
| 3 | Thread(target=fn) implicit calls | FIXED (session 142, verified 143) |
| 4 | @socketio.on / @app.route decorators | FIXED (session 142, verified 143) |
| 7 | JS socket.emit -> Python handler | FIXED (session 143) |
| 8 | ABC/subclass polymorphic dispatch | FIXED (Item 20 data) |
| JS | DOM controls -> JS handlers -> socket.emit | OPEN (RM38) |
| DF | Data flow / return value chains | OPEN (RM39) |

## Known issues (carried forward)

**RM21 probes not re-run this session [?]:**
Last known: all 6 pass (commit e242815). Graph traversal changed significantly in
sessions 142-144. Must verify before building on them.
Run: `.venv\Scripts\pytest tests/regression/ -k "probe or RM21"` -- or grep for
the probe test file (prior search was interrupted).

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and inline GUIDE_DATA in
console.html are separate stores -- both must be updated together.

**Determined corpus DB path [V]:** `C_Users_bartl_dev_Determined.db`

**test_graph_viz.py fixture [?]:** still uses old schema (no source_id/target_id).
to_text_tree was fixed this session; test now exercises fallback path. Fine for now.
Worth upgrading when a FQ-callee test is written for it.

**Stub queries use callee surface column [V]:** list_stubs, detect_topology, find_abc_gaps
use `ge.callee = f.name OR ge.callee LIKE '%.' || f.name`. This is NOT broken --
LIKE handles FQ callees correctly. Replacing with target_id is a cleanup, not a fix.

## NEXT SESSION -- start here

1. **Verify RM21 probes** -- find probe test file, run against re-ingested corpus.
   Traversal changed substantially; confirm all 6 still pass before building further.

2. **dj2 path analysis (RM39 prerequisite)** -- re-ingest dj2 corpus, run bfs_callees
   from every socket handler, document: where chains break, which functions carry
   game state, which return values drive branching. File in HISTORY.md. This scopes
   RM39 Level 1 to actual patterns, not speculation.

3. **RM38 tooling investigation** -- 0.5 days: try js-callgraph, acorn/esprima via
   subprocess, pyjsparser. Entry point: `determined/ingestion/dynamic_edges.py`.
   Pick lightest tool that returns structured event bindings.

4. **RM39 Level 1** -- after step 2 identifies target patterns.
   Entry point: `determined/ingestion/parse_ast.py` Visitor.visit_Call.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
