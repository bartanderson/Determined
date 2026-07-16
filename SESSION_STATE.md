Written at commit: 8c62c79

# SESSION STATE - session 187
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 187, 2026-07-16)

**RM21 Technique 3: trace_call_chain + heuristic bug fix [V]** (8c62c79)

Three multi-hop probes run against Commonplace corpus to gate the work:
- Probe 1 (search path trace): FAIL -- DECOMPOSE emitted template prose ("files in Key files",
  "files in Entry points") instead of real lookups. Model can't plan a 4-hop traversal in one pass.
- Probe 2 (entry save trace): FAIL -- "what does each one do" matched "what does X do" heuristic,
  extracted "each" as symbol name, wasted all tool calls on symbol_intent('each').
- Probe 3 (blast-radius + implementation status): PASS -- DECOMPOSE correct, impact bypass fired,
  answer honest. General iterative DECOMPOSE loop has no evidence of being needed.

Fixes shipped:
1. **Heuristic bug**: negative lookahead `(?!(?:each|every|one|it|this|that|they|we|you|all|any|its)\b)`
   added to "what does X do" regex in agent_resolver.py.
2. **walk_call_chain(start, oracle, max_depth=5)** in agent_tools.py: deterministic BFS from a
   start symbol, annotates stub/impl per node, cycle-safe, returns list[dict] with callees.
3. **trace_call_chain detect rule** in pattern_executor.py: fires before trace_data_flow on
   traversal queries ("trace path from HTTP route through to database", etc.).
4. **run_traversal()** in PatternExecutor: finds HTTP route handlers via http_route column
   (falls back to name heuristics -- *_get, *_post, *handler, *route, *capture -- for older
   corpora where column wasn't populated at ingest time). Walks chain deterministically.
   One LLM synthesis call over the structured chain.
5. **Hooked in local_agent._answer()** as a new branch alongside existing pattern bypasses.
6. **14 new regression tests** in tests/regression/test_technique3.py. 999 passed, 1 skipped [V].

Known limitation: Commonplace corpus was ingested before http_route column was extracted --
http_route IS NULL for all functions. Fallback finds 2 handlers by name heuristic (capture,
capture_post). Chain is shallow (1 node) because graph_edges from capture only captured
library calls (Blueprint, flask.request.*), not project-level calls. Re-ingest would fix both.

**TRACKER.md updated [V]**: Technique 3 block added to RM21 entry; general iterative DECOMPOSE
gated on non-traversal multi-hop failure (not yet observed).

**HISTORY.md updated [V]**: Technique 3 decision and limitation recorded.

## NEXT SESSION -- start here

Priority order:
1. **RM21-B** -- prose confabulation scan, gated on observing it in live probe. Not yet seen.
2. **RM21 remaining techniques** -- Technique 2 (constrained decoding), 4 (MCTS), 5 (speculative
   verification), 6 (large-model fallback). Build only after observing a failure Technique 1+3
   can't fix. No current evidence any of these are needed.
3. **RM64 follow-ons** -- gated on more real-world exercise of feature_work_plan.
4. **RM10** -- DeRe-CoT recomposition pass in goal_intake, long-horizon.

If next session wants to test trace_call_chain properly: re-ingest Commonplace corpus first
so http_route is populated. Then run the two traversal queries from this session again.
Re-ingest command: use EngineRunner (Python corpus), NOT ingest_lang_corpus.py.

## Corpus status [?]

(Unchanged from session 186 -- no re-ingest this session)

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs; 1 UNGROUNDABLE (CombatFSM), 1 MISSING_BRIDGE (session->Encounter), 8 BLOCKED |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested, EP counts correct |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |
| Commonplace (Python) | ~64 | ? | 0 | OLD ingest -- no http_route col; re-ingest needed |

## Known issues (carried forward)

**trace_call_chain start node [V]:** Uses http_route col; falls back to name heuristics for old
  corpora. Commonplace DB needs re-ingest to populate http_route. Start node selection is
  approximate when http_route is absent -- picks handler whose name scores highest on question
  keywords; both handlers score 0 on "search", picks alphabetically first ("capture").
**trace_call_chain shallow chain [V]:** graph_edges from old Commonplace capture() only has
  library calls (Blueprint, flask.request.*), not project calls. Re-ingest fixes.
**concept extraction scope [V]:** _extract_docstring_concepts: single-word capitalised English
  words excluded by design (match prose verbs, not class-like concept names).
**feature_shape vs dev_priorities% inconsistency [V]:** Different counting methods, not a bug.
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
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.
**RM62 callee writeback trap [V]:** After resolution post-pass, callee is qualified FQDN.
  Tests asserting bare JS callee names on resolved edges will fail.
**feature_work_plan axis grouping [V]:** Axes derived from unresolved callees only. Stubs
  with no unresolved callees land in the feature's own axis, not a destination axis.
**claim_verifier prose escape [V]:** Verifier only catches confabulation expressed as "X calls Y".
  Prose-style confabulation escapes. Filed as RM21-B, gated on observing it in live probe.
  Not yet observed.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
