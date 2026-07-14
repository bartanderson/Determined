Written at commit: 6632db4

# SESSION STATE - session 171
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 171, 2026-07-13)

**RM55 + RM56 confirmed done [V]:**
- JS data flow tests (L1/L2/L3): 4 tests passing. Code already in language_walker.py.
- parse_ast.py _last_call_fqdn.pop() fix already in place.
- Both marked DONE in TRACKER.md.

**RM57 done -- commit 6632db4 [V]:**
- `_extract_response_shape(fn_node)` in parse_ast.py: walks function body for
  `return jsonify({"key": ...})` / `return jsonify(key=v)` / `return {"key": ...}`.
  Only runs when `http_route` is set (route handler only).
- `response_shape: list[str]` field added to `FunctionRepresentation` in types.py.
- Persistence: route handlers with response_shape get `knowledge_artifact(kind='response_shape',
  subject=fn_name, content=json(keys))` in persistence_engine.py.
- `LanguageWalker.response_consumers()` / `_js_response_consumers()` in language_walker.py:
  detects `const {key} = await resp.json()` (object_pattern destructuring) and property
  access on variables bound from `.json()` calls. Returns [(fqdn, [keys])].
- `cross_language_linker.py` (new file): `run_cross_language_link(conn, corpus_root)` --
  loads http_fetch edges + response_shape artifacts + scans JS/TS files for response_consumers,
  emits `cross_language` graph_edges (caller=js_fn, callee=flask_handler), stores
  `response_mismatch` knowledge_artifacts (needs_review=1) for consumed keys not in shape.
- Wired as step 5d in persistence_engine.persist_all after _persist_js_ts_files.
- 15 regression tests. 831 passed, 1 skipped [V].

**RM58 done [V]:**
- end-of-eden (Go) cloned to C:\Users\bartl\dev\corpora\end-of-eden
- ruggrogue (Rust) already existed at C:\Users\bartl\dev\corpora\ruggrogue
- All 4 corpora verified present: dnd-dungeon-gen, dungeoncrawler, rotjs, end-of-eden, ruggrogue
- TRACKER marked DONE.

**Arc complete [V]:**
RM53-58 (LanguageWalker arc) all DONE. No open TODO items remain in TRACKER.md.

## NEXT SESSION -- start here

**No open TODO items.** Time to plan the next arc.

Options to discuss with Bart:
1. **Go/Rust validation** -- ingest end-of-eden and ruggrogue, confirm call graphs surface
   correctly, mark RM58 fully validated (currently just "cloned").
2. **dj2 cross-language validation** -- re-ingest dj2 with RM57, verify cross_language edges
   appear for fetch→Flask chains, check response_mismatch artifacts for real gaps.
3. **New arc planning** -- what's the next capability gap? (items 6/20/1 from CLAUDE.md arc
   are all done; likely need fresh brainstorm against current dj2 analysis pain points).

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
(single-file scope); persist post-pass resolves against full corpus.

**RM57 response_consumers scope [V]:** LanguageWalker constructor is (src, file_path, language)
not (src, language, basename). basename derived from file_path internally.

**graph_edges no provenance column [V]:** cross_language linker uses edge_type='cross_language'
as the type discriminator (not a provenance column). Stale edges deleted by edge_type.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
