Written at commit: 8d9ff32

# SESSION STATE — session 278 (end)

## Active branch: main [V]

## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**GAP-4: wiring gaps fix** [V]
Root cause confirmed: routing was correct all along — domain_analyst bypass fires for
all "what is the state of X?" phrasings. The actual bug was in `_build_wiring_gaps`:
stubs with 0 callers were silently skipped with `continue`, so corpora where all stubs
are orphans (dj2: all 25 stubs have 0 callers) always got "No direct wiring gaps found."

Fix: isolated stubs now produce "X is unimplemented and not yet connected to any caller"
(or grouped "X and N other stub(s)..."). Connected stubs (callers waiting) unchanged.
8 new tests in `tests/regression/test_domain_analyst.py`. FILE_MAP and TEST_MAP updated.
Commits: 8237b2f (fix), 8d9ff32 (tracker update).

Also confirmed: `_is_domain_analysis_question` routing was already correct before this session.
The SESSION_STATE claim that "synthesis is absent" reflected the output quality bug, not missing routing.

**RM76 usage: decisions.toml seeded for dj2** [V]
Created `C:\Users\bartl\dev\dj2\.determined\decisions.toml` — 9 decision records:
- `_get_encounter_context`: critical, must implement first in encounter domain
- `_get_combat_context`: implement alongside encounter context (same class)
- `process_consequences`, `_register_world_tools`, `on_arc_completed`: post-context stubs
- `subrace_stubs`: 5 functions in dnd_data.py — delete, not implement (out of scope)
- `test_mock_stubs`: 3 test-file stubs accepted as scaffolding
- `phases_abstract_methods`: phases.py ABC methods are design-complete — build concrete classes
- `encounter_implementation_order`: dependency-ordered sequence for encounter closure

File is untracked in dj2 repo — Bart commits when ready.
Loads cleanly: `load_decisions("C:/Users/bartl/dev/dj2", conn)` → 9 decisions, 0 name_resolutions.

---

## WHAT IS NOT YET DONE

- GAP-4 remaining: section 5 DESIGN thin until dj2 re-ingested with design_docs
- GAP-4 larger arc (TRACKER tiers 2-4): plan layer, direction layer not started
- dj2 re-ingest: needed to restore design_notes + get full 25 stubs into DB (current DB stale)
- dj2 decisions.toml: untracked in dj2 repo — Bart to commit
- assessor.py docstring gap: 37 missing — not urgent
- Plan layer (workflow_items from analysis): not built

---

## WHAT TO DO NEXT SESSION

1. **dj2 full re-ingest via UI** — start server, load dj2, run full ingest with design_docs.
   This restores: design_notes (section 5 DESIGN), full 25 stubs (not just 13), GAP-3 JS edges.
   After re-ingest, test Ask bar with "what is the state of the encounter subsystem?"
   and verify section 4 WIRING GAPS now shows the isolated stub list.

2. **GAP-4 quality verification** — after re-ingest, probe the analyst with dj2:
   - "what is the state of the encounter subsystem?" → expect 6 sections, section 4 non-empty
   - "what is the state of the subrace system?" → expect stubs listed, section 6 says "delete"
   If section 5 DESIGN is still thin, check whether decisions.toml entries are surfacing.

3. **GAP-4 plan layer (Tier 2)** — analyst output → ordered workflow_items in Build Queue.
   This is the next unbuilt tier from the TRACKER larger arc. Start after re-ingest confirms
   the analyst is producing useful output.

---

## KNOWN ISSUES / TRAPS

- dj2 DB currently stale: CLI ingest (no design_docs, only 13 of 25 stubs) was run for
  GAP-3 verification last session. Full UI re-ingest needed. [V]
- decisions.toml in dj2 loads correctly but is not yet committed to dj2 git. [V]
- Ask bar browser automation: Set `#q-input` value + dispatchEvent + click `#send-btn`.
  Use JS not refs. [V]
- After read_page(all), refs go to (0,0) — always use JS for Ask bar interaction. [V]
- No tests for `pattern_executor.py` in FILE_MAP. [V]
- dj2 DB schema: stub data is in `functions` table, NOT `symbols`. graph_edges uses
  `resolved` (0/1). [V]
- chain_context upstream paths may surface test EPs (test_ functions with 0 callers)
  rather than prod EPs — reverse BFS walks all callers. [?]
- wiring_chain cross-contamination filter works for clean subsystem names but may fail
  if src and dst share a common word. [?]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts. Only kill if a
  duplicate is accumulating (multiple processes on same port).
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py`
