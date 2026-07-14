Written at commit: 5d325d5

# SESSION STATE - session 170
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 170, 2026-07-13)

**LangSpec refactor -- commit e939072 [V]:**
- `LangSpec` dataclass in `language_walker.py`: callee_extractor, builtins,
  fn_ranges_builder, compute_resolved
- `_lang_spec()` returns the right LangSpec for the active language
- `_shared_call_edges(spec)` replaces `_js_call_edges`, `_go_call_edges`,
  `_rust_call_edges` (three duplicated walk loops, root cause of prior bugs)
- `call_edges()` now delegates to `_shared_call_edges(self._lang_spec())`
- Adding a new language: add callee extractor method + builtins set + LangSpec entry
- 814 passed, 1 skipped [V]

**RM54 done -- commit 5d325d5 [V]:**
- 2 new regression tests: arrow fn as caller, cross-file callee unresolved
- Cross-file resolution post-pass in `_persist_js_ts_files`: after all JS/TS files
  processed, UPDATE graph_edges SET resolved=1 where callee matches any known
  JS/TS symbol (bare name OR fqdn suffix via SUBSTR). Walker always emits
  resolved=False (single-file scope); persist layer has full corpus.
- Validated: dnd-dungeon-gen 974 edges (controller->generateDungeon chains surface)
- Validated: dungeoncrawler 163 TS edges (Game.constructor->handlePlayerInput,
  CombatSystem.executeAttack->defender.takeDamage)
- 816 passed, 1 skipped [V]

**Known trap discovered this session [V]:**
JS `resolved` was always False before RM54 because walker compares raw callee
("placeWalls") against fqdn symbol names ("gen.placeWalls") -- never matches.
compute_resolved=True in LangSpec was doing nothing. Fixed by persist post-pass.
See HISTORY.md 2026-07-13 entry.

## NEXT SESSION -- start here

**RM55: JS data flow L1/L2/L3 [V -- likely already done]**
Same situation as RM54: data_flow_edges() and all L1/L2/L3 tests are already
in place from RM53 Phase 1. Check if any spec tests are missing, validate against
dnd-dungeon-gen, mark DONE in TRACKER.md.

After RM55: RM56 (Python AST cleanup, 1-2 hrs) then RM57 (cross-language data flow).

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run this session.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.

**readiness_check T4 off by default [V]:** include_design_check=true required.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.

**RM42 clue pinned state not persisted [V]:** In-memory only (low priority).

**UI re-ingest via preview browser [V]:** socket.emit("ingest", {path}) works.

**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.

**dj2 ignore dirs trap [V]:** Always exclude Lib/, archive/, tools/, tools.old/, og_system/,
recovered_code/, codebase_analyzer/, Scripts/. See reference_dj2_ignore.md memory.

**dj2 DB edge_type not kind [V]:** graph_edges uses edge_type='data_flow', not kind.

**TRACKER.md update rule [V]:** Edit tool for status changes; scratchpad-first for new
multi-line blocks.

**JS/TS _persist_graph_edges ordering trap [V]:** Step 5c MUST come after step 5.

**Go selector_expression [V]:** Fixed 702dbce. _go_callee_name() handles it.

**Rust field_expression receiver [V]:** Fixed 405bb31. _rust_callee_name emits
"receiver.method" not just "method".

**JS resolved=False trap [V]:** Fixed in RM54 (5d325d5). Walker always emits False
(single-file scope); persist post-pass resolves against full corpus. LangSpec
compute_resolved is now effectively unused -- resolution happens in persist layer.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
