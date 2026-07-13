Written at commit: 89fdcaa
# SESSION STATE - session 162 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 162, 2026-07-13)

**RM42 Pass 2 done + committed (89fdcaa) [V]:** Clue board persistence across page reloads.
- 3 new Flask routes in ui_server.py: GET /api/clues, POST /api/clues, DELETE /api/clues/<id>.
- Clues stored as workflow_items (kind='clue', status='active'/'deleted', content=JSON card).
- `from datetime import datetime` added to ui_server.py imports.
- pinClue() POSTs on add, stores db_id on clue object.
- Remove button DELETEs via API (only if db_id present).
- Page load fetches GET /api/clues and restores _clues array before first _renderAll().
- Verified in browser: pin → POST 200, reload → GET restores card, remove → DELETE 200, reload → empty. [V]
- 738 passed, 1 skipped (no change to test count -- no new tests needed for UI-only pass). [V]

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

**dj2 needs re-ingest for http_route [V]:** TODO-1 adds http_route column; existing corpus DB
has the column (migration runs) but all rows are NULL until re-ingest populates them.
trace_http_chain falls back to decorators_json regex + http_fetch edges until then.

**RM42 clue pinned state not persisted [V]:** pinned=True/False is stored in initial POST content
but toggling pin after creation does not PATCH the DB row. Pinned state is in-memory only.
Low priority -- pinned flag only affects "Clear unpinned" button behavior.

## NEXT SESSION -- start here

**Recommended next action:** dj2 re-ingest to populate http_route column.
- Run via EngineRunner script (same path as last re-ingest in session 159).
- After re-ingest, trace_http_chain will use http_route primary lookup for dj2.

**Also open (TRACKER.md items 6, 20, 1):**
- Item 6: live sync loop (incremental re-ingest per file).
- Item 20: call graph accuracy (type annotation exploitation + __init__ tracking).
- Item 1: files.role column (implement or remove).

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
