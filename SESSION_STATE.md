Written at commit: fe5c659

# SESSION STATE — session 274 (end)

## Active branch: main [V]

## This session (committed) [V]

- `c44fb3b` — fix(analyst): section 5 DESIGN uses subsystem name not random words
- `fe5c659` — feat(analyst): GAP-2 chain synthesis — wiring_chain pattern + fuzzy symbol resolution

---

## WHAT HAPPENED THIS SESSION

**Section 5 DESIGN fix** [V]
`_enrich_with_stub_status` was mining random words from fact text to query
`knowledge_artifacts`. Fixed to extract the subsystem name from the question
(e.g. "encounter" from "what is the state of the encounter subsystem?") via
`_SUBSYSTEM_NAME_RE` and pass it as `subsystem=` param. Falls back to word-mining
only when no name is found. Live test not run (server not up at fix time).

**GAP-2 probe: "what is the wiring chain from travel to encounter?"** [V]
First probe run showed `[heuristic matched] ['symbols named wiring', ...]` —
LLM decomposed "wiring" as a symbol name, returned nothing. Pattern fired in
Phase 1, not Phase 0a.

**Root cause: `graph_path` already existed, but wasn't routed to** [V]
`graph_path` tool + `shortest_path` in `graph_utils.py` fully built since earlier
sessions. The gap was routing: "wiring chain from X to Y" fell through to LLM
decomposition. `trace_call_chain` pattern in `pattern_executor.py` only matches
HTTP→database chains, not general symbol-to-symbol chains.

**Fix: `wiring_chain` pattern + `build_chain_answer`** [V]
Three-layer change:
1. `pattern_executor.py`: added `wiring_chain` detect rule before `trace_data_flow`
   — catches "wiring chain/call chain/call path from X to Y", "how does X reach Y",
   "trace from X to Y"
2. `local_agent.py`: added `_CHAIN_RE`/`_CHAIN_RE2` for endpoint extraction,
   `build_chain_answer()` calling `shortest_path` with stub annotation
3. Phase 0a: routes `wiring_chain` pattern to `build_chain_answer`, bypasses all LLM

**Fuzzy symbol resolution required** [V]
The question says "travel" and "encounter" (subsystem words), not real function names.
`shortest_path('travel', 'encounter')` returns None. Three rounds of iteration:
- Round 1: source_id/target_id name-match only → missed `progress_journey` (in
  travel_system.py but name contains no 'travel')
- Round 2: added file-path expansion → cross-contamination: `generate_encounter`
  in travel_system.py appeared as a travel source, found spurious `generate_encounter
  → Encounter` path  
- Round 3: cross-contamination filter (exclude src candidates whose name contains
  dst word and vice versa) → clean

Final result [V]:
```
Call chain from 'progress_journey' to 'Encounter':
  progress_journey (travel_system.py) → generate_encounter (encounter_generator.py) → Encounter
```
Instant, deterministic, correct.

---

## WHAT IS NOT YET DONE

- Section 5 (DESIGN) fix not live-tested yet — server wasn't reloaded after that commit.
  Easy to verify: ask "what is the state of the encounter subsystem?" and check section 5
  now says something about encounter.json FSM configs instead of "No design artifacts found."
- GAP-3 (JS→Python route matching): not built
- Plan layer (workflow_items from analysis): not built
- find_stub_islands not yet wired to UI Workbench picker
- RM67 probe: skipped again this session

---

## WHAT TO DO NEXT SESSION

1. **Section 5 DESIGN live verify** — ask "what is the state of the encounter subsystem?"
   in the live UI. Confirm section 5 now returns FSM config content instead of "No design
   artifacts found." If still empty, check whether encounter.json artifacts are in
   `knowledge_artifacts` table at all (may need discovery pass first).

2. **RM67 probe** — standing rule, skipped two sessions running.

3. **Chain answer quality** — current output names `Encounter` (a class) as terminal node.
   Consider annotating class vs function, and whether the terminal node being a class
   (not a stub) changes the action hint logic.

---

## KNOWN ISSUES / TRAPS

- Ask bar browser automation: click Ask tab via JS (`.tab` elements, find one with
  "Ask" in textContent, call .click()). Set `#q-input` value + dispatchEvent + click
  `#send-btn`. Do NOT use ref_14 — toggles closed if already open. [V]
- After read_page(all), refs go to (0,0) — always use JS for Ask bar interaction. [V]
- No tests mapped to `local_agent.py` or `pattern_executor.py` in FILE_MAP. [V]
- wiring_chain fuzzy expansion: cross-contamination filter works for clean subsystem
  names but may fail if src and dst share a common word. Watch for this. [?]
- Section 5 DESIGN fix verified by regex test only, not live UI — see next session item 1. [?]

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py`
