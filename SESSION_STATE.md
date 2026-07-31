Written at commit: c80978d

# SESSION STATE — session 276 (end)

## Active branch: main [V]

## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

**ingest_design_docs on dj2** [V]
Ran CLI script against C_Users_bartl_dev_dj2.db. Result: 594 design_notes + 2
layer_rules stored from 15 docs. Before: zero design_note rows. Section 5 now
returns real content (5 encounter-matching rules) instead of "No design artifacts
found." Verified live in browser.

**GAP-1: find_stub_islands wired to Workbench** [V]
Added to _WORKBENCH_TOOLS in ui_server.py under Frontier category with optional
scope param. Tool was already implemented in agent_tools.py (commit a2231bd).
11 UI tests pass. Live verify: returns all 25 orphaned dj2 stubs grouped by file.

**GAP-2: chain_context tool built and wired** [V]
New tool in agent_tools.py (commit c80978d). Given a symbol, traces upstream
(reverse BFS to nearest EP) and downstream (forward BFS into callees), flagging
[STUB] gaps at each hop. Wired to Workbench Frontier palette. Registered in TOOLS
and test allowlist. Live verify: `_get_encounter_context` shows correct upstream
path through test harness; `trigger_encounter` correctly shows as orphan.

**RM67 probe — Determined corpus (self-model check)** [V]
DB: C_Users_bartl_dev_Determined.db. Results:
- 12 stubs: 2 real gaps (pattern_executor.__init__, contract_drift_classifier.__init__),
  1 known accepted (suggest_tags), 9 test mocks. 0 false positives.
- 95.6% unresolved edges — external-lib ceiling, accepted.
- 1426/2147 inferred EPs — framework-caller ceiling, accepted.
- Docstring health: 62.1% missing (test files dominant; assessor.py notable).
TRACKER.md updated with today's numbers for both Determined and dj2 rows (commit f9c9756).

**llama-server pre-flight rule corrected** [V]
Prior memory/SESSION_STATE said "kill llama-server before every UI start, no
exceptions." This was wrong — llama-server is stateless, no reason to kill it
unless a duplicate is accumulating. Memory file updated. SESSION_STATE pre-flight
rule corrected below.

---

## WHAT IS NOT YET DONE

- GAP-3 (JS→Python route matching): not built
- Plan layer (workflow_items from analysis): not built
- RM76 implementation (name/variable resolution decision ledger): design in TRACKER, not built
- test_detect_trace_call_chain_route: pre-existing failure (wiring_chain regex fires
  too broadly). Spawn task created for fix.
- assessor.py docstring gap: 37 missing — not urgent, noted in RM67 probe

---

## WHAT TO DO NEXT SESSION

1. **GAP-3: JS→Python route matching** — JS fetch() to Flask routes not joined.
   Check if route strings are already in the DB (graph_edges.callee or symbol_references)
   before building anything new.

2. **RM76 implementation** — design is in TRACKER.md. Build the name/variable
   resolution ledger (decisions.toml schema, auto-suggest trigger, human-confirm flow).

3. **wiring_chain pattern regex fix** — pre-existing test failure in
   test_technique3.py::test_detect_trace_call_chain_route. Tighten wiring_chain regex
   so generic noun phrases ("web route", "database") fall through to trace_call_chain.
   Spawn task is waiting.

---

## KNOWN ISSUES / TRAPS

- Ask bar browser automation: find `.tab` elements, click "Ask" via JS `.click()`.
  Set `#q-input` value + dispatchEvent + click `#send-btn`. Do NOT use ref_14. [V]
- After read_page(all), refs go to (0,0) — always use JS for Ask bar interaction. [V]
- No tests mapped to `local_agent.py` or `pattern_executor.py` in FILE_MAP. [V]
- dj2 DB schema: stub data is in `functions` table, NOT `symbols`. Symbols has no
  is_stub column. graph_edges uses `resolved` (0/1) not a missing-callee join. [V]
- wiring_chain fuzzy expansion: cross-contamination filter works for clean subsystem
  names but may fail if src and dst share a common word. [?]
- chain_context upstream paths may surface test EPs (test_ functions with 0 callers)
  rather than prod EPs — filter exclude_tests applies to find_entry_points set but
  reverse BFS walks all callers. [?]

---

## RESOURCE / PROCESS RULES [V]

- llama-server: stateless, no reason to kill between UI restarts. Only kill if a
  duplicate is accumulating (multiple processes on same port).
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py`
