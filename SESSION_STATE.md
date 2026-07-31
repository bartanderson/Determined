Written at commit: 62e8050

# SESSION STATE — session 280 (end)

## Active branch: main [V]

## Working tree: clean (after this commit) [V]

---

## WHAT HAPPENED THIS SESSION

**GAP-4 Tier 2 — Plan layer** [V] (commit abbf018 + 62e8050)
New `generate_domain_plan()` in `determined/agent/local_agent.py`:
- Detects "plan for X" / "build plan for X" queries via `_is_plan_request()`
- Routes before domain analyst in Phase 3 bypass block
- Calls `_enrich_with_stub_status()` on facts; falls back to `_enrich_from_db()`
  when facts are empty (Phase 1 gives no NEED: lines for short queries)
- Writes ranked `workflow_items` to DB: stubs-with-callers → next_up #1,2,...;
  isolated stubs → next_up after; orphaned → backlog
- Returns plain-text summary of what was added
6 tests in `test_domain_analyst.py`, all pass.

Verified in UI: "plan for encounter" on dj2 produced 24 items in Build Queue.
`_get_encounter_context` ranked #1 (1 caller waiting). Build Queue tab renders
all 8 next_up items after tab activation fires `bqLoad()`.

**RM67 dj2 probe update** [V] (commit abab512)
Fresh probe numbers in TRACKER dj2 row:
- 594 design_notes, 9 decisions (now loaded from decisions.toml)
- 66 JS cross-boundary edges (33 http_fetch + 33 cross_language)
- Unresolved edge ratio: 87.6% (resolved=0 column; was 87.8% — same ceiling)
- Docstring: 804/1419 non-stub = 56.7% missing
- process_consequences: 0 callers (orphaned, not a blocker; prior entry called it a "real gap")
- No `is_entry_point` column in dj2 schema — old "inferred EPs 1131/1419" removed

**dj2 decisions.toml — FSM JSON stubs decision added** [V]
New `[[decisions]]` block for `fsm_json_callback_stubs` in
`C:\Users\bartl\dev\dj2\.determined\decisions.toml`.
Documents all 12 FSM stubs (EncounterFSM/TradeFSM/BarterFSM), explains
string-dispatch invocation (no static call edges), sets implementation sequencing.
File still untracked in dj2 git — Bart commits when ready.

---

## WHAT IS NOT YET DONE

- GAP-4 Tier 3 — Direction layer: re-run analyst after stub closes, surface what unlocks
- GAP-4 Tier 4 — Knowledge accumulation: store analyst runs as knowledge_artifacts
- GAP-1 — Island detection tool (`find_stub_islands`): pure graph query, no LLM
- GAP-2 — Chain synthesis: entry-point-to-implementation path with missing links
- dj2 decisions.toml: untracked in dj2 git — Bart to commit
- RM70 Step 1: V1+V2 baseline measurement (not started this session)
- RM72 Phase A: graph_explorer socket bridge (not started this session)

---

## WHAT TO DO NEXT SESSION

1. **Build Queue rendering check** — verify next session that Build Queue shows the
   24 encounter items from this session (they persist in the dj2 corpus DB).
   If they need de-duplication (plan run twice), `list_items(conn, status='active')`
   then `update_item(conn, id, status='done')` to clear.

2. **GAP-4 Tier 3 — Direction layer**: after a stub is implemented, re-run analyst on
   the domain, surface what just unlocked. Design: detect "I implemented X" or
   "X is done" → re-run `build_domain_analysis` → diff stubs list → report what's new.

3. **RM70 Step 1 baseline**: run `.venv\Scripts\python tools\rm70_baseline.py` without
   UI server competing (kill UI first). Get clean V1/V2 numbers to compare against s268
   partial result (5 stubs: V1 100%, V2 mean 0.833).

4. **RM72 Phase A socket bridge** — graph_explorer `_SocketBridge` class connecting to
   UI on localhost:5050. See TRACKER RM72 for full Phase A spec.

---

## KNOWN ISSUES / TRAPS

- Plan layer DB fallback: `_enrich_from_db` queries by LIKE on name/file_path.
  For subsystems with common words ("world", "game") this may over-match.
  Subsystem specificity matters — "encounter" is safe, "world" is not. [?]
- dj2 decisions.toml: untracked in dj2 git. [V]
- Ask bar browser automation: Set `#q-input` value + dispatchEvent + click `#send-btn`.
  Use JS not refs. [V]
- dj2 DB schema: no `is_entry_point` column — old probes that counted EPs used
  a different schema version. [V]
- chain_context upstream paths may surface test EPs (test_ functions with 0 callers). [?]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py`
