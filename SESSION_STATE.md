Written at commit: 6217782

# SESSION STATE — session 213
Written at commit: 6217782 (2026-07-18)

## Active branch: main [V]

## What happened this session

**Work queue items 1, 2, 4, 5, 6, 7 — all done [V]**
Item 3 (RM68 dj2 subrace removal) skipped per memory: never suggest dj2 work.

---

**Item 1 — Test stubs filter in _fetch_stubs() [V — 401e43f]**
- `determined/agent/corpus_projections.py:85`
- Added four NOT LIKE conditions (Unix + Windows, /test_% + /tests/) matching agent_tools.py:list_stubs.
- All four projection tools now exclude test-file stubs.
- Regression test: `test_file_shape_excludes_test_files` in test_corpus_projections.py. 36 pass [V].

**Item 2 — TS call tree FQN fix [V — d83fbd0]**
- `determined/agent/agent_tools.py` in `walk_call_chain`
- When bare-name lookup returns None, retries with `WHERE name LIKE '%.' || ?` suffix.
- Passes `row[0]` (stored FQN) to `_list_callees_raw` for correct callee lookup.
- Regression test: `test_walk_chain_ts_fqn_fallback`. 15 pass [V].

**Item 4 — classify_stub file_path_hint TS fix [V — 68349a8]**
- `determined/agent/classify_stub.py:242` + agent_tools.py:annotate_function
- `LOWER(REPLACE(...)) LIKE '%' || ?` suffix match replaces exact `file_path = ?`.
- Falls back to name-only if normalized hint misses. 42 tests pass [V].

**Item 5 — Ask routing fallback [V — ab7bafa]**
- `_prioritize_from_stub_shape()` added before `prioritize_work` in agent_tools.py.
- Calls stub_file_shape + stub_subsystem_shape when no workflow items or known issues exist.

**Item 6 — Design Oracle [V — 471ee71]**
- New `design_oracle` tool: CRITICAL / OPPORTUNITY / FOREWARNING, deterministic, no LLM.
- CRITICAL: highest-fanout stub with prereq-language docstring.
- OPPORTUNITY: unblocked stubs in same dir/file as `context` symbol.
- FOREWARNING: prereq stubs on callee chain ahead of `context`.
- Registered in TOOLS + tool_registry.py. 5 regression tests in test_design_oracle.py [V].

**Item 7 — Polish [V — 6217782]**
- graph_path FQN fallback: `_shortest_path_by_name()` in graph_utils.py, BFS over caller/callee when source_id BFS fails.
- .db path auto-load: handle_scan in ui_server.py detects .db file, calls init() directly.
- Non-db non-directory paths show hint: "to load an existing corpus, enter a .db file path".

## Tests [V]
- test_corpus_projections.py: 36 pass
- test_technique3.py: 15 pass
- test_classify_stub.py: 42 pass
- test_agent_tools.py: 57 pass
- test_design_oracle.py: 5 pass (new)
Full suite not re-run this session (+15 new tests added).

## Known issues [V = verified, ? = recalled]

**RM68 subrace dead code [?]:** still pending; dj2 game work, deferred by policy.
**world/ verdict misleading [?]:** dead-concept dominant due to 5 subrace stubs; clears after RM68.
**Shape index symbols [?]:** only stub names in index; prereq map concept names may not be clickable.
**design_oracle FOREWARNING depth [?]:** BFS over callee chain may miss stubs if graph stores FQNs but chain uses bare names. Not tested against live corpus.

## NEXT SESSION — start here

All 7 work queue items done. Check `docs/CLOSURE.md` for next unchecked Phase 2/3 item.
If CLOSURE.md is complete, next goal is UI redesign arc (docs/UI_VISION.md).
Consider: run `design_oracle` against dj2 corpus live to exercise the new tool.
