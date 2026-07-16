Written at commit: fb1f728

# SESSION STATE - session 193
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 193, 2026-07-16)

**RM10 done [V]** (74da033)
goal_intake intent classifier (2A) + trace routing (2B). Live-validated against dj2:
all 3 probes pass (investigate/trace/implement). 19 regression tests.

**RM64 fully done [V]** (1e4b71f)
verify_implementation(symbol): post-ingest close-the-loop check (is_stub=0, callers
resolve, no new unresolved callees, docstring not stale). PASS/WARN/FAIL verdict.
detect_doc_drift(feature_path): flags EP/design_note gaps and doc-stale symbols after
stubs are closed. Both in TOOLS + tool_registry. 13 regression tests. 1043 pass.

**RM21-B closed [V]** (fb1f728)
Gate probe: Q5 ("what is the path from the web route to the database for a new entry?")
run against Commonplace. trace_call_chain pattern fired correctly, found 0 HTTP handlers
(correct -- Commonplace has no web layer), returned honest "none found" answer.
No invented symbols, no prose-style confabulation. Fix A (session 191) was sufficient.
Prose-escape token scan not needed. RM21-B closed in TRACKER.

## NEXT SESSION -- start here

No urgent open items. Candidates:

**RM21 Techniques 2-6 [future, low urgency]:** Constrained decoding, MCTS, speculative
verification, large-model fallback. Build only when Technique 1 proves insufficient on
real queries. No evidence of that yet.

**New work:** consider what Determined is missing for the next dj2 development push.
Good time to run feature_work_plan on a specific dj2 feature and see what the full
pipeline (feature_work_plan -> explore_stub -> verify_implementation -> detect_doc_drift)
surfaces end-to-end.

## Corpus status [V] (unchanged)

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
**claim_verifier prose escape [V]:** RM21-B CLOSED -- Fix A sufficient, not observed.
**capn cache empty on fresh machine [V]:** .capn/ is gitignored; each machine starts cold.
**trace_data_flow collision [V]:** "call path from X to db" routes to trace_data_flow not
  trace_call_chain (regex grabs X+db as symbol pair before scoring); benign, answer correct.
**goal_intake BLAST_RADIUS fixture [V]:** Test requires patching _search_symbols_raw + fake
  numpy model to inject HOT relevant_symbols without embedding. See test_goal_intake.py.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
