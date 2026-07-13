Written at commit: 12668b2
# SESSION STATE - session 161 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 161, 2026-07-13)

**RM43 done + committed (4d0f7b0) [V]:** Canned reasoning lenses for investigation clue board.
- 5 lenses: Next action, Blast radius, Open questions, Convergence check, Not ready.
- `determined/agent/reasoning_lenses.py` -- LENS_CATALOG dict with prompt_template per lens.
- `/api/reasoning_lenses` Flask route in ui_server.py serves catalog as JSON.
- Investigation panel fetches catalog on load; lens buttons appear when clues are pinned.
- Click composes clue summaries + lens prompt template, prefills Ask bar. Same path as RM42.
- Verified in browser: catalog loaded (5 buttons), lens section shows on pin, click prefills. [V]
- 731 passed, 1 skipped. [V]

**RM40 done + committed (472452c) [V]:** resolved_only filter for direct caller/callee lookups.
- `_list_callers_raw` and `_list_callees_raw` gain `resolved_only: bool = False` param.
- `list_callers`, `list_callees`, `blast_radius` thread it through from args dict.
- `bfs_callees` and `subgraph_around` in graph_utils.py already had it -- full stack consistent.
- 4 new regression tests in test_graph_utils.py documenting the bare-name collision scenario.
- 735 passed, 1 skipped. [V]

**TODO-1 done + committed (12668b2) [V]:** http_route column for reliable Flask handler lookup.
- `FunctionRepresentation` gains `http_route: Optional[str] = None` field (shared/types.py).
- `parse_ast.py` extracts route URL from `@<x>.route('/path')` AST node in decorator loop.
- `persistence_engine.py`: `http_route TEXT` in CREATE TABLE + ALTER TABLE migration + INSERT.
- `trace_http_chain` in agent_tools.py: queries `http_route` column first (via `_url_matches`),
  falls back to decorators_json regex (for pre-migration corpora), then http_fetch edge targets.
- 3 new tests in test_http_chain.py. Fixed positional INSERT in test_intent_view_wiring.py.
- 738 passed, 1 skipped. [V]

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
| INV | Investigation context panel | DONE Pass 1 (RM42) |
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

**dj2 needs re-ingest for http_route [V]:** TODO-1 adds http_route column; existing corpus DB
has the column (migration runs) but all rows are NULL until re-ingest populates them.
trace_http_chain falls back to decorators_json regex + http_fetch edges until then.

**RM42 Pass 2 deferred [V]:** Clue board is session-only JS; lost on page reload.
Pass 2 (persist to workflow_items) not yet implemented.

## NEXT SESSION -- start here

**Recommended first action:** RM42 Pass 2 -- persist clue board to DB.
- Clue board (RM42) works in-session but is lost on page reload.
- Three API endpoints: POST /api/clues (pin), DELETE /api/clues/<id>, GET /api/clues.
- Store in workflow_items table (body = JSON card, kind = 'clue').
- Frontend: on load, fetch GET /api/clues and restore _clues array.
- On pin/remove, emit socket or fetch to sync. Same panel UI, no visual change.
- Estimated effort: 0.5 days.

**Also open:** dj2 re-ingest to populate http_route column after TODO-1 fix.
Run via EngineRunner script (same path as last re-ingest in session 159).

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
