Written at commit: 6c9c92a

# SESSION STATE — session 275 (end)

## Active branch: main [V]

## This session (uncommitted changes)

- TRACKER.md: RM76 expanded with full name resolution + variable resolution design

---

## WHAT HAPPENED THIS SESSION

**Section 5 DESIGN live verify** [V]
Ran "what is the state of the encounter subsystem?" in live UI. Section 5 still
returned "No design artifacts found." Root cause: the code fix from session 274 is
correct (uses subsystem name, queries subject LIKE 'encounter'). The data gap is real:
`knowledge_artifacts` in dj2 DB has zero rows of kind='design_note','finding','sots'.
All 2675 rows are inline_note/dead/entry/hot/response_shape/stub/pattern.
Conclusion: section 5 fix is correct; message is accurate; `ingest_design_docs` has
never been run on dj2. Not a bug — a data gap.

**RM67 probe — dj2 2026-07-30** [V]
25 stubs, all orphans (0 live callers). No regressions vs 2026-07-25.
- 12 FSM stubs (encounter/trade/barter JSON) — design-complete islands, nothing calls them yet (GAP-1)
- 5 subrace stubs (dnd_data.py) — delete when dj2 coding starts, accepted
- 5 real gaps: `_get_encounter_context`, `_get_combat_context`, `process_consequences`,
  `_register_world_tools`, `on_arc_completed`
- 3 test stubs — accepted mocks
Unresolved edge ratio: 87.8% — accepted world/ ceiling, no change.
Live-blocked stubs: 0 — no live code waiting on any unimplemented stub.
Inferred EPs: 1131/1419 real functions — inflated by FSM symbols + world/ ceiling.
Docstring health: 43.3% (804 missing).

**RM76 extended: name resolution + variable resolution** [V]
Triggered by Acoda paper (arxiv 2606.11755) — adversarial obfuscation that defeats
LLM analysis by breaking token-level name signals. Insight: Determined's structural
evidence (callers, callees, file path, inline notes) survives obfuscation; committing
derived name mappings as durable artifacts closes the gap.

Added two subsections to RM76 in TRACKER.md:
1. Name resolutions — function/symbol scope, graph evidence, `decisions.toml` schema
2. Variable resolutions — parameter/local/module scope, AST evidence, same ledger
   with `scope` + `parent` fields. Resolution chain: resolved symbol name propagates
   to its parameter canonicals so analyst output reads coherently at every level.
   Auto-suggest trigger: opaque name (≤3 chars or known pattern) + evidence threshold;
   human confirms before write.

---

## WHAT IS NOT YET DONE

- Section 5 data gap: `ingest_design_docs` not run on dj2 — no design_note artifacts exist
- GAP-3 (JS→Python route matching): not built
- Plan layer (workflow_items from analysis): not built
- find_stub_islands not wired to UI Workbench picker
- RM76 TRACKER changes uncommitted

---

## WHAT TO DO NEXT SESSION

1. **Commit TRACKER.md** — `git add docs/TRACKER.md && git commit`

2. **ingest_design_docs on dj2** — populate design_note artifacts so section 5 has
   content. Run via Workbench or CLI. Then re-run "what is the state of the encounter
   subsystem?" to confirm section 5 shows FSM config content.

3. **GAP-1: find_stub_islands UI wiring** — tool exists, not in Workbench picker.
   Wire it so the island detection is reachable from the UI.

4. **RM67 probe — Determined corpus** — probe dj2 done; run same probe on Determined
   itself (self-model check). DB: `C_Users_bartl_dev_Determined.db`.

---

## KNOWN ISSUES / TRAPS

- Ask bar browser automation: click Ask tab via JS (`.tab` elements, find one with
  "Ask" in textContent, call .click()). Set `#q-input` value + dispatchEvent + click
  `#send-btn`. Do NOT use ref_14 — toggles closed if already open. [V]
- After read_page(all), refs go to (0,0) — always use JS for Ask bar interaction. [V]
- No tests mapped to `local_agent.py` or `pattern_executor.py` in FILE_MAP. [V]
- dj2 knowledge_artifacts: zero design_note/finding/sots rows — section 5 will always
  return "No design artifacts found" until ingest_design_docs runs. [V]
- dj2 DB schema: stub data is in `functions` table, NOT `symbols`. Symbols has no
  is_stub column. graph_edges uses `resolved` (0/1) not a missing-callee join. [V]
- wiring_chain fuzzy expansion: cross-contamination filter works for clean subsystem
  names but may fail if src and dst share a common word. [?]

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py`
