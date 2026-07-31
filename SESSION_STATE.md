Written at commit: 9553e65

# SESSION STATE — session 277 (end)

## Active branch: main [V]

## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**RM76: decisions ledger — .determined/decisions.toml** [V]
New module `determined/intent/decisions_ledger.py`. Reads `<target>/.determined/decisions.toml`,
materializes `kind='decision'` and `kind='name_resolution'` rows into `knowledge_artifacts`
on every `init()`. Idempotent (deletes prior human-confirmed rows, re-inserts). No-ops if
file absent. Two new kinds added to `VALID_KINDS`. `ui_server.py init()` hooked to recover
`_source_path` from `project_meta` and call `load_decisions`. `_check_design_violations_core`
now surfaces `'decision'` alongside `'design_note'`. Commit: ff5b14f

Also fixed pre-existing gap: `find_stub_islands` and `chain_context` added to `tool_registry.py`
(they were in TOOLS but missing from REGISTRY, causing `test_tool_registry_covers_all_tools` to fail).

**wiring_chain regex fix** [V]
"Trace the call chain from the web route to the database" was routing to `wiring_chain`
instead of `trace_call_chain`. Root cause: both the `call chain` arm and the `trace` arm
matched any word after `from`, including articles + generic nouns ("the web route").
Fix: `(?!(?:the|a|an)\s)` negative lookahead after `from` and `to` in both arms.
All 15 technique3 tests pass. Commit: 2a608a8

**GAP-3: JS→Python route matching** [V]
Root cause found and fixed. `_persist_cross_boundary_edges` disk-scan fallback guarded by
`not html_srcs and not js_srcs` — HTML templates from file_analyses made `html_srcs` non-empty,
so JS was never scanned from disk. Fixed by decoupling with `_need_html`/`_need_js` flags
computed before the loop. Re-ingest of dj2 now produces 21 JS `http_fetch` + `cross_language`
edges (e.g. `dungeon.enterIntegratedMode → dungeon_enter`, `CharacterCreator.completeCharacter → create_character`).
TRACKER GAP-3 marked FIXED. Commit: 9553e65

---

## WHAT IS NOT YET DONE

- GAP-4: Ask bar synthesis — retrieval works but no narration pass (data not analysis)
- Plan layer (workflow_items from analysis): not built
- assessor.py docstring gap: 37 missing — not urgent
- RM76 usage: decisions.toml schema is live; no dj2 decisions written yet (Bart's call)
- dj2 re-ingest needed to refresh DB after GAP-3 fix (CLI ingest was run for verification,
  but full engine ingest with design_docs not re-run this session)

---

## WHAT TO DO NEXT SESSION

1. **GAP-4: Ask bar synthesis** — retrieval is working; the gap is no narration pass after
   retrieval. Check `determined/agent/local_agent.py` around the Ask handler for where
   synthesis would hook in. The "what is complete / stub / orphaned / wiring gap" verdict
   needs to run after the semantic search returns context.

2. **RM76 usage: seed decisions.toml for dj2** — the ledger is live. Write the first
   `.determined/decisions.toml` for dj2 with the known architectural commitments:
   - _get_encounter_context must be implemented before encounter resolution closes
   - The 12 FSM stubs (encounter/trade/barter) are design-complete islands — implement next
   - The 5 subrace stubs are delete-candidates when dj2 coding starts

3. **dj2 full re-ingest** — re-run with the UI (not just the CLI tool) to get design_docs
   re-ingested alongside the new GAP-3 JS edges. CLI ingest cleared the DB; design_notes
   are gone until re-ingested.

---

## KNOWN ISSUES / TRAPS

- Ask bar browser automation: find `.tab` elements, click "Ask" via JS `.click()`.
  Set `#q-input` value + dispatchEvent + click `#send-btn`. Do NOT use ref_14. [V]
- After read_page(all), refs go to (0,0) — always use JS for Ask bar interaction. [V]
- No tests mapped to `local_agent.py` or `pattern_executor.py` in FILE_MAP. [V]
- dj2 DB schema: stub data is in `functions` table, NOT `symbols`. Symbols has no
  is_stub column. graph_edges uses `resolved` (0/1) not a missing-callee join. [V]
- dj2 DB currently stale: CLI ingest (no design_docs) was run for GAP-3 verification.
  Next session: re-ingest from UI to restore design_notes. [V]
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
