Written at commit: 6f6cd36

# SESSION STATE - session 195
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 195, 2026-07-16)

**RM66: is_tool column -- layer fix [V]** (91dc6e9)
is_tool INTEGER DEFAULT 0 added to functions table schema + ALTER TABLE migration.
parse_ast.py detects @tool(...) via isinstance(dec, ast.Call) + bare=='tool' at ingest.
FunctionRepresentation.is_tool: bool = False added to shared/types.py.
_ep_tier() signature: now takes is_tool int|bool instead of decorators_json string.
Both list_entry_points and detect_doc_drift SELECT is_tool -- no Python string matching
in tool layer. Language-specific detection is behind the language wall.

**RM65: function_reference edge detection [V]** (9993e06, 6f6cd36)
_extract_function_references(tree) in parse_ast.py, wired after dynamic_edges.
Three patterns, all pure AST:
  1. Dict values: ast.Attribute depth==1, root not self/cls
     (catches {'price_too_low': builtins.price_lt}; rejects self.x.y, event.data.x)
  2. 2-arg register calls: fn_attr in _REGISTER_ATTRS, args[1] is fn ref
  3. Callback kwargs: kw.arg in _CALLBACK_KWARGS, value is fn ref (depth==1, no self/cls)
Helper fns: _fn_ref_name(), _attr_root_id(), _attr_depth().
False-positive guard went through two refinement passes -- final filter: depth==1 +
no self/cls root via shared _is_fn_ref() helper.

**Results on dj2 after re-ingest [V]**
  function_reference edges: 140
  builtins.py functions with callers: 17/18 (was 0/18)
  Inferred EPs world/: 185 -> 170
  20 new regression tests. 1063 total pass.

**Known residual noise in function_reference edges [V]**
  ~10 edges like state.party_position, event.actor_id where root (state/event) is a
  local variable that happens to be depth-1. These don't affect EP detection (names
  not in functions table) but add graph_edges noise. Fixing precisely requires threading
  alias_map into _extract_function_references to distinguish imports from locals.
  Low priority -- no correctness impact.

## NEXT SESSION -- start here

**No immediate must-do.** RM65 + RM66 done. Options:

1. **Alias-map filter for function_reference (low priority)**
   Pass alias_map into _extract_function_references so dict/callback patterns only
   emit edges for known import names. Eliminates ~10 residual false edges like
   state.party_position. File: parse_ast.py. Low blast radius, purely additive.

2. **Re-ingest other Python corpora**
   Determined corpus (C_Users_bartl_dev_Determined.db) and Commonplace haven't been
   re-ingested with is_tool or function_reference. Run EngineRunner against each to
   pick up the new columns and edges. Determined especially worth doing -- 83% agent
   completion, structural_score blocking 4 stubs.

3. **Continue dj2 stub work**
   170 inferred EPs remain in world/. 8 BLOCKED stubs from session 194 still open.
   feature_work_plan -> explore_stub -> verify_implementation pipeline is ready.
   Next natural target: AdjudicationEngine._execute_purchase / _execute_sell
   (both show as inferred EPs, likely called via guard_registry dispatch).

4. **RM-Perf static purity sub-tier**
   Static purity classification (no I/O, no shared-state writes) is answerable from
   existing graph today. Could ship as standalone tool ~1 session.

## Corpus status [?] (dj2 re-ingested this session; others unchanged from session 194)

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | needs re-ingest for is_tool/function_reference |
| dj2 (Python+JS) | ~1,400 | ~10,000+ | 13 | re-ingested [V]; world/ 15 explicit + 170 inferred EPs |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested, EP counts correct |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |
| Commonplace (Python) | 31 | 168 | 0 | needs re-ingest for is_tool/function_reference |

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
**function_reference residual noise [V]:** ~10 false edges from depth-1 local vars (state.x,
  event.y). No correctness impact (names not in functions table). Fix: pass alias_map to
  _extract_function_references to filter to known imports only.
**EP inferred count floor [V]:** 170 inferred EPs remain in world/ after function_reference
  edges. Remaining are likely dynamic dispatch, protocol methods, or JS-only callers.
  Not a bug -- 185->170 is real improvement; further reduction requires runtime analysis.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
