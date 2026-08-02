Written at commit: 79948b2

# SESSION STATE — session 287 (end)

## Active branch: main [V]

## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**GAP-7 fixed** (commit 9cbd0ee) [V]
- `feature_shape("encounter")` returned "No symbols found" because the tool expected a
  file-path fragment, not a keyword. Two-stage resolution added inside `feature_shape`
  itself (not the query router — router fix would leave Workbench tool broken and split
  "what counts as a feature" across two places).
- Stage 1: existing directory prefix match. Stage 2: fires only when stage 1 returns zero
  rows; matches keyword against relative path with prefix stripped, so a corpus-root-level
  keyword can't match everything.
- Entry-point detection switched from `startswith(norm_path)` to membership in the matched
  file set — equivalent in directory mode, correct in both.
- dj2 verified: "encounter" resolves 5 files across world/, resolver/, config/fsms/, root.
  "world" still takes directory mode. 6 new tests.

**GAP-8 fixed** (commit 28d00d8) [V]
- Exposed by GAP-7 fix but pre-existing. One test caller (test_encounter_flow) outside the
  encounter feature suppressed the "no entry points → use all local symbols" fallback, so
  33 of 34 encounter symbols were hidden from count and completeness denominator.
- Fix: BFS seeded from all local symbols always. Entry points annotated as
  "entered through" markers, not BFS seeds. The fallback is gone — "use all local symbols"
  is now the universal rule, simplification not addition.
- Added "Uncalled within this feature" section: symbols in no edge at all were counted but
  appeared in no section; the total silently disagreed with the listing.
- 4 new tests. Known limitation: same-name symbols in different files collapse in
  local_symbols dict (e.g. __init__, to_dict collide). Affects directory mode equally.
- dj2 before: "Symbols: 1 total, Completeness: 25%". After: 28 symbols, completeness ~54%.

**Slow test suite fixed** (commit 79948b2) [V]
- `tools/run_tests.py` on `agent_tools.py` changes took >120s and had to be killed.
  Root cause: 6 unmarked tests calling the LLM; pyproject.toml addopts was already correct.
  - `test_agent_tools.py`: 3x infer_behavior_batch variants (~36s each)
  - `test_infer_behavior.py::TestInferBehaviorDispatch`: 3x dispatch tests (~18s each)
- Added `@pytest.mark.slow` to all six. `test_missing_symbol_arg_returns_error` stays
  unmarked (returns before LLM).
- HF_HUB_OFFLINE moved from ui_server.py to `embedding_model.py` module level — UI was
  protected, everything else silently made HF Hub network calls on every model load.
- `run_tests.py`: no `-m` by default (addopts governs); `--slow` flag uses
  `"slow or not slow"` (always-true, avoids empty-string shell drop); prints skip count.
- CLAUDE.md: documented the `-m` CLI override trap.
- Measured: 20-file selection for agent_tools.py changes, >120s killed → 17.4s, 422 passed,
  8 deselected.

---

## WHAT IS NOT YET DONE

- GAP-6 (ABC scaffold intent): `find_abc_gaps` can't distinguish intentional scaffolds from
  real voids. dj2 has a `phases_abstract_methods` entry in decisions.toml that covers the 8
  ABCs in phases.py. Could close GAP-6 by wiring find_abc_gaps to check for a matching
  'decision' artifact on the ABC's file/subject before flagging as "architecture void."
  Low complexity, high signal quality improvement.
- dj2 decisions.toml: untracked in dj2 git (dj2-repo concern, not a Determined task).
- RM73/RM21: not touched this session.

---

## WHAT TO DO NEXT SESSION

1. **GAP-6 close** — add decision-artifact check to `find_abc_gaps()` in `agent_tools.py`.
   When the tool finds an ABC with no concrete subclasses, query `knowledge_artifacts` for a
   'decision' row whose subject matches the ABC's file path. If one exists, annotate as
   "intentional scaffold" instead of "architecture void." First command:
   `grep -n "find_abc_gaps" determined/agent/agent_tools.py` to find the function.

2. **RM73/RM21** — pick based on what next dj2 probe surfaces.

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
  with the same name in different files within a feature collapse. dj2 encounter: 28 counted
  vs 34 rows (__init__, to_dict, from_dict collide). Pre-existing, affects directory mode
  equally. Known limitation, not a priority fix. [V]
- Second query in local_agent.py ~line 813 already had 'decision' in its kind list.
  Only _enrich_with_stub_status (line ~488) was missing it. Both now correct. [?]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it.
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate.
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` — llama-server must be up first.
