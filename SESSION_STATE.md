Written at commit: 1bccda2

# SESSION STATE — session 299 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**Session goal shift:** Bart said "the remaining gap is in me — you know how to use the tool, I don't. Show me through development." New direction: build a developer entry point that tells a developer what to run, in order, what the output means, and when to make a judgment call vs. when the tool has a clear answer.

**analyze_corpus() shipped (1bccda2)** [V]

New developer entry point tool. Run this first on any corpus. Produces:
- CORPUS ANALYSIS: counts (impl / stubs)
- SHAPE: connectivity-dominant / stub-blocked / complete
- WHAT TO DO NOW: ordered concrete steps (wired subsystems first, then isolated, then stubs with verified callers)
- JUDGMENT CALLS: FSM mechanics, isolated stubs, test stubs, ABC gaps — places where human decides
- SUGGESTED NEXT TOOLS: context-aware (points to list_stubs, feature_shape, find_abc_gaps based on what's present)

**dj2 output (verified)** [V]:
```
SHAPE: Connectivity-dominant — 66% orphaned vs 25 stubs.
WHAT TO DO NOW:
  1. Implement wired subsystems — world/ (10 stubs, 164 EPs)
  2. Wire isolated — dungeon_neo/ (141 syms), static/ (75 syms)
JUDGMENT CALLS: FSM 12, isolated 5, test 1, ABC 39
```
Matches what Claude would say. No synthesis needed.

**False positive caught and fixed** [V]: commonplace (60 functions) was labeled
"Connectivity-dominant" because HTTP routes aren't statically resolved. Fix: added
`orphaned_impl >= 50` floor to the connectivity-dominant threshold.

**All corpora checked** [V]:
- dj2: connectivity-dominant, correct
- commonplace: "unclear" (1 stub, small app) — correct after fix
- rotjs: "unclear" (6 method stubs, library) — correct

391 tests pass [V].

---

## CURRENT TOOL STATE (verified at 1bccda2)

**analyze_corpus:** Ships. Registered in TOOLS, REGISTRY, test expected set. [V]

**All gaps 1-10 remain closed** (from sessions 296-298). [?]

---

## WHAT TO DO NEXT SESSION

1. **Run analyze_corpus as the opening move.** Don't run detect_topology manually first —
   run `analyze_corpus()` and show Bart what a fresh developer would see. The tool is now
   the teacher. See: `determined/agent/agent_tools.py:analyze_corpus`.

2. **RM67 convergence assessment for dj2.** Read TRACKER.md RM67 criteria. dj2 now outputs
   everything needed without Claude synthesis — does that meet the convergence probe criteria?
   If yes, update the probe table. Command: read TRACKER.md, look for RM67 section.

3. **find_abc_gaps() on dj2.** analyze_corpus shows 39 ABC gaps. Run find_abc_gaps() and
   check: does the output explain which are accepted scaffolds vs real gaps? If not, that's
   the next delta log entry.

4. **config/ missing from wired_incomplete in analyze_corpus.** [?] config has 12 stubs and
   60 entry points but didn't appear in the WHAT TO DO NOW step 1. Needs investigation —
   may be a query path issue in analyze_corpus vs list_features (dir_key mapping).
   Start with: run list_features() and compare config/ numbers.

5. **static/ false positive in analyze_corpus.** static/ (75 symbols, 6 EPs) appears as
   "built-but-isolated" — but it's web assets (JS/CSS), not Python code to wire. May need
   an `_is_test_feature`-style filter for static directories.

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
- dj2 "tail" stubs ALL have unresolved callers — phantom edges, not real call paths. [V s298]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50 (small apps / HTTP routing). [V s299]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
