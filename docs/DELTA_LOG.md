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

---

## 2026-08-04 — Second evaluation run against dj2 (session 297)

### Tool: detect_topology
**Local AI output:** ABC-interface: 39 listed in "Implement now" queue. No pointer to find_abc_gaps(). No note that some may be accepted scaffolds.

**Delta:** Developer reads "39 ABC interfaces to implement" but the actual number is lower — RM67 accepted 8 phases.py scaffolds. The action queue line gives no path to classify them. A developer needs: "run find_abc_gaps() to see per-gap classification before treating all 39 as work."

**Fix needed:** Action queue line for abc-interface should append "— run find_abc_gaps() to classify; some may be accepted scaffolds."

**Outcome:** FIXED — ABC-interface moved to own action queue line with find_abc_gaps() pointer.

---

### Tool: list_stubs
**Local AI output:** Stubs with 0 callers labeled "tail."

**Delta:** "tail" implies "implement me first to unblock the chain above" — but if callers=0 there is no chain above. These stubs are isolated, not chain-tails. A developer misreads 0-caller stubs as chain leaves (high priority) when they're actually disconnected (decide priority). The correct label is "isolated."

**Fix needed:** In list_stubs output, when callers=0 and depth=0, use "isolated" not "tail."

**Outcome:** FIXED — 0-caller/0-depth stubs now labeled "isolated."

---

### Tool: list_features
**Local AI output:** config (45 symbols, 12 stubs, 60 entry points) shown in table. No conclusion drawn.

**Delta:** config is the inverse pattern of dungeon_neo: heavily wired (60 entry points) but meaningfully incomplete (12/45 stubs = 27%). That's the "wired-but-incomplete" pattern — these stubs actually block real callers. The table shows the numbers but says nothing. A developer should know: "config stubs matter; they're connected to the live call graph."

**Fix needed:** list_features should flag directories where entry_points >= 20 AND stub_count >= 5 as "wired-but-incomplete" — the actionable counterpart to built-but-not-integrated.

**Outcome:** FIXED — "Wired-but-incomplete" section added. Fires for dj2: world (10 stubs, 164 EPs) and config (12 stubs, 60 EPs).

---

### Observation: no bridge from detect_topology ABC count to frontier_priority
detect_topology reports 39 ABC-interface gaps. frontier_priority shows 1 result (a test stub). No connection between them in the output. Developer has to know to run find_abc_gaps() separately. This is covered by the fix to detect_topology (Gap 5 above).

**Outcome:** COVERED_BY_GAP5

---

## 2026-08-04 — Third evaluation run against dj2 (session 297)

### Tool: list_stubs vs frontier_priority — caller count inconsistency
**Local AI output:** list_stubs shows `_get_encounter_context (1 callers, tail)`, `_get_combat_context (1 callers, tail)`, etc. frontier_priority doesn't list them.

**Delta:** list_stubs caller count uses a LEFT JOIN on ALL graph_edges — it includes unresolved callers (functions not in the functions table). frontier_priority requires caller to be a resolved implemented function (JOIN functions WHERE is_stub=0). A stub with 1 unresolved caller appears as "1 callers, tail" in list_stubs but zero in frontier_priority. Developer reads "this has a real caller, implement it" but the caller may be noise. The count semantics are different and there's no note explaining the discrepancy.

**Fix needed:** list_stubs footer note: "Caller count includes all graph edges; unresolved callers (external/missing functions) may inflate counts. Use frontier_priority for resolved-caller-only ranking."

**Outcome:** FIXED — note added to list_stubs output.

---

## 2026-08-04 — Fourth evaluation run against dj2 (session 298)

### Tool: detect_topology — FSM stubs misclassified as "Disconnected — Decide"
**Local AI output:** "Disconnected: 18 stubs with no graph connections" in Decide queue.

**Delta:** 12 of those 18 are FSM stubs (already identified in list_stubs as real unimplemented game mechanics). detect_topology puts them in the same "Decide" bucket as potentially-dead disconnected stubs. A developer reads "18 disconnected, decide if dead" when 12 are definitively real work. list_stubs already separates them; detect_topology should too.

**Fix needed:** In detect_topology, detect FSM stubs (::action::, ::guard:: in name, or .json path) among the disconnected set and report them separately. Subtract from "Disconnected" count and add "FSM-dispatch" row.

