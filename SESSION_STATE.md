Written at commit: f6ac757
# SESSION STATE - session 167 wrap
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 167, 2026-07-13)

**RM39-L3 implemented and verified [V]:**
- `visit_For` in parse_ast.py: emits `data_flow_for_iter` edge when iterating over a
  call result; binds loop target var(s) in `_fn_bindings` for downstream tracking.
- `visit_Call` keyword extension: emits `data_flow_var_kwarg` edge for `fn(key=var)`
  where var is bound; skips `**kwargs` unpacks.
- 8 new regression tests; all 26 data_flow tests pass [V].
- Full suite: 770 passed, 1 skipped [V].
- dj2 re-ingested: data_flow edges 1,189 → **1,611** (+422, exceeds projected ~341) [V].
- Committed: 486dbf2

**RM56 Python cleanup partially done [V]:**
- `_last_call_fqdn.pop(node_id, None)` fix applied (clears consumed entries, prevents
  id() reuse collisions). Edit is in parse_ast.py but NOT yet committed -- still in
  working tree at session end. The outer_fqdn dedup analysis showed the two uses are
  semantically different (can't share), documented in session notes.

**RM53-58 designed and committed [V]:**
- RM58: 5 validation corpora across 4 languages. JS/TS already cloned [V]:
  - `C:\Users\bartl\dev\corpora\dnd-dungeon-gen` (112 JS files)
  - `C:\Users\bartl\dev\corpora\dungeoncrawler` (14 TS files, exact hierarchy confirmed)
  - `C:\Users\bartl\dev\corpora\rotjs` (49 TS files)
  - Go: BigJk/end_of_eden -- clone before Go phase of RM53
  - Rust: tung/ruggrogue -- clone before Rust phase of RM53
- RM53: `LanguageWalker` in `determined/ingestion/language_walker.py`, ast-grep backend
  (`pip install ast-grep-py`), 3 phases: JS/TS → Go → Rust. 26 languages for free.
- RM54: JS/TS static call graph via LanguageWalker.call_edges()
- RM55: JS/TS data flow L1/L2/L3 via LanguageWalker.data_flow_edges(); same provenance
  tags as Python side for unified querying
- RM56: Python AST cleanup (see above -- partial)
- RM57: Cross-language data flow (Python response shape → JS consumer); gates on RM55
- Committed: fe0c82d, f6ac757

## NEXT SESSION -- start here

**Option A: Finish RM56 (15 min, trivial):**
- Verify the `_last_call_fqdn.pop()` edit is still in parse_ast.py (not committed yet)
- Add the tuple-unpack comment to visit_For
- Run 26 data_flow tests, commit
- Mark RM56 done in TRACKER.md

**Option B: Start RM53 Phase 1 (LanguageWalker, JS/TS symbols):**
1. `pip install ast-grep-py` in venv
2. Create `determined/ingestion/language_walker.py` with `LanguageWalker` class
3. Phase 1: JS/TS symbol extraction via ast-grep patterns
4. Wire into `persistence_engine.persist_all` after Python symbols
5. Tests in `tests/regression/test_language_walker.py`
6. Validate against dnd-dungeon-gen and dungeoncrawler corpora

**Recommended order:** Finish RM56 first (cleans up uncommitted edit), then RM53.

## Known issues (carried forward)

**RM56 partial [?]:** `_last_call_fqdn.pop()` fix in parse_ast.py NOT committed.
Verify it's still there before starting next session. Outer_fqdn duplication is
intentional (different semantics in visit_For vs visit_Call) -- document only.

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

**dj2 DB edge_type not kind [V]:** graph_edges uses edge_type='data_flow', not kind.
Burned in this session when re-ingest count query failed with "no such column: kind".

**ast-grep-py not yet installed [?]:** `pip install ast-grep-py` needed before RM53.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
