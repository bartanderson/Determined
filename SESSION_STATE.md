Written at commit: b0391f2

# SESSION STATE — session 272 (end)

## Active branch: main [V]

## This session (committed) [V]

- `b0391f2` — feat(analyst): tighten narration quality — assert from data, not hedge

---

## WHAT HAPPENED THIS SESSION

**Analyst narration layer — live UI testing and iteration** [V]
- Restarted UI server with session 271 code (new code was NOT loaded last session)
- Ask bar toggle behavior identified: ref_14 is a toggle; clicking twice closes it.
  Pattern that works: navigate → wait 6s → read_page(interactive) → left_click ref_14
  → wait 2s → read_page(interactive) → ask bar at ref_33 (723, 84)
- First response observed: preamble leaked ("We are given structured facts...")
  — `/no_think` suppresses `<think>` tags but not inline CoT reasoning style
- Fixed: added no-preamble directive to `_ANALYST_SYSTEM`
- Fixed: added `_strip_reasoning_preamble()` post-processor — strips everything before
  first numbered section heading (1. COMPLETE / STUBS / etc.)
- Fixed: orphan query in `_enrich_with_stub_status` — was matching bare name, missed
  qualified callee names (e.g. `AdjudicationEngine.start_encounter`); fixed with
  `callee = ? OR callee LIKE %.name`
- Fixed: enrichment labels — "STUB (1 callers)" was contradictory, triggered model
  self-questioning; replaced with "UNIMPLEMENTED, 1 caller(s) depend on it"
- Added ground-truth assertion rule to `_ANALYST_SYSTEM`: facts are authoritative
  DB data, treat as ground truth, assert directly (based on HN thread on AI confidence)

**Quality status after fixes** [?]
- Last live UI test (before ground-truth rule): started clean with "1. COMPLETE:",
  had correct orphan data, some inline hedging remained ("But note:", "Actually")
- Ground-truth rule + new enrichment labels NOT yet tested in live UI
- Python test with minimal facts gave poor results (thin facts = more model reasoning)
  — not a valid proxy; live UI test with full pipeline facts is the real measure

**Browser automation discovery** [V]
- Ask tab is a toggle: one click = open, second click = close
- After calling read_page(all), the ask bar ref has coordinates (0,0) — element exists
  but is hidden; cannot click it until panel is open and ref is refreshed
- Reliable sequence: navigate → wait 6s → read_page(interactive) [no ask bar] →
  left_click ref_14 → wait 2s → read_page(interactive) [ask bar at ref_33] → use it

**HN research on AI confidence** [V]
- HN thread "Being Confidently Wrong is holding AI back" (id=44983570)
- Key finding: models don't distinguish "guessing from weights" vs "reading from
  provided data" — both get the same hedging treatment
- Prescription: when data is grounded (as our enrichment is), system prompt must
  explicitly contract "treat as ground truth, assert directly"
- Applied as new rule in _ANALYST_SYSTEM

---

## WHAT IS NOT YET DONE

- Ground-truth assertion rule NOT yet tested in live UI [?]
- GAP-2 (chain synthesis): not built
- GAP-3 (JS→Python route matching): not built
- Plan layer (workflow_items from analysis): not built
- find_stub_islands not yet wired to UI Workbench picker

---

## WHAT TO DO NEXT SESSION

1. **Test analyst narration quality** — restart UI, ask "what is the state of the
   encounter subsystem?". Check: does it start with a numbered section? Does it assert
   without hedging? Compare to manual analysis from docs/analyses/dj2_encounter_analysis_1.md.
   Browser sequence: navigate → wait 6s → read_page(interactive) → left_click ref_14
   → wait 2s → read_page(interactive) → click ref_33 → type → click ref_34 → wait 20s.

2. **Continue RM74** — next question: "what is the wiring chain from travel to encounter?"
   Tests GAP-2 (chain synthesis). If tool returns data dump with no chain narrative, GAP-2
   is confirmed unfilled.

3. **RM67 probe** — standing rule, skipped again.

---

## KNOWN ISSUES / TRAPS

- Ask bar toggle: clicking ref_14 twice closes it. Never click ref_14 more than once
  per navigate. After calling read_page(all), refs go to (0,0) — do read_page(interactive)
  after left_click ref_14 to get live coords. [V]
- Python test proxy is unreliable: thin fact set gives worse output than live pipeline.
  Always test analyst quality in the live UI, not the script. [V]
- Phase D pyray framing unverified visually [?]
- type_missing=1.000 for all dj2 stubs — CamelCase docstring words, not corpus classes [V]
- websocket-client must be installed in venv for bridge to work reliably [V]

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill pid on 5050, then preview_start {name: "Determined UI"}, navigate to refresh
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` (llama-server only, no UI)
- Graph explorer CLI: `.venv\Scripts\python.exe tools\graph_explorer.py C_Users_bartl_dev_dj2.db`
