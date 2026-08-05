Written at commit: f31e611

# SESSION STATE — session 299 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

**Session start:** analyze_corpus test fix (forward-reference trap). 391 tests pass.

**Session pivot:** Bart redirected to examine the guided journey (GETTING_STARTED.md)
and whether the tools stayed connected to the teaching vehicle (commonplace).

**Finding:** Three-way drift:
1. The journey taught visual UI only — Ask bar tools never introduced
2. analyze_corpus said "unclear" on commonplace — useless for teaching
3. static/ appeared as built-but-isolated (false positive), config/ appeared as
   wired-but-incomplete in list_features (false positive from bare-suffix collision)

**Fixes shipped:**

1. **analyze_corpus low-pressure shape** (e28e55e): "Low pressure - essentially complete"
   for small near-complete corpora. Seed: "Complete - no stubs, 24 orphaned."
   Complete: "Low pressure, 1 deferred stub, 43 orphaned."

2. **GETTING_STARTED.md Ask bar section** (e28e55e): Brief pointer after skeleton load.
   Full section after Phase 3 showing real analyze_corpus output, explaining each section
   (SHAPE/WHAT TO DO NOW/JUDGMENT CALLS/SUGGESTED NEXT TOOLS), and "what this looks like
   on a real project." Journey is now one continuous path.

3. **_is_asset_dir() filter** (f31e611): static/ no longer appears as built-but-isolated
   in analyze_corpus or list_features. Covers static, assets, public, dist, build, vendor,
   node_modules, www, media.

**Investigated but not fixed:**

4. **list_features FSM EP false positive** (DELTA_LOG): config/ shows 60 EPs in
   list_features because bare-suffix fallback maps FSM names (offer, confirm, cancel)
   to unrelated callers. analyze_corpus correctly shows 0. Needs fix in list_features
   bare-suffix logic to guard against "::" names.

5. **find_abc_gaps on dj2** (DELTA_LOG): 39 intentional scaffolds, 0 real gaps, all from
   engine/phases.py (8 phase ABCs). Two output gaps: decision text truncates mid-sentence,
   no summary line. Logged NEEDS_FIX.

459 tests pass [V].

---

## WHAT TO DO NEXT SESSION

1. **Fix list_features bare-suffix FSM collision.** In `list_features`, the callee_feat_map
   bare-suffix fallback should skip names containing "::" (FSM-qualified names). Adding
   `if "::" not in sym` guard before the rsplit. File:
   `determined/agent/agent_tools.py`, `list_features`, callee_feat_map build loop (~line 7524).

2. **Fix find_abc_gaps decision truncation + missing summary.** Two gaps:
   - Decision text cuts off mid-sentence — check where the text is being stored/retrieved
   - Add summary line at end: "N intentional scaffolds, N real gaps, N unclassified"
   Run find_abc_gaps on dj2 after fix to verify.

3. **RM67 convergence assessment.** Read TRACKER.md RM67 section. dj2 output now matches
   Claude synthesis end-to-end. Check if all 3 convergence probe criteria are met.

---

## PROCESS RULE (standing) [V]

Every session: run Determined on dj2, compare tool output to what Claude would say,
log delta in DELTA_LOG.md, fix the tool. Never synthesize without fixing.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed -- don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n`. [V s291]
- pytest `-m` on CLI REPLACES addopts -- never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns -- handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) -- don't treat as low-priority. [V s295]
- frontier_priority [test] tag uses _is_test_path() -- keep in sync with _is_test_feature(). [V s296]
- list_stubs caller count = ALL edges (resolved + unresolved); frontier_priority = resolved only. [V s297]
- dj2 "tail" stubs ALL have unresolved callers -- phantom edges, not real call paths. [V s298]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal.
  Forward references in dict literals cause NameError at import time. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages containing special characters. [V s299]
- list_features bare-suffix fallback inflates EP counts for FSM dirs (:: names match
  unrelated callers). config/ shows 60 false EPs. analyze_corpus is unaffected. [V s299]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
