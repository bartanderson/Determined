Written at commit: e4b6125

# SESSION STATE - session 178
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 178, 2026-07-15)

**Go receiver types fixed [V]**
- `_go_param_types` now prepends method receiver (e.g. `{"name":"r","type":"Model"}`) before regular params.
- end-of-eden re-ingested: typed params 88% (was 60%). 533 symbols, 7,494 edges unchanged.
- 1 new test: `test_go_method_receiver_in_param_types`. Updated `test_go_method_param_types` (len 3 not 2).

**Plain JS excluded from annotation queue [V]**
- `_build_annotation_queue` now skips `.js` and `.jsx` files -- no type syntax, LLM annotation meaningless.
- `.ts`/`.tsx` stay in queue (TS has type annotations `_ts_param_types` can fill).
- 1 new test: `test_queue_excludes_plain_js`. 892 passed, 1 skipped [V].

**JS "typed params 0%" resolved as N/A [V]**
- Plain JS has no type syntax. `_ts_param_types` bails for non-TS/TSX by design.
- dungeoncrawler (56%) and rotjs (31%) typed params are correct -- both are TypeScript corpora (.ts files).
- SESSION_STATE had them labeled "(JS)" -- corrected in corpus table below.

**All corpora re-ingested [V]**
- dj2: 1,399 fns / 9,931 edges (static 8,595 + data_flow 1,336) / docs 43% / typed 33%
- ruggrogue re-ingested: 337 symbols / 2,741 edges (no Rust extraction changed)

**RM59 filed [V]**
- TRACKER.md: feature shape analysis -- list_features, feature_shape, development_priorities.
- CLAUDE.md active arc updated (prior items 6/20/1 were already done, arc was stale).
- Dashboard updated.

## NEXT SESSION -- start here

**Implement RM59 Phase 1:**
- `list_features([depth=1][, scope])` in `determined/agent/agent_tools.py`
- `feature_shape(feature_path)` in `determined/agent/agent_tools.py`
- Wire both into `determined/agent/tool_registry.py`
- Regression tests in `tests/regression/test_feature_shape.py` (new file)
- See TRACKER.md RM59 for full design

**Two RM59 implementation traps to avoid:**

1. **Path normalization** -- DB file_paths use backslashes on Windows.
   Directory prefix matching must normalize first:
   `REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/')` then LIKE 'dir/%'.
   Pattern already used in knowledge_status and ui_server.py mod_rows query.

2. **`subgraph_around` is the path-tracing primitive** -- lives in
   `determined/agent/graph_utils.py`. Use it (scoped) for feature_shape's
   forward walk from entry points. Don't rewrite it.

**Entry point SQL pattern (needed for feature_shape, not obvious):**
```sql
-- entry points = local symbols called by at least one caller outside the directory
SELECT DISTINCT callee FROM graph_edges
WHERE callee IN (
    SELECT name FROM functions WHERE REPLACE(file_path,'\\','/') LIKE 'dir/%'
)
AND caller NOT IN (
    SELECT name FROM functions WHERE REPLACE(file_path,'\\','/') LIKE 'dir/%'
)
```

## Corpus status [V]

| Corpus | Syms | Edges | data_flow | Docs% | Typed% | Notes |
|--------|------|-------|-----------|-------|--------|-------|
| Determined (Python) | 1,904 | 16,588 | 2,503 | 39% | 36% | [V session 177] |
| dj2 (Python+JS) | 1,399 | 9,931 | 1,336 | 43% | 33% | [V this session] |
| end-of-eden (Go) | 533 | 7,494 | 4,148 | 39% | 88% | [V this session, was 60%] |
| ruggrogue (Rust) | 337 | 2,741 | 439 | 29% | 83% | [V this session] |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 410 | 85% | 0% (N/A) | plain JS, correct |
| dungeoncrawler (TS) | 78 | 192 | 29 | 88% | 56% | TypeScript, not plain JS |
| rotjs (TS) | 626 | 2,239 | 353 | 37% | 31% | TypeScript, not plain JS |

## Known issues (carried forward)

**ingest route trap [V]:** Python corpora use EngineRunner (`python -m determined.engine.run_engine`).
  ingest_lang_corpus.py is for pure Go/Rust/JS/TS only.
**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**RM21 probes not re-run [?]:** Live LLM probe not re-run this session.
**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.
**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.
**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db
**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.
**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.
**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.
**readiness_check T4 off by default [V]:** include_design_check=true required.
**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
  knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
**dj2 ignore dirs trap [V]:** .determinedignore in dj2 repo covers all exclusions.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.
  dungeoncrawler and rotjs are TypeScript -- their typed% is real data, not noise.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
