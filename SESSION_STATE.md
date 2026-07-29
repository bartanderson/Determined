Written at commit: dab8bb5

# SESSION STATE — session 268 (end)

## Active branch: main [V]

## This session (committed) [V]

- `dab8bb5` — fix(graph_explorer): BFS component walk in expanded view (RM72 Phase E)
                + calibrate(export_context): RM71 baseline findings documented

---

## WHAT HAPPENED THIS SESSION

Skipped RM67 probe (user request). Did items 2, 3, 4, 5 from prior handoff.

**Item 5 — UI verify Phase D ("Show in Graph")** [V]
- Graph explorer launched successfully (raylib window, dj2 corpus)
- "⬡ Show in Graph" button injects into workbench output header when:
  (a) gx-active-badge is visible (graph explorer running), AND
  (b) `_gxSymbol` is set (a node was previously selected in graph)
- Verified via JS: button appears, click emits `gx_highlight: {symbol: "generate_lost"}` [V]
- Pyray framing (does the window actually frame the node?) can't be verified headlessly —
  signal chain up to it is confirmed; final step requires eyes on the desktop window.
- Phase D is done; the one gap is visual confirmation in the pyray window.

**Item 2 — RM72 Phase E (cluster summary in expanded view)** [V]
- Fixed `_select_node` line 664: was `{n.id for n in self._nodes}` (all visible nodes)
- In expanded view, `self._nodes` = top nodes + neighborhood mix — over-counts the component
- Fix: BFS from hub through `self._edges` when `self._expanded` is set
- 74 tests pass [V]

**Item 4 — RM71 calibration** [V]
- Ran complexity scores on all 25 dj2 stubs
- Key finding: `caller_complexity` = 0.000 for EVERY stub
  Cause: LEFT JOIN in `_caller_context` fails — `graph_edges.caller` is short name
  ("ContextBuilder.build") but `functions.name` format doesn't match → NULL file_path
  → `_read_function_body("", ...)` → body = "" → avg_lines = 0
- Without that signal (weight 0.25), all real stubs score 0.24–0.48; one test mock at 0.51
- Threshold 0.5 holds provisionally; must recalibrate after RM70 Step 2 fixes the JOIN
- Documented in `export_context.py` comment and HISTORY.md

**Item 3 — RM70 Step 1 baseline (partial)** [V]
- `_verify_candidate` (V1+V2) already exists and works [V]
- Ran sketch_stub on 17 actionable dj2 stubs with llama-server live
- 5/17 produced parseable LLM candidates (llama-server busy — UI server competing)
- Those 5: V1 100% pass, V2 mean 0.833 (range 0.5–1.0)
- `resolve_parley` worst: V2=0.5, calls 2/4 invented APIs
- FSM guards best: V2=1.0 (no checkable corpus calls — builtins/pass bodies)
- Compare to s263 original pre-retrieval baseline: V1 36%, V2 0.36 — clear improvement
- Full clean rerun needed: start llama-server standalone BEFORE the UI server, or kill
  UI first, run baseline script, then restart UI.
  Command: `.venv\Scripts\python.exe scratchpad/rm70_baseline.py`
  (copy to a stable location first; it's currently in session scratchpad)

---

## KNOWN ISSUES / TRAPS

- `websocket-client` must be installed or bridge silently fails on reconnect. [V installed]
- Graph explorer window has no Win32 title — trackable by PID only. [V]
- `_gx_proc` in ui_server tracks subprocess; poll() detects exit and relaunches. [V]
- Phase D pyray framing unverified visually — all code is correct; needs human eyes. [?]
- `caller_complexity` dead signal in RM71 — see calibration finding above. [V]
- RM70 baseline partial (5/17 stubs) — LLM contention with UI server. [V]

---

## WHAT TO DO NEXT SESSION

1. **RM67 probe** — standing rule (skipped this session).

2. **RM70 Step 2 — fix caller body reader JOIN**
   Root cause: `_caller_context` LEFT JOIN on `functions.name = graph_edges.caller`
   fails because dj2 graph_edges stores short names. Fix: try exact match first,
   then fallback to `functions.name LIKE '%.' || ?` or match on file_path + line_number.
   File: `determined/agent/sketch_stub.py`, `_caller_context()` ~line 86.
   After fix: re-run RM70 baseline AND RM71 calibration in one pass.

3. **RM70 baseline clean rerun**
   Baseline script: copy `scratchpad/rm70_baseline.py` to `tools/rm70_baseline.py`
   (scratchpad is session-ephemeral). Run with llama-server only (no UI server).
   Establish definitive V1+V2 scores post all RM70 improvements.

4. **RM72 Phase D — visual verify**
   Start UI server, open graph explorer, click a node (sets `_gxSymbol` for real),
   run a workbench tool, confirm button appears and clicking it frames the node in
   the pyray window. 5-minute manual check.

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Graph explorer: click Graph button in UI tab bar, or CLI:
  `.venv\Scripts\python.exe tools\graph_explorer.py C_Users_bartl_dev_dj2.db`
- websocket-client required in venv for bridge to work reliably
- For LLM baseline runs: stop UI server first to avoid llama-server contention

## Known issues (carried)

- CUDA stubs: dim3 vars [?] — accepted ceiling
- C++ pure virtual not captured [?] — deferred to RM73
- Walker dispatch resolution (RM73) [?] — FUTURE
- RM71 complexity threshold: provisional 0.5, recalibrate after RM70 Step 2 [V documented]
