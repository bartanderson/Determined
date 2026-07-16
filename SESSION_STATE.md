Written at commit: d2a8d10

# SESSION STATE - session 191
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 191, 2026-07-16)

**RM63 signature fix [V]** (d2a8d10)
feature_work_plan was showing (?) for stubs with param_types_json='{}' (known-empty).
Fixed: distinguish SQL NULL (unknown -> ?) from {} (known-empty -> ()). Also added
arguments_json fallback to show bare param names when types absent. Added arguments_json
to fixture in test_feature_work_plan.py. 1 new test.

**RM64 explore_stub [V]** (d2a8d10)
New tool: explore_stub(symbol) -- design exploration for BLOCKED stubs. Surfaces callers
+ what they pass, docstring contract, ghost/bridge analysis, sibling stubs, design
questions. Feeds into completion_contract. 12 regression tests. Registry entry wired in
tool_registry.py and test_agent_tools.py. 1011 tests pass.

**RM10 probe [V]**
Ran goal_intake against 3 multi-hop goals on dj2. Key finding: embedding finds RIGHT
symbols, wrong action plan. Two failure modes confirmed:
1. Intent blindness -- "find where X" gets MODIFY plan, should be READ/blast_radius.
2. Multi-hop gap -- "trace A to B" gets endpoint list, not path (walk_call_chain exists
   but goal_intake never invokes it).
DeRe-CoT is the wrong fix. Revised plan: 2A goal-type classifier + 2B trace routing.
Findings saved in capn (0245de17) and memory (project_rm10_goal_intake.md). TRACKER
updated with probe results and revised plan.

## NEXT SESSION -- start here

**RM10 (ACTIVE):** Build 2A + 2B in goal_intake (agent_tools.py:3470).
- 2A: keyword/embedding heuristic to classify goal as investigate | implement | trace |
  explain. Adjust nav plan per type: investigate -> READ + blast_radius on found symbols;
  implement -> EXTEND/MODIFY (current behavior); trace -> hand off to 2B.
- 2B: for trace goals, extract two endpoint concepts from goal text, invoke
  walk_call_chain between them, surface the path in the nav plan.
- Test against probe goals: "find where AI boundary is violated" (investigate),
  "trace how player input reaches the database" (trace), "add consequence tracking" (implement).
- Regression tests required before commit.

Then: RM64 remaining (close-the-loop, doc-drift) if RM10 is clean and quick.

## Corpus status [V] (unchanged from session 190)

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
**goal_intake intent blindness [V]:** investigation goals get implementation plan. Fix is
  2A goal-type classifier. DeRe-CoT is NOT the right fix.
**goal_intake trace gap [V]:** trace goals get endpoint list not path. walk_call_chain
  exists but goal_intake never invokes it. Fix is 2B trace routing.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
