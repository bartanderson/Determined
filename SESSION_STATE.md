Written at commit: 1a2d12f (+ TRACKER.md uncommitted, no code changed)
# SESSION STATE - session 166 wrap
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 166, 2026-07-13)

**RM39 L2 validated on dj2 [V]:** Re-ingested dj2 corpus. data_flow edges: 388 → 1,189
(+801 new edges from variable binding tracking). Real edges confirmed: DungeonStateNeo ←
create_dungeon, should_invoke_ai → AdjudicationEngine.process. Level 2 is working.

**Coverage map built [V]:** AST-based audit of dj2 game source (excludes .determinedignore dirs).
Deterministic counts:
- For-loop over call result blind spot: **41 occurrences** (15 files)
- Keyword arg variable pass blind spot: **341 occurrences** (56 files)
- For-loop over var (L2 partial coverage): 127 occurrences
- Static edges resolved rate: 13.4% (1,087 / 8,098) -- not a bug, a capability ceiling
- data_flow edges: high confidence (AST-derived, scope-guarded)
- Total gap: ~382 occurrences = ~24% additional coverage if L3 implemented

**RM39-L3 + JS ESTree TODO filed [V]:** docs/TRACKER.md updated with full spec:
- Python: visit_For (for x in fn()) + visit_Call keyword extension (fn(key=var))
- JS ESTree: ForOf/ForIn over CallExpression + named object literal args -- gated on
  JS corpus becoming active analysis target

**Memory burned in [V]:**
- reference_dj2_ignore.md: full .determinedignore exclusion list (Lib/, archive/, etc.)
- reference_dj2_db_schema.md: all table column names; wrong names documented (callee_fqdn,
  artifact_type, path -- all don't exist; use caller/callee, kind, file_path)

## NEXT SESSION -- start here

**Implement RM39-L3 (highest priority -- spec is complete):**
1. Open `determined/ingestion/parse_ast.py`
2. Add `visit_For` -- if `node.iter` is `ast.Call`, emit data_flow edge, bind loop var
3. Extend `visit_Call` -- iterate `node.keywords`, emit data_flow edge if `kw.value` is
   `ast.Name` in `_fn_bindings`
4. Add regression tests (same pattern as L2 tests in tests/regression/test_data_flow.py)
5. Re-ingest dj2, verify count goes from 1,189 toward ~1,530+
6. Commit

**Counting script for verification:** already written at
`scratchpad/count_l3_patterns.py` -- run against dj2 after implementation to confirm
all 41 + 341 occurrences are now emitted.

**After L3:** JS ESTree equivalent is in TRACKER as RM39-L3, gated on JS corpus need.

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

**RM42 clue pinned state not persisted [V]:** Pinned state is in-memory only (low priority).

**UI re-ingest via preview browser [V]:** socket.emit("ingest", {path}) works.

**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
Always check reference_dj2_db_schema.md memory before writing SQL.

**dj2 ignore dirs trap [V]:** Always exclude Lib/, archive/, tools/, tools.old/, og_system/,
recovered_code/, codebase_analyzer/, Scripts/. See reference_dj2_ignore.md memory.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
