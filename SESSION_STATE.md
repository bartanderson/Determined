Written at commit: 337605a

# SESSION STATE — session 288 (start)

## Active branch: main [V]

## Working tree: clean [V]

---

## WHAT HAPPENED (since session 287 handoff)

**GAP-6 fixed** (commits 6f3b094, 54c62fd) [V]
- `find_abc_gaps` now checks `knowledge_artifacts` for a 'decision' row whose
  subject matches the ABC's file path before flagging as "architecture void."
  Commit 54c62fd added content-match fallback when subject is a logical key
  (e.g., "phases_abstract_methods") rather than a file path.
- dj2 dj2 result: 8 phases.py ABCs correctly classified as intentional scaffolds.

**RM74 closed** (commit 39901bd) [V]
- All 8 analyst workflow gaps (GAP-1 through GAP-8) confirmed fixed.
- Both RM74 entries removed from TRACKER.md.

**RM67 probe table updated** (commit 15b3dc6) [V]
- dj2 probe as of 2026-08-02: 25 stubs, 10 real gaps, 8 phases.py ABCs classified
  correctly as intentional scaffolds. See TRACKER.md RM67 for full per-corpus table.

**RM-Perf static tier shipped** (commit 337605a) [V]
- `find_pure_functions`: reports implemented functions in files with zero recorded
  mutations. Multi-caller functions flagged [memo] as memoization candidates.
- `find_hot_callers`: ranks implemented functions by resolved incoming edge count.
  Load-bearing utilities with highest blast radius.
- Both wired to TOOL_DISPATCH, TOOL_REGISTRY, and `_PATTERNS` in agent_resolver.
- 9 new tests; 409 pass total.
- OptimizationOracle wrapper skipped — profile-grounded tier not yet being built.

---

## WHAT IS NOT YET DONE

- **RM-Perf profile-grounded tier**: requires cProfile instrumentation hook producing
  a `call_samples` table. Corpus-agnostic normalization maps profiler output to FQDNs.
  Estimated 2-3 sessions. Gate: static tier proves insufficient for a real perf question.

- **RM21 remaining techniques**: Technique 2 (constrained decoding via outlines),
  4 (MCTS over evaluate), 5 (speculative verification), 6 (large-model fallback).
  Gate: current tier fails on a real multi-hop query. Don't build ahead of failure.

- **RM73** (walker dispatch resolution, per-language edge ceilings): Go interface
  dispatch, Rust dyn Trait, Zig struct methods, Lua stdlib aliases, C function pointers,
  C++ virtual. Future, no gate yet.

- **RM68** (dj2 subrace removal): dj2-session-only task. Not a Determined task.

- **RM77** (export_context back-channel): future, requires external LLM observability.

---

## WHAT TO DO NEXT SESSION

Options (pick based on what next dj2 probe surfaces):

1. **Run RM67 probe on dj2** — use the new find_pure_functions and find_hot_callers
   on dj2 to see if they surface actionable signal. First command:
   `python -c "from determined.agent.agent_tools import find_hot_callers; from determined.agent.db_oracle import DBOracle; o=DBOracle('C_Users_bartl_dev_dj2.db'); print(find_hot_callers(o, top_n=10))"`
   (run from repo root with venv active; adjust DB path as needed)

2. **RM-Perf profile-grounded tier** — if a concrete perf question on dj2 can't be
   answered from the static tools alone, start the instrumentation hook.
   Entry point: design `call_samples` table schema and cProfile normalization pass.

3. **RM21 Technique 2** — if a real multi-hop query fails due to schema mismatch
   in LLM output (not confabulation), constrained decoding is the fix. Gate: observe failure.

---

## KNOWN ISSUES / TRAPS

- _wrap_body() must be used anywhere in sketch_stub.py that parses a body fragment. [?]
- line_number=0 trap: queries on functions table ordered by line_number must exclude
  line_number=0 to avoid config-declared entries crowding out Python functions. [?]
- _pull_type_defs has two paths: (1) classes table for Python types,
  (2) functions LIKE 'TypeName::%' for FSM/protocol entities. [?]
- export_context session is in-memory; resets on server restart. Intentional. [?]
- GAP-5 fix (fetch dead-end detection) only finds fetch() calls stored as raw callee
  strings in graph_edges. If JS walker improves and stores http_fetch edges instead,
  _explain_missing_path needs updating. [?]
- pytest `-m` on CLI REPLACES addopts entirely — `-m "not slow"` silently re-enables
  live_llm tests. run_tests.py passes no `-m` by default; use `--slow` to include LLM. [V]
- Same-name symbol collision in feature_shape: local_symbols keyed by name, so two symbols
  with the same name in different files within a feature collapse. Pre-existing, dir mode too. [V]
- Second query in local_agent.py ~line 813 already had 'decision' in its kind list.
  Only _enrich_with_stub_status (line ~488) was missing it. Both now correct. [?]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it.
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate.
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` — llama-server must be up first.
