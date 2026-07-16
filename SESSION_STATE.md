Written at commit: 06d17eb

# SESSION STATE - session 194
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 194, 2026-07-16)

**Full pipeline run on dj2 world/ [V]**
Ran feature_work_plan -> explore_stub -> verify_implementation -> detect_doc_drift
against all 10 stubs in world/. Found three tool gaps immediately.

**Gap fix 1: verify_implementation body inspection [V]** (9f6e3ab)
When still is_stub=1, reads source at file_path:line_number and classifies body:
  pass_only | return_empty | has_substance | unreadable
process_consequences = pass_only. _get_encounter_context = return_empty (return {}).
Tells caller whether it's a genuine stub or an ingest miss.

**Gap fix 2: detect_doc_drift false-PASS + stub design_note check [V]** (9f6e3ab)
Was silently PASSing when feature had 0 implemented fns (all stubs). Fixed: now
distinguishes "none found" from "all covered". Added Check 3: stubs with no design_note
(the pre-implementation doc gap the tool was previously blind to).
All 10 world/ stubs flagged as lacking design_notes.

**Gap fix 3: explore_stub caller dedup [V]** (9f6e3ab)
_register_world_tools was showing __init__ x6. Dedup by (name, file) before display.

**EP definition work [V]** (06d17eb)
Root cause: graph_edges stores callee as FQDN (ActionQueue.dequeue) but EP check
queried bare name (dequeue) -> 463 false EPs out of 704 apparent no-callers in world/.

Fixes:
- _has_callers(conn, name): bare name OR '%.name' suffix -- FQDN-aware
- _ep_tier(name, fp, decs, http): explicit_http | explicit_tool | protocol | test | inferred
  Protocol = dunders + classmethods + serializers (to_dict/from_dict/etc)
  explicit_tool = tool( decorator in decorators_json
- detect_doc_drift: tiered EP check; explicit always shown; inferred grouped by file,
  top_n=20; 638-item flood -> 8 explicit + 184 inferred, actionable output
- list_entry_points: new tool; world/ = 15 AI tool EPs + 185 inferred

**Architecture reminder from Bart [V]**
Language-specific detection belongs behind the language wall (parse_ast.py for Python,
JS walker for JS, etc). Common patterns (entry points, registration) live in shared
graph layer as edge types. Tools query the graph -- they do NOT detect Python patterns.
UI redesign needed but deferred until pipeline shape is stable.

## NEXT SESSION -- start here

**Immediate: function_reference edge type in parse_ast.py**

Root cause of remaining 185 inferred EPs: parse_ast.py only captures ast.Call nodes.
Function references passed as dict values are invisible:
  `guard_registry={'price_too_low': builtins.price_lt}` in adjudication_engine.__init__
  builtins.price_lt is ast.Attribute in a dict value -- never emitted as graph edge.

Three registration patterns to detect (all Python-wall, all in parse_ast.py):
  1. ast.Dict values that are ast.Name/ast.Attribute resolving to local/imported function
     -> emit edge_type='function_reference' from current_function to referenced fn
  2. register_action(name, func) / register(name, func) -- 2-arg method calls where
     second arg is a function reference -> same edge type
  3. Callback keyword args: Thread(target=func), sorted(key=func), on_any(callback=func)
     -> same edge type

The shared layer: graph_edges.edge_type='function_reference' already exists in schema.
_has_callers() already queries graph_edges generically -- picks it up automatically.
DO NOT handle this in agent_tools.py -- wrong layer.

After adding: re-ingest dj2, re-run list_entry_points world/ -- expect inferred EP
count to drop significantly (most builtins.py functions should gain callers).

Files to touch:
  - determined/ingestion/parse_ast.py: new _extract_function_references() pass
  - determined/ingestion/persistence_engine.py: wire new pass into ingest pipeline
  - tests/regression/: add tests for function_reference edges

**Design read before coding:**
Read docs/sots.md for relevant tenets before implementing. The key tension here:
- Tenet: deterministic before semantic (dict-literal detection is pure AST, good)
- Tenet: blast radius -- parse_ast.py changes affect every Python corpus; need tests

## Corpus status [V] (unchanged from prior session)

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs; 1 UNGROUNDABLE, 1 MISSING_BRIDGE, 8 BLOCKED |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested, EP counts correct |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |
| Commonplace (Python) | 31 | 168 | 0 | re-ingested session 188; http_route populated [V] |

## Known issues (carried forward)

**walk_call_chain FQDN trap [V]:** FIXED session 188.
**concept extraction scope [V]:** single-word capitalised English words excluded by design.
**feature_shape vs dev_priorities% inconsistency [V]:** different counting methods, not a bug.
**ingest route trap [V]:** Python corpora use EngineRunner. ingest_lang_corpus.py is Go/Rust/JS/TS only.
**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.
**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.
**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db
**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.
**DB schema trap [V]:** graph_edges: caller/callee cols not callee_fqdn; no callee_file for JS.
  knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
**dj2 ignore dirs trap [V]:** .determinedignore in dj2 repo covers all exclusions.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a bug.
**RM62 callee writeback trap [V]:** After resolution post-pass, callee is qualified FQDN.
  EP detection must use bare OR '%.name' suffix -- _has_callers() now handles this.
**feature_work_plan axis grouping [V]:** Axes derived from unresolved callees only.
**claim_verifier prose escape [V]:** RM21-B CLOSED -- Fix A sufficient, not observed.
**capn cache empty on fresh machine [V]:** .capn/ is gitignored; each machine starts cold.
**trace_data_flow collision [V]:** "call path from X to db" routes to trace_data_flow not
  trace_call_chain (regex grabs X+db as symbol pair before scoring); benign, answer correct.
**goal_intake BLAST_RADIUS fixture [V]:** Test requires patching _search_symbols_raw + fake
  numpy model to inject HOT relevant_symbols without embedding. See test_goal_intake.py.
**function_reference edges missing [V]:** parse_ast.py only captures ast.Call nodes.
  Dict value references, register_action(name,func), callback kwargs (target=func) are
  invisible to graph. Causes false inferred EPs in builtins.py-style registries.
  Fix in next session: _extract_function_references() in parse_ast.py.
**EP inferred count still inflated [?]:** After FQDN fix, 185 inferred EPs remain in world/.
  Most are likely real internal methods with dynamic dispatch. Expect count to drop after
  function_reference edges are added and dj2 is re-ingested.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
