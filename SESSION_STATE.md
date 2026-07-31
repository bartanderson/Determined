Written at commit: 6b86d52

# SESSION STATE — session 273 (end)

## Active branch: main [V]

## This session (committed) [V]

- `6b86d52` — feat(analyst): fully deterministic 6-section assessment — no LLM hedging

---

## WHAT HAPPENED THIS SESSION

**Analyst narration — ground-truth rule + new labels, first live test** [V]
- Loaded session 272 code (ground-truth assertion rule + enrichment label fix)
- First test: response started clean ("1. COMPLETE:") but model still hedged inline
  ("However, note:", "But note:") — ground-truth rule didn't suppress CoT style

**Prompt iteration — 5 attempts, all failed** [V]
- Attempt 1: ground-truth rule in system prompt (session 272 code)
- Attempt 2: pre-sorted SYMBOL STATUS block + bracket placeholder sections
  → model echoed the placeholders as meta-commentary instead of filling them
- Attempt 3: concrete one-shot example format
  → model copied the example structure but still reasoned through each slot
- Attempt 4: ASD-STE100 rules (SimpleEnglish repo) — ban modals, active voice,
  20-word limit, one claim per sentence
  → model ignored modal ban, used bullet reasoning steps instead
- Attempt 5: split into det sections 1-3 + LLM only for 4-6 (300 tokens)
  → model burned all 300 tokens reasoning, never wrote section 4 conclusion

**Root cause confirmed** [V]
Qwen3-8B with /no_think externalizes reasoning in output tokens regardless of
system prompt instructions. Style rules ("no hedging") are opinions; structural
constraints (word limits, modal bans) help but don't stop non-modal reasoning paths.
The model is fundamentally a CoT reasoner — prompt engineering cannot suppress it.

**Fix: fully deterministic analyst, no LLM** [V]
Refactored `build_domain_analysis` in `determined/agent/local_agent.py`:
- Sections 1-3 (COMPLETE/STUBS/ORPHANED): assembled from graph data in `_enrich_with_stub_status`
- Section 4 (WIRING GAPS): `_build_wiring_gaps` queries graph_edges for callers of each stub
- Section 5 (DESIGN): from knowledge_artifacts query already in enrichment
- Section 6 (FIRST STEP): stub with most callers waiting (first in stubs list)
Zero LLM calls. Instant response. Consistent output.

**Live test result** [V]
"what is the state of the encounter subsystem?" produced:
```
1. COMPLETE: generate_encounter (encounter_generator.py, 6 caller(s)); start_encounter...
2. STUBS: _get_encounter_context (context_builder.py, 1 caller(s) waiting); ...
3. ORPHANED: trigger_encounter (phases.py); test_encounter_flee_success; ...
4. WIRING GAPS: build → _get_encounter_context (unimplemented).
5. DESIGN: No design artifacts found — run discovery to build coverage.
6. FIRST STEP: Implement _get_encounter_context — it already has callers depending on it.
```
Clean, correct, no hedging, matches manual analysis in docs/analyses/dj2_encounter_analysis_1.md. [V]

**External references saved to memory** [V]
- SimpleEnglish / ASD-STE100: https://github.com/AminBlg/SimpleEnglish
  Key finding: "Clearly" is opinion, "no sentence over 20 words" is spec.
  Useful for future LLM prompt design — structural constraints beat style instructions.
- CEL engine article: https://bsid.io/writing/building-a-cel-engine-for-net
  Watch for: compile-once/evaluate-many pattern; ratcheting conformance skip-list.

---

## WHAT IS NOT YET DONE

- RM74 second question: "what is the wiring chain from travel to encounter?"
  Tests GAP-2 (chain synthesis). Not started this session.
- GAP-3 (JS→Python route matching): not built
- Plan layer (workflow_items from analysis): not built
- find_stub_islands not yet wired to UI Workbench picker

---

## WHAT TO DO NEXT SESSION

1. **RM74 GAP-2 probe** — ask "what is the wiring chain from travel to encounter?"
   in the live UI. If the analyst returns a data dump with no chain narrative, GAP-2
   is confirmed unfilled. Browser sequence: navigate → wait 6s → JS click Ask tab →
   set q-input value → click send-btn → wait 20s → read results innerText.

2. **RM67 probe** — standing rule, skipped again.

3. **Section 5 (DESIGN) quality check** — the live test showed "No design artifacts
   found." The encounter subsystem has FSM configs (encounter.json). The knowledge_artifacts
   query is matching on random domain_words extracted from fact text, not on the subsystem
   name. Fix: pass the subsystem name directly as the search term instead of random words.

---

## KNOWN ISSUES / TRAPS

- Ask bar browser automation: click Ask tab via JS (`.tab` elements, find one with
  "Ask" in textContent, call .click()). Then set `#q-input` value + dispatchEvent +
  click `#send-btn`. Do NOT use ref_14 — it toggles and closes if already open. [V]
- After read_page(all), refs go to (0,0) — always use JS for Ask bar interaction. [V]
- Section 5 DESIGN is returning "no artifacts" even when FSM configs exist — domain_words
  extraction is noisy; needs subsystem-name-based lookup instead. [?]
- No tests mapped to local_agent.py in FILE_MAP — if changes are made, add mapping. [V]
- Python test proxy is unreliable (thin facts = poor output). Always test analyst in live UI. [V]

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"` — find PID, kill it
- UI server restart: kill PID on 5050, then `preview_start {name: "Determined UI"}`, navigate
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py`
