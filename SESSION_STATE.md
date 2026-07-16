Written at commit: 74da033

# SESSION STATE - session 192
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 192, 2026-07-16)

**RM10 done [V]** (74da033)
goal_intake intent classifier (2A) + trace routing (2B).

2A: `_classify_goal_type(goal)` -- keyword heuristic returns investigate|trace|explain|implement.
Priority order: trace first (explicit "trace" keyword or >=2 trace terms), then explain
("what is/does", "explain", "describe"), then investigate ("find", "where", "detect",
"boundary", "violat", etc.), then implement (default). Explain wins over investigate so
"what is the AI boundary" routes to explain, not investigate.

Goal output now includes `Intent: <type>` line. Nav plan branches:
- investigate: READ steps + BLAST_RADIUS on hot/warm symbols; no MODIFY/EXTEND
- explain: READ steps only; no MODIFY/EXTEND
- trace: READ steps + "Walk the call path" hint; no MODIFY/EXTEND
- implement: original behavior (EXTEND stubs, MODIFY safe symbols)

2B: For trace goals, `_extract_trace_endpoints(goal)` regex-extracts source+destination
concepts. `_find_symbol_for_concept(oracle, concept)` SQL-matches concept words to
function names. `walk_call_chain()` (existing, BFS) traverses the path; chain trimmed
at dst_sym if found. Path shown inline as "Call path:" block before nav plan.

19 new regression tests in tests/regression/test_goal_intake.py. 1030 pass, 1 skipped.

## NEXT SESSION -- start here

**RM10 live validation (RECOMMENDED):**
Run goal_intake against dj2 with 3 probe goals to confirm real-world behavior:
1. "find where AI boundary is violated" -> Intent: investigate + no MODIFY
2. "trace how player input reaches the database" -> Call path: section populated
3. "add consequence tracking" -> Intent: implement + EXTEND/MODIFY
Use UI Ask bar with dj2 corpus loaded, or python script against dj2 DB.

**RM64 remaining candidates (OPTIONAL, quick):**
- Close-the-loop verification: after re-ingest, check implemented fn resolves stub.
- Doc-drift detection: design_note artifacts vs call graph -- new EPs with no design note.

## Corpus status [V] (unchanged from session 191)

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
**feature_work_plan axis grouping [V]:** Axes derived from unresolved callees only.
**claim_verifier prose escape [V]:** RM21-B, gated on observing in live probe. Not observed.
**capn cache empty on fresh machine [V]:** .capn/ is gitignored; each machine starts cold.
**trace_data_flow collision [V]:** "call path from X to db" routes to trace_data_flow not
  trace_call_chain (regex grabs X+db as symbol pair before scoring); benign, answer correct.
**goal_intake BLAST_RADIUS fixture [V]:** Test requires patching _search_symbols_raw + fake
  numpy model to inject HOT relevant_symbols without embedding. See test_goal_intake.py.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
