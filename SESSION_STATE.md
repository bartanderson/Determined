Written at commit: d04ad84

# SESSION STATE — session 297 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**Delta loop ran 3 passes against dj2; 4 more gaps found and closed** [V]

Gaps 5-8 implemented:
- **Gap 5 (detect_topology):** ABC-interface moved to own action queue line with
  find_abc_gaps() pointer. "39 — run find_abc_gaps() to classify; some may be
  accepted scaffolds."
- **Gap 6 (list_stubs):** 0-caller/0-depth stubs now labeled "isolated" not "tail."
  "tail" incorrectly implied a chain exists above a disconnected stub.
- **Gap 7 (list_features):** "Wired-but-incomplete" detection added (ep >= 20 AND
  stubs >= 5). Fires for dj2: world (10 stubs, 164 EPs) and config (12 stubs, 60 EPs).
- **Gap 8 (list_stubs):** Footer note added explaining caller count includes unresolved
  edges; direct to frontier_priority for resolved-functional-caller ranking.

All 8 gaps across sessions 296-297 are now FIXED in DELTA_LOG.md. 459 tests pass.

---

## CURRENT TOOL OUTPUT FOR dj2 (verified at d04ad84)

After all fixes, running the 5 tools against dj2 produces:

**detect_topology:** Synthesis fires — "CONNECTIVITY (941) not IMPLEMENTATION (25)." ABC
action queue points to find_abc_gaps(). Shape table + synthesis is complete.

**frontier_coverage:** LOW stub pressure + connectivity synthesis. "468 no callers vs 0
stub-gated." Complete.

**frontier_priority:** 1 result (get_player_by_session, test stub, tagged [test]). Note:
"all priority stubs are in test files." Complete.

**list_stubs:** 10 regular stubs (5 with 1 caller/tail, 5 with 0 callers/isolated) + 12
FSM stubs in separate section. Footer note on unresolved-edge semantics. Complete.

**list_features:** Table + "Built-but-not-integrated: dungeon_neo" + "Wired-but-incomplete:
world, config." Complete.

---

## WHAT TO DO NEXT SESSION

1. **Run the delta loop again.** Another pass against dj2. Are there remaining gaps where
   the tool output still doesn't match what a developer needs to know?
2. **Check other corpora.** Run detect_topology + list_features against at least one other
   corpus (e.g., commonplace, rotjs) to verify the new synthesis signals don't misfire on
   clean corpora or produce false positives.
3. **ABC-interface classification.** The 39 ABC gaps in dj2 — run find_abc_gaps() and
   check how many are real vs. accepted phases.py scaffolds. Does find_abc_gaps() output
   need its own synthesis signal?
4. **Convergence assessment.** After 8 gap fixes, does dj2 now reach RM67 convergence?
   Check the probe acceptance criteria in TRACKER.md.

---

## PROCESS RULE (standing) [V]

Every session: run Determined on dj2, compare tool output to what Claude would say,
log delta in DELTA_LOG.md, fix the tool. Never synthesize without fixing.
See memory/feedback_core_job.md.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n`. [V s291]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns — handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) — don't treat as low-priority. [V s295]
- RM-Perf profile tier deferred — trigger is "something feels slow in real use." [V s295]
- frontier_priority [test] tag uses _is_test_path() — keep in sync with _is_test_feature(). [V s296]
- list_stubs caller count = ALL edges (resolved + unresolved); frontier_priority = resolved only. [V s297]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
