Written at commit: 38ed639

# SESSION STATE - session 188
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 188, 2026-07-16)

**Re-ingest Commonplace + fix walk_call_chain BFS depth bug [V]** (38ed639)

Re-ingested `C:\Users\bartl\dev\commonplace-walk` using EngineRunner.
New DB: 31 functions, 168 edges, http_route populated for 3 routes (/, /capture, /search).

Bug found and fixed in `walk_call_chain` (agent_tools.py:547):
- BFS was queuing FQDN callee names (e.g. `services.extractor.extract`) for `WHERE name = ?`
  lookup against functions table, which stores bare names (`extract`). No match → depth stays 1.
- Fix: `bare = callee.rsplit(".", 1)[-1]` before queuing next hops.

Traversal probes re-run with fix:
- Probe 1 (search → DB): **4 nodes** -- search → search_entries → get_db → sqlite3.connect.
  Correctly identifies storage.queries.search_entries as the DB-touching callee.
- Probe 2 (capture → storage): **16 nodes** -- full traversal through validate_url, extract,
  extract_metadata/full_content, run_processors, enrich_entry, insert_entry, find_connections,
  suggest_tags, get_db. Complete end-to-end capture pipeline traced.

999 passed, 1 skipped [V]. Committed.

## NEXT SESSION -- start here

Priority order:
1. **RM21-B** -- prose confabulation scan, gated on observing it in live probe. Not yet seen.
2. **RM21 remaining techniques** -- Technique 2 (constrained decoding), 4 (MCTS), 5 (speculative
   verification), 6 (large-model fallback). Build only after observing a failure Technique 1+3
   can't fix. No current evidence any of these are needed.
3. **RM64 follow-ons** -- gated on more real-world exercise of feature_work_plan.
4. **RM10** -- DeRe-CoT recomposition pass in goal_intake, long-horizon.

trace_call_chain is now working correctly on a properly ingested Commonplace corpus.
No re-ingest needed next session unless corpus changes.

## Corpus status [V]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs; 1 UNGROUNDABLE (CombatFSM), 1 MISSING_BRIDGE (session->Encounter), 8 BLOCKED |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested, EP counts correct |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |
| Commonplace (Python) | 31 | 168 | 0 | re-ingested session 188; http_route populated [V] |

## Known issues (carried forward)

**walk_call_chain FQDN trap [V]:** FIXED session 188. BFS now strips FQDN to bare name before
  queuing. Callee display in node dict still shows FQDN (correct for informational use).
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
