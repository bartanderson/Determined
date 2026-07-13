Written at commit: 3bf787d
# SESSION STATE - session 159 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 159, 2026-07-12)

**Re-ingest dj2 [V]:** Full corpus re-ingest to populate new RM38/RM39 edge types.
- Ran EngineRunner directly via script (same path as UI handle_ingest).
- data_flow: 388, static: 8098, decorator: 100, thread: 1.
- http_fetch and js_event_binding were 0 -- bug found and fixed.

**Bug fixed + committed (0511bdc) [V]:** `_persist_cross_boundary_edges` got 0
HTML/JS sources because `scan_project_files` only processes .py files. File
analyses had no HTML or JS entries so the RM38 extractor block was skipped.
Fix: when flask_route_map is non-empty but html_srcs/js_srcs are empty, fall back
to reading .html/.js directly from disk via `project_meta.project_root`.
Skips .venv, node_modules, __pycache__, .git.
After fix: http_fetch: 32, js_event_binding: 18. [V]

**Validation [V]:**
- `ingest_design_docs(min_score=0.01)`: 00E picked up, 2388 rules stored, 52 docs. [V]
- `trace_http_chain('/api/party/create')`: 2 handlers (get_party_data, api_party_create),
  HTMX element, JS callers (showCreatePartyModal, showJoinPartyModal, leaveParty). [V]
- `data_flow_edges('process')`: runs; 0 results (expected -- process() called via
  result=process() pattern = Level 2, deferred). [V]

**RM42 done + committed (3bf787d) [V]:** Investigation clue board, Pass 1.
- 5th rail icon (magnifier) opens Investigation panel (sb-investigate section).
- Pin button injected into every result-block header via addResultBlock().
- Clue card model: tool-tag, subject, 400-char summary, timestamp, pin/remove.
- Max 20 cards; oldest unpinned auto-dropped at cap.
- "Ask about these clues" prefills q-input with numbered clue summaries.
- "Clear unpinned" removes all non-pinned cards.
- Rail icon flashes amber briefly on new pin.
- Verified in browser: panel opens, pin appears on result blocks, pinning creates
  card, ask composes query, clear works. [V]
- 731 passed, 1 skipped. [V]

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
| LNS | Canned reasoning lenses | OPEN (RM43) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run this session.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. readiness_check T2 uses
_list_callees_raw -- may surface unresolved edges.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.

**readiness_check T4 off by default [V]:** include_design_check=true required.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.

**RM39 Level 2 deferred [V]:** `result=fn_a(); fn_b(result)` not implemented.

**trace_http_chain decorator lookup fragile [V]:** TODO-1 in TRACKER.md covers the fix.

**dj2 re-ingested this session [V]:** http_fetch=32, js_event_binding=18, data_flow=388.

**RM42 Pass 2 deferred [V]:** Clue board is session-only JS; lost on page reload.
Pass 2 (persist to workflow_items) not yet implemented.

## NEXT SESSION -- start here

**Recommended first action:** RM43 -- canned reasoning lenses.
- RM42 (clue board) is the prerequisite -- shipped this session. [V]
- New file: `determined/agent/reasoning_lenses.py` -- lens dict
  {name, description, prompt_template, requires_db_queries}
- UI: lens selector buttons at bottom of #sb-investigate panel in console.html
- Start with 2-3 lenses: "Next action", "Blast radius", "Open questions"
- Each lens: clue summaries + optional live DB queries -> prefills Ask bar

After RM43: TODO-1 (trace_http_chain hardening), RM40 (target resolution),
RM42 Pass 2 (DB persistence for clue board).

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