**Outcome:** FIXED — FSM-dispatch: 12 row added; Disconnected drops from 18 to 6. Action queue: "FSM mechanics: 12 stubs with string dispatch — real work, not dead code; see list_stubs."

---

### Tool: list_stubs — caller names not shown for low-caller stubs
**Local AI output:** "_get_encounter_context (1 callers, tail)" — who is that caller?

**Delta:** Footer says caller count may include unresolved edges. Developer can't verify if the 1 caller is real without a separate query. For stubs with 1-3 callers, showing the actual caller name(s) lets the developer immediately assess if it's real or noise. Extended fix: also annotate whether the caller resolves to a known function (real/stub/unresolved).

**Fix needed:** For stubs with <= 3 callers, fetch and append the caller name(s) inline, annotated as (unresolved), (stub), or bare name for implemented callers.

**Outcome:** FIXED — caller names shown with resolution status. Revealed: ALL 5 "tail" stubs in dj2 have unresolved callers (e.g., "ContextBuilder.build (unresolved)"). These are phantom edges — the callers don't exist in the corpus. Developer now correctly treats these as lower priority than frontier_priority would suggest.

---

## 2026-08-04 — Session 299: analyze_corpus developer entry point

### New tool: analyze_corpus()
**Purpose:** Developer entry point — run first on any unfamiliar corpus. Produces CORPUS ANALYSIS (counts), SHAPE (dominant problem pattern), WHAT TO DO NOW (ordered steps), JUDGMENT CALLS (human decisions required), and SUGGESTED NEXT TOOLS.

**dj2 output (verified):**
- SHAPE: Connectivity-dominant (66% orphaned vs 25 stubs) — correct
- WHAT TO DO NOW: (1) wired subsystems — world/ 10 stubs; (2) wire isolated — dungeon_neo/ + static/; correct priority order
- JUDGMENT CALLS: FSM mechanics (12), isolated stubs (5), test stubs (1), ABC gaps (39) — all correct
- SUGGESTED NEXT TOOLS: list_stubs, feature_shape, find_abc_gaps — appropriate

**False positive caught and fixed (commonplace):** analyze_corpus labeled commonplace "Connectivity-dominant" (42 orphaned, 71%) even though it's a 60-function Flask app where HTTP routes aren't in the static graph. Fix: added `orphaned_impl >= 50` floor to connectivity-dominant threshold (matches detect_topology and frontier_coverage floors).

**rotjs (library):** SHAPE "unclear" — correct. No false positives.

**Outcome:** FIXED — analyze_corpus ships. False positive corrected. 391 tests pass.

---

## 2026-08-04 — Session 299 continued: false positive fixes + find_abc_gaps

### Tool: analyze_corpus — static/ false positive in built_isolated
**Delta:** `static/` (75 symbols, 6 EPs) appeared as "built-but-isolated" in dj2. Web assets
(JS/CSS) are not Python subsystems to wire into the application.

**Fix:** Added `_is_asset_dir()` helper (filters static, assets, public, dist, build, vendor,
node_modules, www, media). Applied in both analyze_corpus and list_features built_isolated
and wired_incomplete checks.

**Outcome:** FIXED — static/ no longer appears. dungeon_neo/ remains correctly flagged.

---

### Tool: list_features — config/ false entry point count (bare-suffix collision)
**Delta:** list_features showed config/ with 60 entry points and flagged it as
"wired-but-incomplete." analyze_corpus correctly showed 0 EPs for config/. Root cause:
list_features builds callee_feat_map with a bare-suffix fallback for qualified names (e.g.
BarterFSM::action::add_gold also maps "add_gold"). FSM action names like "offer", "confirm",
"cancel" are common enough to match unrelated callers in graph_edges. The 60 EPs are false.

**Fix needed:** The bare-suffix fallback in list_features needs a guard against FSM-qualified
names (names containing "::"). The fallback is correct for module.method notation but creates
false positives for FSM state machines.

**Outcome:** FIXED (4ff3ea9) — bare-suffix fallback now skips names containing "::" (FSM-qualified). config/ no longer appears in wired-but-incomplete.

---

### Tool: find_abc_gaps — decision text truncation + missing summary
**Result on dj2:** 39 intentional scaffolds, 0 real gaps. All from engine/phases.py (8 ABC
classes: AuthorityPhase, ConsequencePhase, InputPhase, InterpretationPhase, PersistencePhase,
PhaseSystemFactory, StateMutationPhase, ViewProjectionPhase).

