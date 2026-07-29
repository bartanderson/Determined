Written at commit: 5f7f29c

# SESSION STATE — session 267 (end)

## Active branch: main [V]

## This session (committed) [V]

- `c4248e2` — fix(graph_explorer): context menu position bug + dedup (RM72 Phase B)
- `37d4f24` — feat(graph_explorer): cluster semantic summary in panel (RM72 Phase C)
- `594740a` — chore: add graph_explorer.py to FILE_MAP and TEST_MAP
- `5f7f29c` — feat(graph_explorer): reverse bridge Show in Graph (RM72 Phase D)

---

## WHAT HAPPENED THIS SESSION

**RM67 probe — clean** [V]
- dj2: 25 stubs stable (12 FSM actions/guards accepted, 5 subraces RM68, 3 test mocks, 5 real gaps)
- Determined: 12 stubs all test mocks; `suggest_tags` still the one real frontier stub
- Unresolved edge ratios: dj2 87.8%, Determined 95.6% — accepted ceilings, no change

**RM72 Phase B — context menu position bug fixed** [V]
- Bug: menu drawn clamped to screen edge, hit-test used unclamped raw coords → clicks off-target near edges
- Fix: `_ctx_menu_clamped()` computes cx/cy once at right-click time, stored in `_ctx_menu` dict
- Both `_draw_ctx_menu` and hit-test now read `cm["cx"]`/`cm["cy"]`
- Deduplicated: `_CTX_MENU_ITEMS`, `_CTX_MENU_W`, `_CTX_MENU_H`, `_CTX_MENU_DIV` module constants

**RM72 Phase C — cluster semantic summary in panel** [V]
- `GraphDB.cluster_summary(hub, component_ids)` queries: files, entry points (http_route/is_tool),
  external callees (edges leaving component), semantic_summaries for hub
- Cached on `_select_node`; invalidated when selected hub changes
- Rendered in `_draw_panel` below callers/callees block, hub nodes only
- Entry points shown in green; summary text word-wrapped to ~32 chars

**RM72 Phase D — reverse bridge "Show in Graph"** [V]
- `gxShowInGraph(symbol)` emits `gx_highlight` via socket
- `_gxInjectBtn(container, symbol)` injects "⬡ Show in Graph" button — only when badge visible
- Workbench: button injected into output header row after `workbench_tool_result`
- Oracle: link injected below result div after `oracle_result`
- `ui_server.py`: `handle_gx_highlight()` added — relays browser emit to all clients
  (graph explorer bridge already listened for `gx_highlight`, was just never forwarded)
- `_gxSymbol` JS var tracks last graph-selected symbol; used as fallback if result has no symbol

**FILE_MAP / TEST_MAP updated** [V]
- `determined/ui/graph_explorer.py`: [] (no regression tests — pyray UI window)

**Removed pass-only `__init__` stubs** [V]
- `PatternExecutor.__init__` and `ContractDriftClassifier.__init__` removed (were false positives in probe)

---

## KNOWN ISSUES / TRAPS

- `websocket-client` must be installed or bridge silently fails on reconnect. [V installed]
- Graph explorer window has no Win32 title — trackable by PID only. [V]
- `_gx_proc` in ui_server tracks subprocess; poll() detects exit and relaunches on button click. [V]
- Phase C cluster summary uses `component_ids = {n.id for n in self._nodes}` — works correctly
  for the top-level view but in expanded-node view the component is the neighborhood, not full cluster.
  Accepted for now; could be refined by walking connected components explicitly.

---

## WHAT TO DO NEXT SESSION

1. **RM67 probe** — standing rule, run first.

2. **RM72 Phase E — cluster semantic summary for expanded view**
   Currently `component_ids` is all nodes in view, which is correct for top-level but
   approximates in expanded mode. Could build a proper connected-component walk.
   Low priority — panel data is still useful as-is.

3. **RM70 Step 1 — V1+V2 baseline for sketch_stub**
   Measure current sketch_stub quality before adding the retrieval pipeline.
   File: `determined/agent/sketch_stub.py`. Run against dj2 FSM stubs as test set.
   Design: `docs/RM70_DESIGN.md`.

4. **RM71 calibration** (carried from s265)
   Calibrate complexity threshold against dj2 baseline stubs.
   File: `determined/agent/export_context.py`, `_COMPLEXITY_THRESHOLD = 0.5` (provisional).

5. **UI verify for Phase D**
   Phase D was not browser-verified this session (no server running).
   First action: start UI server, load dj2 corpus, open graph explorer, click a node,
   run a workbench tool, confirm "Show in Graph" button appears and clicking it frames the node.

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Graph explorer: click Graph button in UI tab bar, or CLI:
  `.venv\Scripts\python.exe tools\graph_explorer.py C_Users_bartl_dev_dj2.db`
- websocket-client required in venv for bridge to work reliably

## Known issues (carried)

- CUDA stubs: dim3 vars [?] — accepted ceiling
- C++ pure virtual not captured [?] — deferred to RM73
- Walker dispatch resolution (RM73) [?] — FUTURE
- RM71 complexity threshold: uncalibrated [?] — 0.5 provisional
