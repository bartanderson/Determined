Written at commit: dd71dec
# SESSION STATE - session 168 wrap
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 168, 2026-07-13)

**Process improvement [V]:**
- TRACKER.md update rule added to CLAUDE.md: Edit tool for status changes;
  scratchpad-first for new multi-line item blocks. Memory saved.

**RM56 done [V]:**
- `_last_call_fqdn.pop(node_id, None)` committed (was in working tree from session 167).
- Tuple-unpack comment added to visit_For (known limitation documented in place).
- All 26 data_flow tests pass [V].
- Committed: cc45439

**RM53 Phase 1 done [V]:**
- `determined/ingestion/language_walker.py` created (~620 lines):
  - `LanguageWalker(src, file_path, language)` with `.symbols()`, `.call_edges()`,
    `.data_flow_edges()` public API
  - JS/TS: named fns, arrow fns, class methods, object literal methods; fqdn convention
    `<basename>.<fn>` for top-level, `<ClassName>.<method>` for class methods
  - Call edges: bare + member calls, built-in filtering (_JS_BUILTINS), scope attribution
    via fn_ranges; callee is raw name from call site (cross-file resolution in persist layer)
  - Data flow L1 (nested arg), L2 (var binding), L3a (for-of / for_in_statement with
    operator='of'), L3b (object named arg); provenance tags match Python side
  - Go Phase 2 stub: function_declaration + method_declaration → `<pkg>.<Fn>`
  - Rust Phase 3 stub: function_item + impl block methods → `<mod>::<fn>`
  - `detect_language(file_path)` helper: ext → ast-grep language string
- `tests/regression/test_language_walker.py`: 27 tests, all pass [V]
- Key discovery: tree-sitter JS uses `for_in_statement` (not `for_of_statement`) for
  both for-in and for-of; distinguish via `operator` field == 'of'
- Full suite: 797 passed, 1 skipped [V]
- Committed: dd71dec

**NOT YET DONE (RM53 Phase 1 still open):**
- LanguageWalker is NOT yet wired into `persist_all` or `scan_project_files`.
  JS/TS files are NOT ingested into the DB yet. Wire-in is the next step.

## NEXT SESSION -- start here

**Wire LanguageWalker into ingestion pipeline (completes RM53 Phase 1):**

1. Extend `scan_project_files` to return `.js`/`.ts`/`.jsx`/`.tsx` files alongside `.py`
   - File: `determined/ingestion/scan_project_files.py`
   - Add JS/TS extensions to the glob/walk; apply same ignore-dir rules

2. In `persist_all` (persistence_engine.py:708), after step 4 (PERSIST FILE LAYER),
   add step 4b: for each non-Python file in file_analyses (or a new `js_files` list),
   call `LanguageWalker(src, file_path, language).symbols()` and insert into `functions`
   table; call `.call_edges()` and insert into `graph_edges`.

3. Validate against dnd-dungeon-gen corpus:
   - Re-ingest `C:\Users\bartl\dev\corpora\dnd-dungeon-gen`
   - Confirm `controller`, `dungeon`, `room`, `item` module symbols appear in DB
   - Confirm `controller.generateDungeon → dungeon.buildDungeon` type call chain surfaces

4. Tests for the wire-in (not yet written):
   - `test_language_walker_persist.py` or extend existing test
   - Fixture: ingest a 2-file JS corpus; verify symbols + edges land in DB

**Entry points:**
- `determined/ingestion/scan_project_files.py` — add JS/TS extensions
- `determined/persistence/persistence_engine.py:persist_all` — add step 4b
- Import: `from determined.ingestion.language_walker import LanguageWalker, detect_language`

## Known issues (carried forward)

**RM53 wire-in not done [V]:** LanguageWalker exists but is not called from persist_all.
JS/TS files produce no DB rows yet. This is the immediate next step.

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

**TRACKER.md update rule [V]:** Edit tool for status changes; scratchpad-first for new
multi-line blocks. Documented in CLAUDE.md + memory.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