**Delta 1:** Decision text truncates mid-sentence: "engine/phases.py defines the phase
interface... The design is complete - all" cuts off. Developer can't see the full reasoning.

**Delta 2:** No summary line at the end. Developer has to count to know "39 scaffolds, 0 real
gaps, 0 unclassified." A summary would close the loop.

**Outcome:** FIXED (471740a) — decision text truncation fixed; summary line added showing class/method counts.

---

## 2026-08-05 — Evaluation run against dj2 (session 305)

### Tool: list_entry_points — FSM JSON config symbols appear as inferred EPs

**Probe output:** 116 explicit + 345 inferred EPs. Inferred breakdown by file type:
Python 277, JavaScript 46, FSM config JSON 22.

**Delta:** 22 FSM config symbols (BarterFSM::state::awaiting, BarterFSM::event::confirm, etc.
from config/fsms/*.json) appear as inferred EPs. These are state machine definitions — machine-readable
keys for the FSM dispatcher, not callable functions. They have no callers (confirmed by graph query)
so they pass the has_callers check, but they are not entry points in any architectural sense.

Root cause: `_ep_tier()` has no file-extension guard. Any symbol that isn't a dunder, serializer,
or test function falls through to "inferred", regardless of file type. JSON files containing FSM
configs have 45 symbols total; 22 appear as inferred EPs (rest are stubs).

JavaScript EPs (46) are legitimate — CharacterCreator.init, TravelUI.startJourney, etc. are real
browser-side entry points with no Python callers, correctly classified.

**Fix needed:** In `_ep_tier()`, if file_path ends in `.json` (or other non-code extensions),
return "protocol" to exclude it from EP classification. JSON files are config/data, not code.

**Outcome:** FIXED — see below.

---

### Tool: list_stubs — _caller_names false "(unresolved)" for Class.method callers

**Probe output:** All 5 "tail" stubs show "(unresolved)" callers: ContextBuilder.build,
WorldAI.__init__, AuthoritySystem._validate_creation_action, NarrativeEngine.advance_story_arc.

**Delta:** The `_caller_names` lookup does `f2.name = ge.caller` (exact match). But graph_edges
stores callers as qualified `Class.method` names (e.g., "ContextBuilder.build"), while functions
table stores bare method names (e.g., "build"). The exact match always fails for Class.method
callers → all labeled "(unresolved)".

Verified against DB: 4 of 5 labeled callers actually exist in the corpus under bare names:
- ContextBuilder.build → build in context_builder.py (is_stub=0) — FALSE-UNRESOLVED
- AuthoritySystem._validate_creation_action → _validate_creation_action in authority_system.py — FALSE-UNRESOLVED
- NarrativeEngine.advance_story_arc → advance_story_arc in narrative_engine.py — FALSE-UNRESOLVED
- WorldAI.__init__ → __init__ ambiguous (many matches, can't confirm) — AMBIGUOUS

Session 298 concluded "phantom edges, treat as lower priority" based on this annotation. That
conclusion was wrong: _get_encounter_context and _get_combat_context have real implemented
callers and block real code. They deserve higher priority, not lower.

**Fix needed:** In `_caller_names`, when exact match fails, try bare name + caller_file lookup.
If found, report as resolved (no "(unresolved)" annotation).

**Outcome:** FIXED — see below.

---

### Tool: detect_topology — ABC-interface=0 silent when no-subclass ABCs exist

**Probe output:** ABC-interface: 0. No ABC action queue line.

**Delta:** `_get_abc_gap_set()` only flags ABCs where a concrete subclass exists but is missing
overrides. When NO concrete subclass exists (phases.py pattern: 8 ABCs, 39 abstract methods,
no concrete implementation), it returns 0 gaps. detect_topology shows 0 and drops the action
queue line entirely — the developer has no signal to run find_abc_gaps() and never learns about
the 39 abstract methods.

Verified: 39 @abstractmethod functions in engine/phases.py, all in all-abstract classes.

**Fix needed:** When abc_gap_count=0 but abstract methods exist in all-abstract classes, add
a note: "ABC-interface: 0 concrete gaps — N abstract methods with no subclass; run
find_abc_gaps() to classify as accepted scaffolds or real gaps."

**Outcome:** FIXED — see below.
