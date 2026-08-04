Written at commit: c99b33a

# SESSION STATE — session 296 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**All 4 DELTA_LOG gaps from session 295 implemented and closed** [V]

Bart's instruction: "I don't see them, you do. You are acting in my stead so that a
programmer can use the tool without relying on you." All 4 NEEDS_FIX gaps from the
2026-08-04 evaluation run were implemented without further confirmation.

---

## WHAT WAS FIXED (verify by running tools against dj2)

**Gap 1 — detect_topology: synthesis on orphan-dominant corpus** [V]
Added Synthesis line when orphaned_impl >= 3x total_stubs AND >= 50.
Fires for dj2: "primary gap is CONNECTIVITY (941) not IMPLEMENTATION (25). Wire existing
code into entry points before adding new stubs."

**Gap 1b — frontier_coverage: matching connectivity note** [V]
Added Synthesis line when no_callers >= 3x stub_gated AND >= 50.
Fires for dj2: "468 functions have no callers at all vs 0 stub-gated. Primary gap is
CONNECTIVITY."

**Gap 2 — frontier_priority: test-file tagging** [V]
Added [test] tag per stub when file is a test file. Added note when ALL priority stubs
are in test files.
Fires for dj2: get_player_by_session tagged [test], note "game/application logic has no
stub-blocked paths."

**Gap 3 — list_stubs: FSM stub section** [V]
FSM stubs (name contains ::action:: or ::guard::, or .json source) separated into own
section with explanation: "caller count is 0 due to string dispatch, not disconnection."
Fires for dj2: 12 FSM stubs (EncounterFSM, BarterFSM, TradeFSM) shown separately.
Added helper _is_fsm_stub(name, fp) inline.

**Gap 4 — list_features: built-but-not-integrated signal** [V]
Added detection: completeness >= 85% AND ep_ratio <= 8% AND sym_count >= 20.
Fires for dj2: dungeon_neo (141 symbols, 0% stubs, 6 entry points) flagged.

**Also added** [V]
`_is_test_path(fp)` helper near `_is_test_feature` — used by frontier_priority.

459 tests passed. DELTA_LOG.md updated: all 4 gaps marked FIXED with session note.

---

## WHAT TO DO NEXT SESSION

1. **Run the delta loop again.** Run all 5 tools against dj2 and check whether the tool
   output now matches what a developer needs to know. Look for NEW gaps — things the
   tool still doesn't say that Claude would add.
2. **Consider frontier_priority for FSM stubs.** Currently FSM stubs show 0 in
   frontier_priority (they're disconnected, not in any chain). Should they get a
   bonus score since they're real unimplemented mechanics? Or is the list_stubs FSM
   section sufficient?
3. **ABC-interface count (39) in detect_topology** — this is high and likely includes
   phases.py intentional scaffolds (classified as accepted in RM67). Does detect_topology
   need to exclude or tag accepted ABC gaps? Worth a look.
4. **RM67 convergence probe** — dj2 last probed 2026-08-02. After these fixes, consider
   whether the probe output changes enough to warrant an update to TRACKER.md.

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
- frontier_priority [test] tag uses _is_test_path() helper — keep in sync with _is_test_feature(). [V s296]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
