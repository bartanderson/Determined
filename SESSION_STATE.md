Written at commit: f2d1553

# SESSION STATE - session 175
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 175, 2026-07-14)

**Step 0: Re-ingested dj2 and Determined [V]**
- dj2: cross_language=33 (was 0), js_event_binding=15 (was 0).
- Determined: data_flow=3,157 (was 0).
- Key trap: non-Python corpora must use tools/ingest_lang_corpus.py, NOT
  EngineRunner.run(). Documented in HISTORY.md.

**7432bf3 -- Go/Rust typed params [V]**
- _go_param_types(): parameter_declaration nodes, strips leading *.
- _rust_param_types(): parameter nodes in function_item; self skipped naturally.
- Wired into _go_symbols() and _rust_symbols().
- 8 new tests. 885 passed, 1 skipped.

**3c68ec0 -- Go/Rust data_flow edges [V]**
- _go_data_flow(): L1 nested call args, L2 short_var_declaration (:=).
- _rust_data_flow(): L1 nested call args, L2 let_declaration.
- 6 new tests. 891 passed, 1 skipped.

**f2d1553 -- Wire data_flow_edges() into persist layer [V]**
- _persist_js_ts_files() was calling call_edges() but NOT data_flow_edges().
- Added insert loop for data_flow_edges() after call_edges() loop.
- 891 passed, 1 skipped.

**Gap 3: JS corpora ingested [V]**
- dnd-dungeon-gen: 291 syms, 974 edges
- dungeoncrawler: 78 syms, 163 edges
- rotjs: 626 syms, 1,886 edges (6 js_event_binding)

**Gap 4: ruggrogue external_interfaces.json [V]**
- Created C:\Users\bartl\dev\corpora\ruggrogue\external_interfaces.json
  with Iterator/From/Default/Display traits.
- interface_dispatch: 0 → 12.

## Corpus status (all current) [V]

| Corpus | Syms | Edges | data_flow | dispatch |
|--------|------|-------|-----------|----------|
| dj2 (Python+JS) | 1,399 | 10,206 | 1,611 | cross_lang=33, js_event=15 |
| Determined (Python) | 2,048 | 23,499 | 3,157 | polymorphic=18 |
| end-of-eden (Go) | 533 | 7,494 | **4,148** | iface_dispatch=41 |
| ruggrogue (Rust) | 337 | 2,782 | **439** | iface_dispatch=12, trait=4 |
| dnd-dungeon-gen (JS) | 291 | 974 | 0 | - |
| dungeoncrawler (JS) | 78 | 163 | 0 | - |
| rotjs (JS) | 626 | 1,886 | 0 | js_event=6 |

end-of-eden notable: data_flow (4,148) exceeds static (3,305) -- Go chains heavily.

## NEXT SESSION -- start here

**No open items in TRACKER.md. Next work: Item 6 or Item 20 (see CLAUDE.md).**

Item 6 (live sync loop): incremental re-ingest by file_path, edge delta propagation.
Item 20 (call graph accuracy): type annotation exploitation + __init__ attribute tracking.
  Item 6 should come first -- Item 20 needs re-ingest to populate new columns.

**Optional follow-on: JS data_flow for pure-JS corpora**
dnd-dungeon-gen, dungeoncrawler have 0 data_flow. JS data_flow IS implemented
(_js_data_flow()) but these corpora may not trigger it -- check if the LanguageWalker
is being called with the right language. rotjs has 0 too. May need investigation.

## Known issues (carried forward)

**ingest_lang_corpus.py for non-Python corpora [V]:** Use tools/ingest_lang_corpus.py,
  NOT EngineRunner.run(). Documented in HISTORY.md.
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
**dj2 ignore dirs trap [V]:** Always exclude Lib/, archive/, tools/, tools.old/, og_system/,
  recovered_code/, codebase_analyzer/, Scripts/.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**JS corpora data_flow=0 [?]:** dnd-dungeon-gen, dungeoncrawler, rotjs show 0 data_flow
  despite _js_data_flow() being implemented. Not investigated yet.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
