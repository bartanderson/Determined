Written at commit: 7b2dc74

# SESSION STATE — session 282 (end)

## Active branch: main [V]

## Working tree: clean (after HISTORY.md update — commit that next) [V]

---

## WHAT HAPPENED THIS SESSION

**RM70 Step 1 — Official baseline** [V]
- Three runs total; first two were flawed (no LLM, then post-timeout noise).
- Clean run (llama-server warm, no UI competing): V1=20% (3/15), V2 mean=0.089.
- 7 `[no LLM]` stubs per run — server drops capacity mid-run consistently. Accepted as noise.
- s268 partial (V1=100%, V2=0.833) was biased sample — 5 easy stubs. Real baseline is worse.

**RM70 Step 2 — FSM transition context + builtin sibling retrieval** [V] (commit beede0c)
New in `determined/agent/sketch_stub.py`:
- `_fsm_transition_context(json_path, symbol)`: reads FSM JSON config, finds which
  transition(s) use this action/guard, returns event/from/to/cond as `fsm_context`.
- `_fsm_builtin_siblings(conn, stub_name)`: queries corpus for implemented functions
  in `file_path LIKE '%fsm%'` files; returns `(instance, event_data)` style examples.
- Both wired into `build_brief()` when `body_shape == "config_declared"` and file ends in `.json`.
- `_build_prompt()` updated: FSM siblings shown first as style examples; transition spec
  shown as `# FSM: EncounterFSM (action 'start_combat') / event 'fight': awaiting_choice -> resolving_fight`.
- 6 new tests. Post-step baseline: V1=40% (4/10), V2 mean=0.300. Guards improved most
  (`flee_possible`, `need_more_gold` both V1=PASS, V2=1.000).

**RM70 Step 3 — Same-class sibling priority** [V] (commit 7b2dc74)
New in `determined/agent/sketch_stub.py`:
- `_same_class_siblings(conn, stub_name, limit)`: for `ClassName::method` names, queries
  implemented siblings with same `ClassName::` prefix. Returns them with `similarity=1.0`.
- `_pattern_siblings()` refactored: runs `_same_class_siblings` first; corpus-wide difflib
  fills remaining slots; plain function names skip same-class path entirely.
- 4 new tests. All pass.

**HISTORY.md updated** [V] (not yet committed)
- Added FSM dispatch pattern discovery + baseline lesson.

**Test count at session end**: targeted tests pass (exit 0). [V]

---

## WHAT IS NOT YET DONE

- HISTORY.md update not committed (done in-session, needs `git add docs/HISTORY.md && git commit`).
- RM70 Steps 4-7: return-shape inference, type def pull, V3+V4 scoring, multi-sample loop —
  all already implemented from s263-s265. The stairs are largely climbed; main gap was FSM stubs.
- No post-Step-3 baseline run — LLM variance makes each run noisy; deferred.
- Build Queue check (carried from s280): verify 24 encounter items in dj2 UI. Not done.
- RM72 Phase A socket bridge: not started this session.
- dj2 decisions.toml: still untracked in dj2 git.

---

## WHAT TO DO NEXT SESSION

1. **Commit HISTORY.md**:
   `git add docs/HISTORY.md && git commit -m "chore: HISTORY.md session 282 -- RM70 FSM retrieval lessons"`

2. **Post-Step-3 baseline** (optional — LLM variance is high):
   Ensure llama-server running first, then: `.venv\Scripts\python.exe tools\rm70_baseline.py`

3. **Build Queue check** — open UI on dj2, verify encounter items still present.

4. **RM72 Phase A** — `_SocketBridge` in graph_explorer. See TRACKER for full spec.

---

## KNOWN ISSUES / TRAPS

- RM70 baseline: ALWAYS start llama-server before running rm70_baseline.py. Check with
  `.venv\Scripts\python.exe -c "from determined.agent.llm_client import is_available; print(is_available())"`.
  First call after cold start may timeout (600s) and corrupt the run.
- 7 `[no LLM]` stubs per baseline run: server drops mid-run. Consistent pattern, accepted noise.
- FSM stubs (body_shape=config_declared): callers = 0 always — GenericFSM dispatches by registry.
  Step 2 fix covers this; `_fsm_transition_context` reads JSON from `file_path`. [V]
- Plan layer DB fallback: `_enrich_from_db` LIKE match may over-match common-word subsystems. [?]
- `chain_synthesis()` mixed column usage (callee vs source_id/target_id). Works on dj2. [?]
- Build Queue items from s280 (24 encounter items) may need de-dup. [?]
- Ask bar browser automation: Set `#q-input` value + dispatchEvent + click `#send-btn`. JS not refs. [V]
- dj2 DB schema: no `is_entry_point` column. [V]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it.
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate.
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` — llama-server must be up first.
