Written at commit: 127f43d
# SESSION STATE - session 164 handoff
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 164, 2026-07-13)

**RM39 confirmed already done [V]:** data_flow edge emission was already implemented in
parse_ast.py (visit_Call, lines 596-643: fn_b(fn_a()) pattern), data_flow_edges and
trace_data_flow tools in agent_tools.py. 11 regression tests in test_data_flow.py pass.
TRACKER.md was just not updated.

**RM42 confirmed already done [V]:** Investigation panel Pass 1+2 both done.
ui_server.py has /api/clues GET/POST/DELETE. workflow_items kind='clue'. Pass 2 persistence
confirmed working. TRACKER.md updated.

**TRACKER.md corrected (b32f2c3) [V]:** RM39 and RM42 marked DONE. Dashboard updated.
754 passed, 1 skipped. [V]

**Level 1 data_flow coverage validated on dj2 [V]:**
- 388 total edges; 57% involve builtins (list/str/int/print wrapping -- low signal)
- 168 real app-level edges after filtering; dominated by PerlinNoise._lerp math recursion
- Priority targets (process, execute, move_party) = 0 edges each
- All high-value chains follow `result=fn(); use(result)` -- Level 2 pattern
- Decision: Level 2 (variable binding) is required to surface meaningful app-level data flow

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
| DF | Data flow edges (Level 1) | DONE (RM39); Level 2 needed for real coverage |
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

**RM39 Level 2 deferred [V]:** `result=fn_a(); fn_b(result)` variable binding not implemented.
~2 weeks effort. Level 1 coverage on dj2: 57% builtin noise, priority targets get 0 edges.
Level 2 is the meaningful work. Build when data flow tracing is actively needed.

**RM42 clue pinned state not persisted [V]:** Pinned state is in-memory only (low priority).

**UI re-ingest via preview browser [V]:** socket.emit("ingest", {path}) works.
Re-analyze button falls through to native folder picker when _source_path empty (fresh start).

## NEXT SESSION -- start here

**All major RM items are DONE.** Real open work:

1. **RM39 Level 2 (variable binding tracking):** ~2 weeks.
   Entry point: parse_ast.py -- new visit_Assign that tracks `name = fn()` bindings,
   then in visit_Call checks if any arg is a tracked binding and emits data_flow edge.
   Per-function binding map needed (dict from name -> callee fqdn, scoped to current function).
   This is the work that surfaces process(), execute(), move_party() in the graph.

2. **RM38** (JS event chain): deferred -- dj2 has no client-side socket.emit.

3. **RM21 remaining techniques (2-6):** deferred, gated on Technique 1 proving insufficient.

4. **files.role column:** low priority -- implement or remove.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
