Written at commit: b4c0b6f

# SESSION STATE - session 196
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 196, 2026-07-17)

**Determined corpus re-ingested [V]** (no commit -- DB only)
  functions: 1,904 -> 2,160 (+256 from new sessions' code)
  graph_edges: 16,588 -> 18,693 (+2,105)
  function_reference edges: 54
  is_tool=1: 0 (correct -- Determined doesn't use @tool() decorator)
  BOM parse errors on ~25 test files are pre-existing/benign.

**Stub audit: used the tool on itself [V]**
  Ran readiness_check + explore_stub + completion_contract on all 3 "real" stubs.
  Found 2 bugs in the tool's own stub detection before touching any implementation.

**Fix 1: Protocol false-positive stubs [V]** (6a44058)
  SymbolOriginResolver.resolve (a Protocol abstract method with ... body) was
  flagged is_stub=1. Fix: _is_protocol_class() helper detects Protocol base;
  _iter_top_level_functions now yields (node, in_protocol) tuple;
  _is_stub(node, in_protocol=False) returns False for Protocol methods.
  Files: determined/ingestion/parse_ast.py
  5 new tests added to test_stub_detection.py.

**Fix 2: readiness_check name collision [V]** (6a44058)
  suggest_tags exists in 3 example subdirs (seed/, commonplace/, enhanced/).
  LIMIT 1 with no ordering returned the seed version (is_stub=0) instead of
  the actual stub. Fix: ORDER BY is_stub DESC LIMIT 1.
  File: determined/agent/agent_tools.py

**Delete structural_score dead code [V]** (b4c0b6f)
  evaluation_snapshot.py:27 -- stub returning 0, no callers anywhere.
  build_evaluation_snapshot already computes node degree/high-fanout directly.
  Confirmed dead via grep + explore_stub "no callers resolved".
  File: determined/graph/evaluation_snapshot.py

**Test results [V]**
  1068 passed, 1 skipped (after all three commits).

**Capn charted [V]**
  a99b8bb7: Protocol stub false positive pattern + readiness_check name collision fix.

## Stub status after this session [V]

All 3 previously flagged "real stubs" resolved:
  - structural_score: DELETED (dead code)
  - resolve: FALSE POSITIVE fixed (Protocol method, not an implementation gap)
  - suggest_tags: now correctly detected as READY; callees _call_llm, _parse_tags, _keyword_tags

Remaining is_stub=1 in Determined DB: test fixture mocks (find_symbols, find_files,
  discover_seed_symbols, etc.) -- intentional, not gaps. Nothing actionable.

## NEXT SESSION -- start here

Options in priority order:

1. **Implement suggest_tags** (LOW-MEDIUM priority)
   File: examples/commonplace/services/tagger.py
   Callees already exist: _call_llm, _parse_tags, _keyword_tags
   Run: python scratchpad/probe_contracts.py (or completion_contract('suggest_tags'))
   Blocked on: decide if LLM integration is wanted now vs. later.

2. **Re-ingest Commonplace corpus**
   Hasn't been re-ingested since is_tool + function_reference were added.
   Same EngineRunner pattern as Determined re-ingest. Script in scratchpad/reingest_determined.py
   -- copy and adjust CORPUS_ROOT + DB_PATH.

3. **Continue dj2 stub work**
   170 inferred EPs remain in world/. 8 BLOCKED stubs from session 194 still open.
   Next target: AdjudicationEngine._execute_purchase / _execute_sell.

4. **Alias-map filter for function_reference (low priority)**
   ~10 residual false edges (state.party_position, event.actor_id) from depth-1 local vars.
   Fix: pass alias_map into _extract_function_references.
   File: determined/ingestion/parse_ast.py. No correctness impact.

## Meta: what improved this session [V]

"Probe with the tool first" loop worked:
  - ran readiness_check/explore_stub BEFORE writing code
  - found 2 bugs in the tool itself, fixed them first
  - entry point for probing: determined/ask.py or scratchpad/probe_stubs.py

Capn charting gap identified: under-charting non-obvious findings. agent_tools call
pattern (assessor + args_dict) now charted. Chart aggressively after any re-derivation.

## Corpus status [V] (Determined re-ingested this session; others from session 195)

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 2,160 | 18,693 | 0 real | re-ingested [V]; Protocol fix applied |
| dj2 (Python+JS) | ~1,400 | ~10,000+ | 13 | re-ingested session 195; world/ 170 inferred EPs |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested session 195 |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |
| Commonplace (Python) | 31 | 168 | 0 | needs re-ingest for is_tool/function_reference |

## Known issues (carried forward)

**walk_call_chain FQDN trap [V]:** FIXED session 188.
**concept extraction scope [V]:** single-word capitalised English words excluded by design.
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
**Go resolution 15% [V]:** Correct -- unresolved are external libs.
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct.
**RM62 callee writeback trap [V]:** After resolution post-pass, callee is qualified FQDN.
  EP detection must use bare OR '%.name' suffix.
**trace_data_flow collision [V]:** "call path from X to db" routes to trace_data_flow not
  trace_call_chain; benign, answer correct.
**function_reference residual noise [V]:** ~10 false edges from depth-1 local vars (state.x,
  event.y). No correctness impact. Fix: pass alias_map to _extract_function_references.
**EP inferred count floor [V]:** 170 inferred EPs remain in dj2 world/. Not a bug.
**agent_tools call pattern trap [V]:** Tools take (assessor, args_dict) not (db_path=...).
  Entry point: determined/ask.py ask(db_path, question) wraps oracle+assessor setup.
**Protocol stub false positive [V]:** FIXED session 196. Protocol ... methods now is_stub=0.
**readiness_check name collision [V]:** FIXED session 196. ORDER BY is_stub DESC.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
