Written at commit: 624d8b2

# SESSION STATE — session 295 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**RM-Perf profile tier: correctly deferred** [V]
Profile-grounded tier requires runnable corpus code. dj2 has incomplete stubs.
Profiling incomplete code gives noise. The TRACKER said "Gated on analysis/code-gen
arc complete" — we had already gated it correctly. Deferred as late-stage tool;
trigger is "something feels slow in real use." TRACKER.md updated.

**Standing job clarified (critical)** [V]
Bart surfaced a core process failure: over many sessions, Claude was told to run
Determined on dj2, log the delta between what the tool says and what Claude adds,
and fix the tool to close that gap. This was never done systematically. Claude was
acting as the synthesis layer without logging or fixing.

**Delta log methodology established** [V]
- `docs/DELTA_LOG.md` created — persistent gap log in the repo
- `memory/feedback_core_job.md` saved — standing job in memory for future sessions
- First evaluation run against dj2 completed; 4 gaps logged (see below)

---

## DELTA LOG — gaps found in first evaluation run [V]

All data from running detect_topology, frontier_priority, list_stubs, list_features,
frontier_coverage against `C_Users_bartl_dev_dj2.db`.

**Gap 1 — detect_topology / frontier_coverage: no synthesis on orphan-dominant corpus**
Tool reports 941 orphaned-impls correctly but draws no conclusion. A developer needs
to know: this is a wiring problem, not a stub problem. Fix: emit synthesis line when
orphaned-impl count dominates stub count by large margin.

**Gap 2 — frontier_priority: doesn't flag test-file stubs**
#1 priority stub (`get_player_by_session`) is in `test_economy.py`. Game logic has
zero stub-blocked paths. Tool doesn't distinguish game code from test code in priority
output. Fix: tag test-file stubs; note when ALL direct-call stubs are in test files.

**Gap 3 — list_stubs: FSM stubs falsely ranked 0-priority**
FSM stubs (EncounterFSM, BarterFSM actions/guards) show 0 callers because FSMs
dispatch by string name. `resolve_parley`, `resolve_flee` etc. are real unimplemented
game mechanics but rank below a test fixture. Fix: detect FSM stubs (`.json` source,
`::action::` / `::guard::` naming), tag them separately, note caller count is 0 due
to dispatch not disconnection.

**Gap 4 — list_features: no "implemented-but-isolated" signal**
`dungeon_neo/`: 141 symbols, 0 stubs, 6 entry points. Fully implemented but barely
wired. `config/`: 73% complete, 0 entry points. Tool shows numbers but draws no
conclusion. Fix: flag directories where completeness is high but entry points are low
relative to symbol count — "built but not integrated" pattern.

**What dj2 actually looks like (Claude synthesis for reference):**
dj2 is not stub-blocked. 98% implemented. Primary gap is integration — dungeon_neo
is a complete subsystem sitting in isolation. config/ is the only subsystem with
real stub incompleteness (12/45 stubs). FSM mechanics (encounter/barter) have
unimplemented actions the static tool can't prioritize due to dispatch pattern.

---

## WHAT TO DO NEXT SESSION

1. **Ask Bart:** do the 4 logged gaps match what he's seen? Any other walls?
2. **Implement the fixes** (if Bart confirms):
   - Gap 1: synthesis line in detect_topology / frontier_coverage
   - Gap 2: test-file tagging in frontier_priority
   - Gap 3: FSM stub detection and tagging in list_stubs / frontier_priority
   - Gap 4: "built-but-isolated" signal in list_features
3. Re-run evaluation after fixes; log new deltas or close gaps.
4. Repeat until gaps are small enough that Bart can use the tool without Claude.

---

## PROCESS RULE (new, standing) [V]

The job in every session: run Determined on dj2, compare tool output to what Claude
would say, log the delta in DELTA_LOG.md, fix the tool. Never synthesize the delta
yourself without logging and fixing. "Good enough is good enough" — check with Bart
on judgment calls. See memory/feedback_core_job.md.

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

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
