Written at commit: 6feb238
# SESSION STATE - session 165 in progress
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 165, 2026-07-13)

**RM39 Level 2 done [V]:** Variable binding data flow tracking implemented in parse_ast.py.
Commit 6feb238. 762 passed, 1 skipped [V].

**What was built:**
- `Visitor._fn_bindings`: per-function dict `{var_name -> callee_fqdn}`, pushed/popped
  on function entry/exit via visit_FunctionDef. Bindings never cross function boundaries.
- `Visitor._last_call_fqdn`: `{id(call_node) -> fqdn}`, set in visit_Call BEFORE
  generic_visit so visit_Assign can read the RHS fqdn after traversal completes.
- `visit_Assign`: calls `generic_visit(node)` first (fires visit_Call on the RHS),
  then registers binding if `target[0]` is a simple `ast.Name` and value is an `ast.Call`.
  Only tracks simple `name = fn()` -- not tuple unpacking, augmented assign, module-level.
- `visit_Call` Level 2 addition: for each positional `ast.Name` arg, checks `_fn_bindings`;
  if found emits `data_flow` edge with provenance `["data_flow_var"]`.
- 7 new regression tests; existing Level 2 marker test converted to affirmation.

**What Level 2 covers:**
- `result = fn_a(); fn_b(result)` -> data_flow edge fn_b -> fn_a [V]
- Variable rebinding: latest assignment wins [V]
- Chained bindings: `a=fn_a(); b=fn_b(a); fn_c(b)` -> two data_flow edges [V]
- Level 1 + Level 2 coexist: `fn_c(fn_a(), result)` -> both detected [V]
- Multi-function independence: same var name in different functions tracked separately [V]
- Bindings scoped to function: never leak into nested functions [V]
- Module-level assignments not tracked [V]

**What Level 2 does NOT cover (deferred until corpus queries surface the need):**
- Keyword args: `fn_b(x=result)` -- only positional args tracked
- Starred args: `fn_b(*args)` -- skipped
- Tuple unpacking: `a, b = fn_a()` -- skipped
- For-loop iteration: `for x in fn_a(): fn_b(x)` -- skipped

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
| DF | Data flow edges Level 1 | DONE (RM39 L1) |
| DF2 | Data flow edges Level 2 | DONE (RM39 L2, this session) |
| HTTP | fetch/HTMX -> Flask route | DONE (RM38/RM41) |
| INV | Investigation context panel | DONE Pass 1+2 (RM42) |
| LNS | Canned reasoning lenses | DONE (RM43) |

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. readiness_check T2 uses
_list_callees_raw -- may surface unresolved edges. Pass resolved_only=True explicitly.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.

**readiness_check T4 off by default [V]:** include_design_check=true required.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.

**RM42 clue pinned state not persisted [V]:** Pinned state is in-memory only (low priority).

**UI re-ingest via preview browser [V]:** socket.emit("ingest", {path}) works.

## NEXT SESSION -- start here

**All major RM items including RM39 L2 are now DONE.**

1. **Validate Level 2 on dj2 corpus (highest priority -- quick win):**
   Re-ingest dj2 (full or per-file), then:
   `SELECT COUNT(*) FROM graph_edges WHERE edge_type='data_flow'` -- compare to Level 1 baseline
   Then: `data_flow_edges({"symbol": "process", "direction": "in"})` -- should now surface
   callers passing results of other calls into process().
   Entry: UI -> Re-analyze, or `reingest_file` on adjudication_engine.py, world_app.py etc.

2. **RM38** (JS event chain): deferred -- dj2 has no client-side socket.emit.

3. **RM21 remaining techniques (2-6):** deferred, gated on Technique 1 proving insufficient.

4. **files.role column:** low priority -- implement or remove.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
