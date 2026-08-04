# Determined Delta Log

Running log of gaps found by comparing local AI (Qwen3) narration against Claude's
assessment when using Determined on a real corpus. Each entry drives a fix or a
conscious "good enough" decision.

**Process:**
1. Run tool on corpus (dj2 or other)
2. Read local AI narration
3. Note what Claude would say differently or additionally
4. Log below; fix the tool; mark outcome

**Outcome codes:** FIXED | GOOD_ENOUGH | DEFERRED | NEEDS_BART

---

## 2026-08-04 — Evaluation run against dj2

### Tool: detect_topology + frontier_coverage
**Local AI output:** Counts and categories. "Signal: LOW stub pressure — most implemented code is reachable." Action queues listed.

**Delta:** The tool reports numbers but draws no conclusion about *what kind of problem this is*. 941 orphaned-impls and 468 no-caller functions is not a stub problem — it's a wiring problem. The game code exists; it's not connected to the game loop. A developer reading this needs to know: stop implementing stubs, start wiring existing code in. The tool doesn't say that.

**Fix needed:** detect_topology and frontier_coverage should emit a synthesis line when orphaned-impl count dominates — something like: "Primary gap is connectivity (N functions unconnected), not implementation (M stubs). Focus: wire existing code into entry points before adding new stubs."

**Outcome:** FIXED

---

### Tool: frontier_priority
**Local AI output:** Single result — `get_player_by_session` (score 3, 3 callers, direct-call).

**Delta:** The tool doesn't flag that this stub lives in `test_economy.py` — a test file, not game code. The #1 "build this next" result is a test fixture, not a game feature. A developer would dismiss this immediately; the tool presents it as the top priority with no context.

**Fix needed:** frontier_priority should tag which file each stub lives in (already does filename, but doesn't flag test files) and — more importantly — should note when ALL direct-call stubs are in test files, meaning game logic has zero stub-blocked paths.

**Outcome:** FIXED

---

### Tool: list_stubs
**Local AI output:** FSM stubs (EncounterFSM, BarterFSM actions/guards) ranked at bottom with 0 callers.

**Delta:** FSMs dispatch by string name, not direct function calls, so caller count = 0 is a false signal. `EncounterFSM::action::resolve_parley` is an unimplemented game mechanic — the encounter system can't resolve a parley — but ranks below `get_player_by_session` (a test stub). The FSM dispatch pattern is invisible to static analysis.

**Fix needed:** FSM stubs (identified by `::action::` or `::guard::` in name, or `file_path` ending in `.json`) should get a special tag noting their caller count is zero due to dispatch, not because they're unwired. Could promote them in priority since they represent actual game features.

**Outcome:** FIXED

---

### Tool: list_features (new insight — no delta, this is good)
**Output:** Directory-level table with symbol counts, stub counts, entry points, cross edges.

**Observation:** `dungeon_neo/` — 141 symbols, 0 stubs, 6 entry points. Fully implemented but barely connected. `config/` — 45 symbols, 12 stubs, 0 entry points. Most stubs, no connectivity. `engine/` — 100% complete.

**Delta:** The table is actually useful and readable. What's missing is a conclusion: "dungeon_neo is complete but isolated (6 entry points from 141 symbols). It's built but not integrated." The numbers are there; the interpretation isn't.

**Fix needed:** list_features should flag directories where completeness is high but entry points are very low relative to symbol count — that pattern means "implemented but not wired in."

**Outcome:** FIXED

---

### Summary — what kind of problem dj2 actually has (Claude synthesis)
The tool correctly reports the numbers. What it doesn't say:

dj2 is **not stub-blocked**. The game code is 98% implemented. The actual gap is integration: `dungeon_neo/` (141 symbols, 0 stubs) has 6 external entry points — it's a complete dungeon system sitting in isolation. `config/` (12 stubs) is the only subsystem with meaningful incompleteness. The FSM mechanics (encounter/barter) have unimplemented actions/guards that the static tool can't prioritize because FSMs dispatch by name.

**What a developer needs to know:** Wire dungeon_neo into the game loop. Implement config stubs. Then implement FSM actions for encounter and barter resolution. The tool has all the data to say this but doesn't.

---

## 2026-08-04 — Session 296 fixes (all 4 gaps closed)

All 4 gaps from the 2026-08-04 evaluation run were implemented in `determined/agent/agent_tools.py`:

- **Gap 1 (detect_topology):** Added Synthesis line when orphaned_impl >= 3x total_stubs and >= 50. Fires for dj2: "primary gap is CONNECTIVITY (941) not IMPLEMENTATION (25)."
- **Gap 1b (frontier_coverage):** Added matching Synthesis line when no_callers >= 3x stub_gated and >= 50.
- **Gap 2 (frontier_priority):** Added `[test]` tag per stub + note when all priority stubs are in test files. Fires for dj2 (get_player_by_session).
- **Gap 3 (list_stubs):** FSM stubs separated into own section with "0 callers due to string dispatch" explanation. Fires for dj2 (12 FSM stubs: EncounterFSM, BarterFSM, TradeFSM).
- **Gap 4 (list_features):** Built-but-not-integrated detection (completeness >= 85%, ep_ratio <= 8%). Fires for dj2: dungeon_neo (141 syms, 0 stubs, 6 EPs).

459 tests passed. Verified against C_Users_bartl_dev_dj2.db.
