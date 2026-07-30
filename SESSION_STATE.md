Written at commit: 00101d6

# SESSION STATE — session 270 (end)

## Active branch: main [V]

## This session (committed) [V]

- `f74b349` — ForceGraph white-glove parity with pyray graph_explorer
- `00101d6` — ego-graph focus mode: empty start, Overview on demand

---

## WHAT HAPPENED THIS SESSION

**ForceGraph white-glove audit (full pyray parity)** [V]
- Rewrote the entire ForceGraph JS section in console.html (~350 lines)
- All pyray graph_explorer.py behaviours now implemented in-browser:
  - `_fgSelect()`: callers (green), callees (red), `_selDim` for non-neighbours
    in expand mode, `_selEdge` on incident edges — matches pyray `_select_node`
  - Gold halo + white ring on selected node — matches pyray `_draw_node` rings
  - `onBackgroundClick` → deselect
  - `onEngineTick`/`onEngineStop` → "settling…" overlay show/hide
  - Minimap click-to-pan via stored `_fgMinimapGeo`; viewport rect in COL_MINIMAP_VP
  - Minimap nodes coloured by selection state
  - Escape: expand mode → `_fgLoadFull()`; else → clear selection
  - Enter on `gxInput` → `gxMap()`
  - After `graph_expand_result`: select + frame center node; expand-mode dim
  - F key: frame selected or zoomToFit; Ctrl+0: zoomToFit
  - Double-click → `_fgExpand` + set `_fgExpandedId`
  - New state: `_fgSelectedId`, `_fgExpandedId`, `_fgMinimapGeo`
  - `_fg.refresh()` → `_fg.resumeAnimation()` (correct v1.51.4 API)
- Also added `graph_full` and `graph_expand` socket handlers to `ui_server.py`

**Ego-graph focus mode** [V]
- Map tab previously auto-loaded 200 nodes on open
- Now starts empty: "Search a symbol to start, or click Overview"
- "Overview" button in toolbar loads top-N by degree (same as before)
- Searching a symbol from empty hits the expand branch → ego-graph seeds from that node
- Queued for review during Bart's full analysis workflow walkthrough

**Popover (sym-popover) — resolved** [V]
- Decision: leave it. It fires for sym-link clicks in chat/workbench/call tree.
  Bart doesn't consciously use it; removing it risks breaking symbol link clicks.
  Not worth touching until the full flow review.

---

## WHAT IS QUEUED FOR FLOW REVIEW

Bart wants a session where he walks through the full analysis workflow using the tool.
During that session, review:
- Ego-graph focus mode vs overview — does the split feel right in practice?
- Popover vs panel — after using both surfaces, decide if popover should go away
- Drop-box / breadcrumbs / history for pinning nodes across surfaces
- Full navigation flow: chat result → sym-link → graph → expand → workbench → back

---

## KNOWN ISSUES / TRAPS

- Phase D pyray framing unverified visually [?]
- type_missing=1.000 for all dj2 stubs — CamelCase docstring words, not corpus classes [V]
- RM70 V1/V2 scores vary run-to-run (LLM non-determinism) — take means [V]
- websocket-client must be installed in venv for bridge to work reliably [V]

---

## WHAT TO DO NEXT SESSION

1. **Bart walks through the analysis workflow** — next session is a demo/use session.
   Start UI server, load dj2, Bart asks questions, we find gaps together.
   This drives the flow review items above.

2. **RM67 probe** — standing rule, skipped multiple sessions.

3. **RM72 Phase D visual verify** — start UI + pyray, click node, run workbench,
   confirm "⬡ Show in Graph" frames correctly.

4. **RM70 Steps 3+** — pattern sibling search (Levenshtein), return-shape inference.
   Run `tools/rm70_baseline.py` after each step.

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Baseline runner: `.venv\Scripts\python.exe tools\rm70_baseline.py` (llama-server only, no UI)
- Graph explorer CLI: `.venv\Scripts\python.exe tools\graph_explorer.py C_Users_bartl_dev_dj2.db`
