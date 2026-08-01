Written at commit: 74ab6b8

# SESSION STATE — session 283 (end)

## Active branch: main [V]

## Working tree: HISTORY.md updated, not yet committed [V]

---

## WHAT HAPPENED THIS SESSION

**Post-Step-3 baseline run** [V]
- First run showed regression: V1=21% (3/14), V2=0.125 vs Step 2's V1=40%, V2=0.300.
- FSM stubs that passed in Step 2 (flee_possible, need_more_gold) all scoring 0.000.

**Bug 1 fixed: line_number=0 in _fsm_builtin_siblings** [V] (commit f0d309e)
- `_fsm_builtin_siblings` queries `file_path LIKE '%fsm%' AND is_stub=0 ORDER BY line_number`.
- JSON config entries (FSM states/events) are stored with line_number=0 and is_stub=0.
- They filled the entire LIMIT before real Python functions in builtins.py appeared.
- Fix: add `line_number > 0` to the WHERE clause.
- After fix: re-run scored V1=60% (6/10), V2=0.600. [V]

**Evaluation methodology assessment** [V]
- Denominator varies each run (random LLM server drops). Step comparisons are not apples-to-apples.
- V2 mean is cleaner signal than V1 rate across runs with different denominators.
- Root insight: all of Stage 1 (retrieval) is deterministic and independently verifiable.
  LLM is only at Stage 2. Verify retrieval quality directly, not via noisy LLM output.
- RM70_DESIGN.md criterion "finds _get_combat_context as top match" is wrong:
  _get_combat_context is also a stub (no body). Highest difflib scorer on a well-named
  corpus is the right sibling. Criterion updated in HISTORY.md. [V]

**Bug 2 fixed: _infer_return_shape silently returning NONE** [V] (commit 74ab6b8)
- Caller bodies are indented fragments. ast.parse() rejects them with SyntaxError.
- _infer_return_shape caught the SyntaxError silently and returned NONE for all callers.
- _wrap_body() already existed for this exact problem, used in _verify_candidate and
  _ast_node_sequence but not applied in _infer_return_shape.
- Fix: `ast.parse(_wrap_body(body))` instead of `ast.parse(body)`.
- After fix: _get_encounter_context return-shape yields STRONG confidence with hints. [V]
- 154 tests pass. [V]

---

## WHAT IS NOT YET DONE

- HISTORY.md update not committed (done in-session, needs commit).
- RM70 acceptance criteria: all 7 design steps are implemented. Two retrieval bugs
  fixed this session. Remaining criteria not yet verified (Steps 5-7).
- Build Queue check (carried from s280): verify 24 encounter items in dj2 UI. Not done.
- RM72 Phase A socket bridge: not started.
- dj2 decisions.toml: still untracked in dj2 git.

---

## WHAT TO DO NEXT SESSION

1. **Commit HISTORY.md**:
   `git add docs/HISTORY.md && git commit -m "chore: HISTORY.md session 283 -- _wrap_body rule, criteria lesson"`

2. **Verify remaining RM70 acceptance criteria** (deterministic, no LLM):
   - Does _get_encounter_context brief contain type_defs with real corpus methods? (Step 5)
   - Does V3/V4 scoring run correctly on a passing candidate? (Step 6)
   - Does feedback loop emit specific constraint on V2 failure? (Step 7)
   Check via build_brief() and _verify_candidate() directly.

3. **Mark RM70 done in TRACKER.md** if criteria pass, then move to RM72 Phase A.

4. **Build Queue check** — open UI on dj2, verify encounter items still present.

---

## KNOWN ISSUES / TRAPS

- _wrap_body() must be used anywhere in sketch_stub.py that parses a body fragment.
  Currently consistent after today's fix. If new functions parse bodies, apply it. [V]
- line_number=0 trap: any query on functions table ordered by line_number must exclude
  line_number=0 to avoid config-declared entries crowding out Python functions. [V]
- RM70 baseline runner: always start llama-server first. 7 [no LLM] drops per run
  is normal; denominator varies; don't compare V1 rates across runs with different
  denominators. Use V2 mean or verify retrieval quality deterministically. [V]
- FSM stubs (body_shape=config_declared): callers=0 always. _fsm_transition_context
  reads JSON from file_path; _fsm_builtin_siblings reads builtins.py. Both working. [V]
- Build Queue items from s280 (24 encounter items) may need de-dup. [?]
- dj2 DB schema: no is_entry_point column. [V]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it.
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate.
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` — llama-server must be up first.
