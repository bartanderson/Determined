Written at commit: 2c2d132

# SESSION STATE — session 301 final handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION (full arc)

**1. RM67 self-probe on Determined corpus (2c2d132)** [V]

Determined corpus DB was stale since 2026-07-17 (3 weeks). Re-ingested fresh before probing.
29 test files skipped due to BOM/unicode encoding issues -- pre-existing, not new.

Probe results (all 5 steps):
- Step 1 (stubs): 1 real stub -- `suggest_tags` in `tagger.py` (known accepted, frontier).
  9 test mocks across 3 test files. 0 false positives.
  Prior "real gaps" (`pattern_executor.__init__`, `contract_drift_classifier.__init__`)
  WERE PHANTOM DETECTIONS in the stale July 17 DB. Fresh re-ingest cleared them.
  Neither class has or ever had an explicit `__init__`. See HISTORY.md 2026-08-05.
- Step 2 (unresolved edges): 95.4% overall (stable; external-lib ceiling, accepted).
- Step 3 (ABC gaps): agent + ingestion subsystems both clean.
- Step 4 (EPs): 587 EPs in `determined/`, 0 stubs.
- Step 5 (docstring health): 39.1% missing in core (non-test, non-example).
  Worst: `assessor.py` 37/53, `graph_explorer.py` 40/51, `runtime_locator.py` 17/21.

All 3 RM67 convergence criteria pass. [V]
TRACKER.md Determined row updated to 2026-08-05 probe. [V]
HISTORY.md: stale-DB phantom stub lesson added. [V]

**2. Phase D sidebar collapse -- verified already done** [V]

SESSION_STATE s300 listed "sidebar panel collapse" as a next step. Checked code and browser:
- `flex: 0 0 auto` already in style.css line 123.
- `sbMakeCollapsible()` in console.html line 4587 wires chevrons + localStorage.
- Browser verified: Oracle/Quick actions/Tools/Investigation default-collapsed;
  Corpus map + Analyze default-open; click toggles correctly.
Phase D was completed 2026-07-19. No work done -- confirmed done.

459 tests pass [?] (no code changes this session; unchanged from s300 verified run).

---

## WHAT TO DO NEXT SESSION

1. **Docstring health (optional cleanup).** 39.1% missing in core. Not a convergence blocker.
   Closeable in a focused pass: `assessor.py` (37/53), `graph_explorer.py` (40/51),
   `runtime_locator.py` (17/21), `db_oracle.py` (17/35). Do only if Bart wants to close it.

2. **Incremental re-ingest file-watcher (new RM item).** Re-ingest only changed files for
   active dj2 development. No design chosen -- surface as RM item, design first.

3. **Determined DB needs re-ingest each session.** The DB at session start was 3 weeks stale.
   Add re-ingest to session start if DB mtime is more than 1 session old.
   Script: `scratchpad/reingest_determined.py` (lives in temp; re-create from reingest pattern in ui_server.py handle_ingest).

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
- New tools registered in TOOLS dict: add AFTER function def, not inside the dict literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes and smart quotes.
  Use Git Bash (Bash tool) for commit messages containing special characters. [V s299]
- _get_abc_gap_set() excludes no-subclass ABCs by design -- they belong to find_abc_gaps.
  Re-adding the no-subclass block causes false JUDGMENT CALLs in analyze_corpus. [V s300]
- Stale corpus DB produces phantom stubs. Always re-ingest before trusting stub list
  if DB is more than one session old. s301: pattern_executor.__init__ and
  contract_drift_classifier.__init__ were phantom gaps in 3-week-stale DB; cleared by re-ingest.
  See HISTORY.md 2026-08-05. [V s301]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
- Determined corpus DB: re-ingest at session start if DB mtime > ~1 week old. Takes ~30s.
