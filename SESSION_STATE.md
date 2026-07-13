Written at commit: dd94562
# SESSION STATE - session 163 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 163, 2026-07-13)

**dj2 re-ingest done [V]:** Populated http_route column (93 functions) and http_fetch/js_event_binding edges.
- Ran via Python script (bypassed UI server) -- see HISTORY.md for why and correct UI procedure.
- dj2 DB: 153 files, 1321 functions, 93 with http_route, 32 http_fetch edges, 18 js_event_binding edges.

**RM41 confirmed done + tests added (dd94562) [V]:** HTTP fetch/HTMX -> Flask route edges were already
implemented in dynamic_edges.py and persistence_engine.py. Gap was missing regression tests.
- 16 new tests: extract_flask_route_map, extract_htmx_edges, extract_js_event_bindings,
  extract_fetch_edges, _url_matches (URL normalization with Jinja2/Flask param wildcards).
- 754 passed, 1 skipped. [V]
- TRACKER.md updated: RM41 marked DONE.

**UI re-ingest procedure documented (HISTORY.md) [V]:**
- Re-analyze button on fresh server start -> native Windows folder picker opens on desktop.
- User selects project folder there; ingest runs. Do NOT try to automate via preview browser.
- If automating: socket.emit("ingest", {path: "..."}) works (socket is live in preview browser).
- Root cause of confusion: _source_path only set after ingest, not on server restart with existing DB.

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
| HTTP | fetch/HTMX -> Flask route | DONE (RM38/RM41) |
| INV | Investigation context panel | DONE Pass 1+2 (RM42) |
| LNS | Canned reasoning lenses | DONE (RM43) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run this session.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. readiness_check T2 uses
_list_callees_raw -- may surface unresolved edges. Pass resolved_only=True explicitly.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.

**readiness_check T4 off by default [V]:** include_design_check=true required.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.

**RM39 Level 2 deferred [V]:** `result=fn_a(); fn_b(result)` not implemented.

**RM42 clue pinned state not persisted [V]:** pinned=True/False is stored in initial POST content
but toggling pin after creation does not PATCH the DB row. Pinned state is in-memory only.
Low priority -- pinned flag only affects "Clear unpinned" button behavior.

**UI re-ingest via preview browser [V]:** socket.emit("ingest", {path}) works but
Re-analyze button silently falls through to browse dialog when _source_path is empty
(fresh server start). See HISTORY.md for full procedure.

## NEXT SESSION -- start here

**Recommended next action:** RM39 -- data flow edges Level 1.
- Emit data_flow graph edges when fn_b(fn_a()) nested-call pattern detected in AST.
- Entry point: determined/ingestion/parse_ast.py Visitor.visit_Call.
- Storage: extend graph_edges with edge_type='data_flow' (Option B -- existing traversal handles it).
- Estimated effort: ~2 days.
- Prerequisite analysis done (dj2 path analysis, TRACKER.md RM39 section).

**Also open:**
- RM21 remaining techniques (2-6): gated on Technique 1 proving insufficient.
- files.role column: implement or remove (low priority).
- RM38: JS event chain via socket.emit (deferred -- dj2 has no client-side socket.emit).

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
