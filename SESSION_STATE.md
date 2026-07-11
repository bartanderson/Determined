Written at commit: 16f6f6d
# SESSION STATE - session 142 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 142, 2026-07-10)

**Rich graph + virtual edge system** -- committed 16f6f6d, 545 tests pass [V]

Started from problem.odt documenting two Q5 graph traversal gaps, then expanded
to survey and close all dynamic/unlinked paths in the call graph.

### Changes made [V]

**`determined/identity/symbol_identity.py`**
- `normalize_symbol`: strips module prefix -- `pkg.mod.fn` -> `fn` (was just strip())
- `all_name_forms(name)`: returns (name, name_type) pairs for all known name forms

**`determined/shared/types.py`**
- `SymbolReference`: added `resolved: bool = False` and `edge_type: str = 'static'`

**`determined/persistence/persistence_engine.py`**
- `graph_edges` schema: added `edge_type TEXT DEFAULT 'static'` column
- `symbol_names` table: new -- (canonical_id, name, name_type) -- all known name forms
- Indexes on symbol_names(canonical_id) and symbol_names(name)
- Migration: adds `edge_type` to existing DBs
- `_persist_graph_edges`: populates symbol_names; includes edge_type in INSERT
- `_persist_cross_boundary_edges`: new -- Gap 7 cross-language + annotation edges
- `_persist_polymorphic_edges`: new -- auto-generates ABC polymorphic edges from Item 20 data
- `persist_all`: calls both new functions after graph layer

**`determined/ingestion/reingest_file.py`**
- INSERT includes edge_type; populates symbol_names after each edge insert

**`determined/agent/graph_utils.py`**
- `_resolve_to_canonical`: resolves any name form to canonical_id via symbol_names
- `shortest_path`: traverses by source_id/target_id not caller/callee strings

**`determined/ingestion/parse_ast.py`**
- Calls `extract_all_dynamic_edges(source)` after symbol extraction;
  appends results as SymbolReferences with correct edge_type

**`determined/ingestion/dynamic_edges.py`** (new)
- `extract_dispatch_dict_edges`: Gap 2 -- TOOLS/TASK_PATTERNS dict dispatch
- `extract_thread_target_edges`: Gap 3 -- Thread(target=fn)
- `extract_decorator_entry_edges`: Gap 4 -- @socketio.on / @app.route
- `extract_socketio_handler_map`: event_name -> handler_fn from Python source
- `extract_cross_language_edges`: Gap 7 -- JS socket.emit -> Python handler
- `load_virtual_edge_annotations`: Gap 8+ -- reads virtual_edges.json
- `extract_all_dynamic_edges`: runs all Python-side detectors

**`tests/regression/test_graph_utils.py`**
- _make_oracle updated with source_id/target_id/edge_type/symbol_names
- Added test_shortest_path_module_qualified_callee (Gap 1 regression)

**`tests/regression/test_dynamic_edges.py`** (new, 11 tests) [V]

### Gap taxonomy [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1 | Module-qualified callee names break BFS | FIXED |
| 2 | dict-of-callables dispatch (TOOLS) | FIXED |
| 3 | Thread(target=fn) implicit calls | FIXED |
| 4 | @socketio.on / @app.route decorators | FIXED |
| 7 | JS socket.emit -> Python handler | FIXED |
| 8 | ABC/subclass polymorphic dispatch | FIXED (auto from Item 20 data) |
| manual | Anything else cross-boundary | virtual_edges.json |

Synthetic caller nodes: `__js_client__`, `__http_client__` (auto-generated).
`__abc_base__`, `__annotation__` available in virtual_edges.json.

## Probe scorecard (Determined corpus) [?]

Not re-run this session. Last known: all 6 RM21 probes pass (commit e242815).

## Known issues (carried forward)

**Corpus DB not re-ingested [V]:**
symbol_names table and all virtual edges only populate on next ingest.
Re-ingest from UI or:
`.venv\Scripts\python -m determined.agent.local_agent --source C:\Users\bartl\dev\Determined`

**Gap 7 _source availability [?]:**
`_persist_cross_boundary_edges` reads `analysis._source` for HTML content.
FileAnalysis may not store source text -- cross-language matching silently skips if absent.
Verify on next re-ingest; fix if needed.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and inline GUIDE_DATA in
console.html are separate stores -- both must be updated together.

**ingest_design_docs project root mismatch [?]:** Must call with explicit path.

**find_abc_gaps same-file blind spot [V]:** ABC base + subclasses in same file = false gap.

**Determined corpus DB path [V]:**
`C_Users_bartl_dev_Determined.db` (183 files).

## NEXT SESSION -- start here

1. **Re-ingest Determined corpus** to populate symbol_names + all virtual/polymorphic edges
2. **Verify Gap 7** -- check if FileAnalysis stores _source; fix if cross-language edges absent
3. **Run RM21 probes** to confirm all 6 still pass after graph changes
4. **dj2 corpus probe** -- run RM21 probe suite against dj2; find gaps there

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
