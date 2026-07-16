Written at commit: 4c5ef80

# SESSION STATE - session 190
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 190, 2026-07-16)

**capn reframed as trap registry + lookup cache [V]** (4c5ef80)
Two explicit use cases:
- TRAPS: non-obvious facts that cause wrong answers (wrong column names, silent defaults,
  schema quirks, routing collisions). Chart after getting burned.
- FREQUENT LOOKUPS: things that take more than a grep to re-derive (entry points,
  non-obvious call chains). Chart after locating.
Updated docstring and context output. Pruned fileless/fake-anchored entries.
5 clean entries remain, all properly file-anchored.

**capn usage discipline established [V]**
Was being ignored entirely. Reframed trigger: run `ask` before DB queries, symbol
resolution, ingestion routing, or any known-tricky area -- not before every grep.
Chart after hitting a trap or completing a high-cost lookup.

**capn seeded from SESSION_STATE.md known traps [V]**
Entries: normalize_symbol strips ::, resolved_only defaults False, trace_data_flow
routing collision, graph_edges column names (caller/callee not callee_fqdn),
where is the pattern detector.

## NEXT SESSION -- start here

Priority order (unchanged):
1. **RM64** -- feature_work_plan follow-ons. Gate: validate feature_work_plan on dj2
   first and observe real gaps. Run it against dj2, see what's missing, then decide
   which of the 3 candidate extensions to build.
2. **RM21-B** -- prose confabulation scan. Still gated -- not observed in live probe.
3. **RM21 remaining techniques** (2, 4, 5, 6) -- gated on T1+T3 failures.
4. **RM10** -- DeRe-CoT recomposition in goal_intake. Long-horizon, read TRACKER first.

## Corpus status [V] (unchanged from session 189)

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
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.
**RM62 callee writeback trap [V]:** After resolution post-pass, callee is qualified FQDN.
**feature_work_plan axis grouping [V]:** Axes derived from unresolved callees only.
**claim_verifier prose escape [V]:** RM21-B, gated on observing in live probe. Not observed.
**capn cache empty on fresh machine [V]:** .capn/ is gitignored; each machine starts cold.
**trace_data_flow collision [V]:** "call path from X to db" routes to trace_data_flow not
  trace_call_chain (regex grabs X+db as symbol pair before scoring); benign, answer correct.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
