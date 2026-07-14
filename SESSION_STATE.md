Written at commit: 3c68ec0

# SESSION STATE - session 175
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 175, 2026-07-14)

**Step 0: Re-ingested dj2 and Determined [V]**
- dj2: cross_language=33 (was 0), js_event_binding=15 (was 0) -- now correct.
- Determined: data_flow=3,157 (was 0) -- now correct.
- Key trap discovered and documented in HISTORY.md: non-Python corpora (JS/Go/Rust)
  must use tools/ingest_lang_corpus.py, NOT EngineRunner.run(). EngineRunner only
  discovers .py files and raises "Engine ingestion produced no analyses" on pure
  JS/Go/Rust corpora.

**7432bf3 -- Go/Rust typed params [V]**
- _go_param_types(): extracts {name, type} from parameter_declaration nodes in Go
  function_declaration and method_declaration. Strips leading * from pointer types.
- _rust_param_types(): extracts {name, type} from parameter nodes in Rust function_item.
  self parameters (no type field) are skipped naturally.
- Both wired into _go_symbols() and _rust_symbols() via param_types_json= arg.
- 8 new tests. 885 passed, 1 skipped.

**3c68ec0 -- Go/Rust data_flow edges [V]**
- _go_data_flow(): L1 via nested call_expression in arguments, L2 via
  short_var_declaration (:= binds). Uses _go_callee_name() and _go_fn_ranges().
- _rust_data_flow(): L1 via nested call_expression, L2 via let_declaration.
  Inner _rust_callee() handles identifier, scoped_identifier, field_expression.
- Both wired into data_flow_edges() dispatcher.
- 6 new tests. 891 passed, 1 skipped.

**Gap 3: JS corpora ingested [V]**
- dnd-dungeon-gen: 291 syms, 974 edges
- dungeoncrawler: 78 syms, 163 edges
- rotjs: 626 syms, 1,886 edges (6 js_event_binding)

**Gap 4: ruggrogue external_interfaces.json [V]**
- Created C:\Users\bartl\dev\corpora\ruggrogue\external_interfaces.json
  with Iterator (next), From (from), Default (default), Display (fmt).
- Re-ingested ruggrogue: interface_dispatch 0 → 12. trait_dispatch stays 4.

## Corpus status (all up to date) [V]

| Corpus | Syms | Edges | Notable edge types |
|--------|------|-------|--------------------|
| dj2 (Python+JS) | 1,399 | 10,206 | data_flow=1611, cross_lang=33, js_event=15 |
| Determined (Python) | 2,048 | 23,499 | data_flow=3157, polymorphic=18 |
| end-of-eden (Go) | 533 | 3,346 | interface_dispatch=41 |
| ruggrogue (Rust) | 337 | 2,343 | interface_dispatch=12, trait_dispatch=4 |
| dnd-dungeon-gen (JS) | 291 | 974 | static only |
| dungeoncrawler (JS) | 78 | 163 | static only |
| rotjs (JS) | 626 | 1,886 | js_event_binding=6 |

## NEXT SESSION -- start here

**No open items in TRACKER.md [V].** Remaining work from gap list:

**Gap 5: Go/Rust resolution rate improvement**
Go is at ~15.6%, Rust at ~7.5%. Most unresolved edges are external stdlib calls
(expected). But in-corpus method calls also fail because receiver type isn't tracked
at the point of call resolution. Now that param_types_json is populated, a type-guided
resolution pass could match `x.Method()` to `ReceiverType.Method` when x's declared
type is known. This requires a new resolution post-pass in _persist_js_ts_files or
a new Go/Rust equivalent. Medium complexity, would move resolution rates meaningfully.

**Next natural work: Item 6 (live sync loop) or Item 20 (call graph accuracy)**
See CLAUDE.md "Active work arc" for details. Item 6 (incremental re-ingest) is
prerequisite for Item 20 (type annotation exploitation needs re-ingest to populate
new columns). Both are medium complexity (~1 day each).

## Known issues (carried forward)

**ingest_lang_corpus.py for non-Python corpora [V]:** Use tools/ingest_lang_corpus.py
  NOT EngineRunner.run() for pure JS/Go/Rust corpora. Documented in HISTORY.md.
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
**Go/Rust data_flow edge counts [?]:** Not yet evaluated against Go/Rust corpora post-commit.
  Re-ingest end-of-eden and ruggrogue to populate data_flow edges there.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
