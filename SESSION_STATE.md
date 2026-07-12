Written at commit: cf9388c
# SESSION STATE - session 158 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 158, 2026-07-12)

**RM39 done [V]:** data_flow edge emission for nested-call pattern fn_b(fn_a()).
- `parse_ast.py` `visit_Call`: scans `node.args` for nested `ast.Call` nodes,
  emits `data_flow` edge caller=fn_b callee=fn_a (matches existing graph direction).
  Results tuple extended to 5 elements with edge_type; return comprehension updated.
- New tool `data_flow_edges(symbol, direction?)` queries graph_edges WHERE
  edge_type='data_flow', shows CONSUMES/RETURN VALUE sections.
- Wired into TOOLS + tool_registry (category: graph).
- 11 regression tests. 702 passed, 1 skipped [V].

**Note:** Level 2 (variable binding: `result=fn_a(); fn_b(result)`) is deferred.
More common in Python than nested-call pattern; Level 1 is foundation only.

**RM38 done [V]:** HTTP/HTMX -> Flask route chain extraction.
- `dynamic_edges.py`: four new extractors:
  - `extract_flask_route_map(py_src)` -- @app.route -> {url: handler}
  - `extract_htmx_edges(html_src, route_map)` -- hx-get/post/put/patch/delete -> handler
  - `extract_js_event_bindings(html_src)` -- onclick/on* -> JS fn, element id as caller
  - `extract_fetch_edges(js_src, route_map)` -- fetch(url) inside named JS fn -> handler
  - URL normalization: `{{ jinja_var }}` and `<flask:param>` both -> `*` for wildcard match
  - Two new edge_types: `http_fetch`, `js_event_binding`
- `persistence_engine.py` `_persist_cross_boundary_edges`: wires all three client-side
  extractors alongside existing Gap 7 socket.emit extraction.
- New tool `trace_http_chain(url)`: DOM element -> JS function -> Flask handler ->
  downstream calls (depth 2).
- Wired into TOOLS + tool_registry (category: graph).
- TODO-1 filed in TRACKER.md: `trace_http_chain` matches handlers via `decorators_json`
  string inspection -- fragile. Fix: add `http_route` column to `functions` table.
- 30 regression tests. 732 passed, 1 skipped [V].

## Gap taxonomy (cumulative) [V]

| Gap | Pattern | Status |
|-----|---------|--------|
| 1-4,7,8 | Various call graph gaps | FIXED |
| TR | Target resolution collision | DONE (RM40) |
| ICX | Inline comment extraction | DONE (RM50) |
| ANN | annotate_function tool | DONE (RM49) |
| APD | Annotation pass driver | DONE (RM51) |
| ORD | Implementation ordering | DONE (RM44) |
| CTR | Completion contract | DONE (RM45) |
| SFP | Scaffold from pattern | DONE (RM46) |
| RDY | Readiness gate | DONE (RM47) |
| MMP | Multi-method ingestion pre-pass | DONE (RM52) |
| DGP | Design-to-code delta | DONE (RM48) |
| DF | Data flow edges (Level 1) | DONE (RM39) |
| HTTP | fetch/HTMX -> Flask route | DONE (RM38) |
| INV | Investigation context panel | OPEN (RM42) |
| LNS | Canned reasoning lenses | OPEN (RM43) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. readiness_check T2 uses
_list_callees_raw which does NOT filter resolved_only -- may surface unresolved edges.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.

**readiness_check T4 off by default [V]:** include_design_check=true required for design tier.

**00E not ingested [V]:** docs/design/00E in dj2 scored 0.04, below default min_score=0.05.
Needs min_score=0.01 to pick it up.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.

**design_gaps Level A embedding [?]:** Embedding-intensive; no caching; may be slow.

**RM39 Level 2 deferred [V]:** `result=fn_a(); fn_b(result)` not implemented.

**trace_http_chain decorator lookup fragile [V]:** Matches handlers via decorators_json
string inspection. TODO-1 in TRACKER.md covers the fix.

**dj2 not re-ingested this session [V]:** RM38 and RM39 edges not yet in dj2 DB.
Must re-ingest to populate http_fetch, js_event_binding, data_flow edges.

## NEXT SESSION -- start here

All planned RM items are DONE or explicitly deferred.
Remaining open: RM42 (investigation panel, UI), RM43 (lenses, requires RM42).
Filed: TODO-1 (trace_http_chain route lookup hardening).

**Recommended first action:**
Re-ingest dj2 corpus to populate new edge types, then validate:
- `ingest_design_docs(min_score=0.01)` to pick up 00E
- Full re-ingest for http_fetch, js_event_binding, data_flow edges
- `trace_http_chain('/api/party/create')` and `data_flow_edges('process')`
  to confirm edges show up against real data

Then ask Bart: RM42 (UI panel), RM43 (lenses), TODO-1 (hardening), or new items?

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
