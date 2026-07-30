Written at commit: 2c5ff74

# SESSION STATE — session 269 (end)

## Active branch: main [V]

## This session (committed) [V]

- `d432cf0` — fix(sketch_stub): two-phase caller lookup (RM70 Step 2 JOIN fix)
- `0f3c248` — calibrate(rm71): post-JOIN-fix findings; RM71 pass added to baseline script
- `89cf719` — feat(map): add workbench + ask buttons to node popover
- `5256adb` — fix(graph_explorer): start_line → line_number in editor nav
- `0c498a5` — fix(graph_explorer): complete Phase B/C — all broken navigation paths
- `2c5ff74` — feat(map): draggable floating node panel replaces popover on graph click

---

## WHAT HAPPENED THIS SESSION

**RM70 Step 2 — caller body reader JOIN fix** [V]
- `_caller_context` was LEFT JOINing `f.name = e.caller`; dj2 graph_edges stores
  "Class.method" but functions.name may store just "method" → NULL file_path → no body
- Fix: exact lookup first, then rsplit(".", 1) fallback for short-name callers
- 144 tests pass [V]

**RM70 baseline clean rerun + RM71 calibration** [V]
- `tools/rm70_baseline.py` created (standalone runner, no UI server needed)
- V1 pass: 71% (10/14), V2 mean: 0.357 — LLM non-determinism accounts for run-to-run variance
- caller_complexity now live post-fix: _get_combat_context=0.633, _get_encounter_context=0.633
- FSM stubs still caller_cx=0 (correct — no callers tracked in graph_edges for config-declared)
- type_missing=1.000 for ALL dj2 stubs: CamelCase words in docstrings match regex but are not
  corpus classes — noisy signal on this corpus; documented in export_context.py
- Threshold 0.5 holds; only _get_combat_context hits it (correct escalation) [V documented]

**Graph explorer — full nav audit and fix** [V]
- editor crash: wrong column name `start_line` → `line_number` [V]
- oracle pre-fill silent no-op: `question-input` → `q-input` in both gx_nav handler
  AND the popover "ask" button [V]
- Expand + Frame missing from context menu (_CTX_MENU_ITEMS); wired to
  _expand_node/_frame_node via self._cam stored in run() [V]
- Socket bridge gave up after 3 attempts; now retries every 5s indefinitely [V]
- _pending_highlight was a class variable (shared across instances) → instance var [V]

**In-browser map: draggable node panel** [V]
- Was: click node → dismissing popover near cursor, same 6 buttons always
- Now: click node → floating panel overlaid on graph canvas
  - Appears near click, drag header to reposition, pin survives node changes
  - X to close resets pin position
  - Adaptive primary buttons (2) by node type:
      stub → workbench + ask
      HOT  → ↙ callers + workbench
      EP   → ↗ callees + workbench
      else → workbench + ask
  - Secondary row: remaining 4 actions at reduced prominence
  - panel-map set to position:relative; panel is position:absolute within it
    so it naturally hides when map tab is not active
- Both _cy tap handlers (main map + path finder) → openMapPanel [V]
- symbol_quick_result now calls _mnpRender alongside _renderPopover [V]
- 11 UI surface tests pass [V]

**Open question from Bart (answer next session):**
"Did you revive the old style of display for some reason?"
Refers to the popover (sym-popover) which still fires for sym-link clicks
throughout the app (chat results, workbench output, call tree, frontier).
Map node clicks now use the panel. The popover is still live elsewhere —
is that the right call, or should the panel replace it everywhere?

---

## KNOWN ISSUES / TRAPS

- Phase D pyray framing unverified visually — all code is correct; needs human eyes. [?]
- type_missing=1.000 for all dj2 stubs — CamelCase docstring words, not corpus classes [V documented]
- RM70 V1/V2 scores vary run-to-run (LLM non-determinism) — take means, not single runs [V]
- websocket-client must be installed in venv or bridge silently fails on reconnect [V]
- Graph explorer window has no Win32 title — trackable by PID only [V]
- CUDA stubs: dim3 vars [?] — accepted ceiling
- C++ pure virtual not captured [?] — deferred to RM73

---

## WHAT TO DO NEXT SESSION

1. **Answer the popover question** — sym-popover is still live for sym-link clicks
   everywhere outside the map. Should it stay (lightweight quick-nav) or be replaced
   by the same draggable panel? If replaced: openMapPanel would need to work outside
   the map tab context (fixed positioning, not absolute within panel-map).

2. **RM67 probe** — standing rule, skipped two sessions running.

3. **RM72 Phase D visual verify** — still needs eyes on the pyray window.
   Start UI server, open graph explorer, click node, run workbench tool,
   confirm "⬡ Show in Graph" appears and clicking it frames the node in pyray.

4. **RM70 further steps** (build order in TRACKER RM70):
   Step 3 — pattern sibling search (corpus-scoped Levenshtein)
   Step 4 — return-shape inference
   Steps 5-7 after those.
   Run `tools/rm70_baseline.py` after each step to measure improvement.

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` (llama-server only, no UI)
- Graph explorer CLI: `.venv\Scripts\python.exe tools\graph_explorer.py C_Users_bartl_dev_dj2.db`
- websocket-client required in venv for bridge to work reliably
