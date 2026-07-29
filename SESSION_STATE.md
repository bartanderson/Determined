Written at commit: 533ffca

# SESSION STATE — session 266 (end)

## Active branch: main [V]

## This session (committed) [V]

- `31cbda0` — feat(graph_explorer): pyray graph explorer with socket bridge (RM72 Phase A)
- `ad352a0` — fix: defer wbSetSymbol until workbench_tools loads
- `533ffca` — feat(graph_explorer): launch button in UI tab bar

---

## WHAT HAPPENED THIS SESSION

**RM72 Phase A — pyray graph explorer, fully integrated** [V]

New file: `determined/ui/graph_explorer.py` (~1360 lines)
Launcher: `tools/graph_explorer.py` (CLI entry point)

Key pieces:
- Force-directed layout (Fruchterman-Reingold): k=28, gravity=0.074, equilibrium ~378 world units
- Camera2D zoom centered on cursor; hard freeze after auto-frame so zoom is pure scale
- Panel: scrollable cluster list (top), search bar + results (middle), selected node details + action buttons, controls + minimap (bottom)
- `_SocketBridge`: connects to UI at :5050 via python-socketio WebSocket; emits `gx_select` on node click, `gx_navigate` on panel/menu actions, polls `gx_highlight` for reverse routing
- Panel action buttons: Workbench | Oracle | Map | Call Tree | Editor (hit-rect recorded each frame)
- Right-click context menu on nodes and panel with same destinations + Copy name/path
- `_navigate_to()`: dispatches to bridge or local (VS Code via `code --goto`, clipboard)

UI server additions (`ui_server.py`):
- `@socketio.on("gx_navigate")` -> broadcasts `gx_nav`
- `@socketio.on("gx_select")` -> broadcasts `gx_selection`
- `POST /api/launch_graph_explorer` -> spawns explorer subprocess with active corpus DB name

console.html additions:
- `Hexagon Graph` button in tab bar -> calls launch endpoint
- `gx-active-badge` span shows selected symbol name
- `socket.on("gx_nav")` -> activateTab + loads symbol into target surface
- `socket.on("gx_selection")` -> updates badge
- `wbSetSymbol()` fills all workbench symbol inputs by type
- `launchGraphExplorer()` fetch wrapper with spinner state

**Bridge verified live** [V]
- `gx_select` -> badge updated in Chrome
- `gx_navigate` -> workbench tab activated + all symbol inputs filled
- `gx_navigate` -> call_tree tab activated + ct-input filled

---

## KNOWN ISSUES / TRAPS

- `websocket-client` must be installed (`pip install websocket-client`) or the bridge
  silently fails on reconnect. Already installed this session. [V]

- `wbSetSymbol` timing fix: gx_nav to workbench defers fill via `socket.once("workbench_tools")`
  if _wbTools is empty (first open). [V]

- Graph explorer window has no Win32 title -- PowerShell `MainWindowTitle` is empty.
  Process is trackable by PID only. [V]

- `_gx_proc` in ui_server tracks the subprocess; if the user kills the window and
  clicks the Graph button again, `poll()` detects exit and relaunches. [V]

---

## WHAT TO DO NEXT SESSION

1. **RM67 probe** -- run at session start (standing rule).

2. **RM72 Phase B -- context menu polish**
   Right-click context menu is functional. Verify it fires correctly at various zoom levels.
   Hover highlight on items draws correctly but test at edges.

3. **RM72 Phase C -- cluster semantic summary**
   When a cluster hub is selected, show files, entry points, external callees, and
   semantic_summaries from DB in the panel. Add a `GraphDB.cluster_summary(hub)` method.

4. **RM72 Phase D -- reverse bridge "Show in Graph"**
   Add "Show in Graph" links on symbol_context / call_tree results in the UI that emit
   `gx_highlight` -> graph explorer selects and frames that node.

5. **FILE_MAP / TEST_MAP update**
   `graph_explorer.py` is new but has no tests. Add file -> [] mapping to FILE_MAP in
   `tools/run_tests.py` and TEST_MAP.md so the test runner doesn't skip it.

6. **RM71 calibration** (carried from s265)
   Calibrate complexity threshold against dj2 baseline stubs.
   File: `determined/agent/export_context.py`, `_COMPLEXITY_THRESHOLD = 0.5` (provisional).

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` -- two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Graph explorer: click Graph button in UI tab bar, or CLI: `.venv\Scripts\python.exe tools\graph_explorer.py C_Users_bartl_dev_dj2.db`
- websocket-client required in venv for bridge to work reliably

## Known issues (carried)

- CUDA stubs: dim3 vars [?] -- accepted ceiling
- C++ pure virtual not captured [?] -- deferred to RM73
- Walker dispatch resolution (RM73) [?] -- FUTURE
- RM71 complexity threshold: uncalibrated [?] -- 0.5 provisional
