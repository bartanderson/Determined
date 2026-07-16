Written at commit: 0514b63

# SESSION STATE - session 189
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 189, 2026-07-16)

**capn discovery cache (scripts/capn.py) [V]** (0514b63)
Adapted from cap'n hook (github.com/cyrusNuevoDia/capn-hook), pure Python, no deps.
Commands: ask / chart / prune / context / list.
SHA256 staleness detection per entry (auto-expires when referenced files change).
est_tokens stored at chart time (len(question+details)//4); accumulated in stats.json.
Inline savings line on cache hits: `[capn: ~N tokens | lifetime: ~XK across N hits]`.
Session hook updated: session_start_hook.py calls `capn context` and appends to context.
.capn/ added to .gitignore. Cache starts empty on each machine.

**Pattern detection upgrade [V]** (0514b63)
New: determined/agent/pattern_detector.py -- TOOL_REGISTRY with canonical example
questions per pattern. detect_pattern() tries regex first (fast, structurally certain),
then falls back to stop-word-filtered word-overlap scoring against examples.
Coverage: 84% -> 98% on 64 realistic questions; all 6 prior misses eliminated.
Key regex fixes: "show me X" in understand_symbol anchored to bare symbol ($);
new trace_call_chain branch for "what is/show me the path from web/http/route to db".
One known remaining error: "what is the call path from X to db" routes to
trace_data_flow (regex grabs X+db as symbol pair before scoring); benign, answer correct.
36 targeted tests pass [V].

**RM21 probe suite run on Commonplace [V]**
Q1 PASS (orient_to_codebase), Q2 PASS (blast_radius, fixed path to storage/queries.py),
Q3 PASS, Q4 PASS, Q5 PASS (no confabulation, Fix A working), Q6 CORRECT (no Entry class).
RM21-B stays gated -- no prose confabulation observed in Q5.

**Architecture note logged [V]**
detect_pattern() is human-input-only. If goal_intake ever generates sub-questions that
re-enter _answer(), use structured directives (QUERY: blast_radius(file.py)) not scoring.
See HISTORY.md.

**Test targeting rule updated [V]**
memory/feedback_test_targeting.md: targeted tests only for non-load-bearing changes.
Full suite only for persistence/ingestion/resolver changes. Grep affected test files first.

## NEXT SESSION -- start here

Priority order (unchanged from session 188):
1. **RM21-B** -- prose confabulation scan. Stays gated -- not observed in live probe.
2. **RM21 remaining techniques** (2, 4, 5, 6) -- gated on failures T1+T3 can't fix.
3. **RM64 follow-ons** -- gated on more real-world exercise of feature_work_plan.
4. **RM10** -- DeRe-CoT recomposition pass in goal_intake. Long-horizon, read TRACKER first.

## Corpus status [V]

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
