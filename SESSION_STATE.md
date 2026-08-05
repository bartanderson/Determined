Written at commit: a21e32b

# SESSION STATE — session 305 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

**Option B from s304 handoff: dj2 delta probe.** Three gaps found and fixed, all in agent_tools.py.

### Delta 1: _ep_tier JSON false positives (commit 1026ece) [V]

`list_entry_points` was reporting 22 FSM config symbols (BarterFSM::state::awaiting, etc.
from config/fsms/*.json) as inferred entry points. Root cause: `_ep_tier()` had no
file-extension guard — any non-dunder, non-test symbol fell through to "inferred".
JSON files are config/data, not callable code.

Fix: added `.json`/`.yaml`/`.toml` check in `_ep_tier` returning "protocol" to exclude them.
dj2 inferred EPs: 345 → 323. JS EPs (46) unchanged — legitimate browser-side entry points.

Also corrected two stale NEEDS_FIX entries in DELTA_LOG that were fixed in s299 but never updated.

### Delta 2: _caller_names false "(unresolved)" for Class.method callers (commit a21e32b) [V]

`_caller_names` in list_stubs matched callers with `f2.name = ge.caller` (exact). But graph_edges
stores callers as `ContextBuilder.build` while functions stores bare `build`. All Class.method
callers appeared as "(unresolved)" even when the method existed in the corpus.

**Important**: Session 298 concluded "phantom edges, treat as lower priority" for
_get_encounter_context, _get_combat_context, semantic_match_subrace, on_arc_completed — that
conclusion was wrong. 4 of 5 labeled stubs have real implemented callers. These stubs block
real production code, not phantom edges.

Fix: bare-name fallback in `_caller_names` — if exact match fails, try `caller.rsplit('.', 1)[-1]`
in `caller_file`. Result: those stubs now show callers without "(unresolved)" annotation.

### Delta 3: detect_topology ABC silence on no-subclass classes (commit a21e32b) [V]

When `abc_gap_count=0`, the ABC action queue line was gated out (`if abc_gap_count > 0`). For
phases.py (8 ABCs, 39 abstract methods, no concrete subclass), detect_topology showed
"ABC-interface: 0" with no pointer to find_abc_gaps(). Developer had no signal.

Fix: added `else` branch — when abc_gap_count=0 but abstract methods exist in all-abstract classes,
surfaces: "0 concrete gaps — N abstract methods with no subclass; run find_abc_gaps() to classify."

459 tests pass [V].

### What the probe also confirmed (no delta — tool was correct) [V]

- list_stubs: FSM stubs separated, isolated/tail labels correct
- find_abc_gaps: 8 intentional scaffolds, 0 real gaps, summary line present
- analyze_corpus: SHAPE "Connectivity-dominant" correct; JUDGMENT CALLS correct
- detect_topology: Synthesis fires correctly
- frontier_priority: test-file tag on get_player_by_session correct
- blast_radius: works correctly (called with target= arg)
- Edge ratio: 87.6% unresolved — accepted ceiling [V]
- Docstring health: 54.5% missing for dj2 (not a delta; tracked separately)

DELTA_LOG updated with all 3 new entries (status FIXED). HISTORY.md updated with
_caller_names bug note.

---

## WHAT TO DO NEXT SESSION

**Step 0 — DB state.** Determined corpus is fresh (re-ingested s304). dj2 DB is fresh
(ingested before s304 probe). No re-ingest needed unless files changed.

**Option A: Run RM67 convergence probe update for dj2.**
The TRACKER's dj2 probe entry (2026-08-05) was written before today's fixes. The
"tail" stubs section now shows real callers without "(unresolved)". Re-run the probe
and update the TRACKER: does the stub classification change? Specifically:
- _get_encounter_context and _get_combat_context have real callers → may shift from
  "acknowledged" to "real gaps that block ContextBuilder.build."
- Run: list_stubs + frontier_priority on dj2 and compare to TRACKER entry.

**Option B: Pick next corpus for RM67 probe loop.**
All listed corpora have "probe-passes" status. If a new corpus is wanted,
RM75 is closed. Start fresh corpus or re-probe an existing one with the fixed tools.

**Option C: dj2 subrace cleanup (RM68).**
dj2-session only. Use blast_radius to confirm the 5 subrace stubs are truly dead,
then delete them. Now that we know the "unresolved" annotation was wrong, re-verify
they're truly isolated before acting.

**Option D: Further delta probe — list_features EntryPts vs feature_shape EPs.**
list_features shows world/ with 164 EntryPts; feature_shape('world') shows 39 Entry
points. Different definitions, same label, no explanation. Not logged yet — worth logging
and deciding if the terminology should be unified.

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
- dj2 "tail" stubs: prior session (298) concluded "phantom edges, lower priority" for
  _get_encounter_context etc. -- that was WRONG. Those callers ARE in the corpus. [V s305]
- analyze_corpus connectivity-dominant threshold requires orphaned_impl >= 50. [V s299]
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages. [V s299]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps. [V s300]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB forward-slash paths: when querying by file_path, use forward slashes not backslashes. [V s303]
- persist_file_analysis ingested_at fix: Python file rows now get ingested_at on every write.
  Old corpus DBs ingested before d48836f have NULL ingested_at for Python files -- detect_changed_files
  will see nothing on those DBs until a fresh re-ingest populates the timestamps. [V s304]
- _ep_tier now excludes .json/.yaml/.toml files (protocol tier). FSM config symbols no
  longer appear as inferred EPs. [V s305]
- _caller_names bare-name fallback: Class.method callers now resolved via bare name + caller_file.
  Re-run list_stubs on any corpus that previously showed surprising "(unresolved)" labels. [V s305]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old.
- reingest_changed is available as a tool: call it when corpus may be stale (files changed
  outside the editor). After the first re-ingest post-d48836f, it will work correctly.
