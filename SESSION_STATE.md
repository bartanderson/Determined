Written at commit: fd768a6

# SESSION STATE — session 291 handoff (extended)

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

Fixed F19, F2, F3, F7, F1, F10. Verified F11, F14, F16 already working. [V]
4 fix commits + 1 wrap commit. 450 regression tests pass. [V]

---

## FIXES SHIPPED (all verified in browser)

**F19 DONE** [V]: Editor sym list duplicated — two files share same filename
(dungeon_neo/dm_tools.py + world/dm_tools.py). Switched `LIKE '%dm_tools.py'`
to exact equality `replace(file_path,'\\','/') = fp_fwd` in handle_open_file
(ui_server.py:2287-2296).

**F2 DONE** [V]: `LLM_MAX_TOKENS` 400 → 1200 in llm_client.py:38.

**F3 DONE** [V]: `.fp-link` elements (file paths in Ask answers) now get a click
handler in `attachSymbolHandlers()` (console.html:2770-2773) → `edOpenFile + activateTab("editor")`.

**F7 DONE** [V]: Blast radius extended impact filtered to project symbols via
`SELECT name FROM functions/classes WHERE name IN (...)` (agent_tools.py:197-208).

**F1 DONE** [V]: `find_large_files` outputs relative paths from project root so
`_shapeIndex.files` key lookup succeeds (agent_tools.py:2811-2816).

**F10 DONE** [V]: Raw fetch call-chain strings (`fetch('/api/...',\n{method:...}`)
stored verbatim in graph_edges.callee were appearing as call tree children. Added
`"\n" in (callee or "")` / `"\n" in (caller or "")` guards in handle_call_tree_expand
(ui_server.py:2085, 2106).

---

## VERIFIED ALREADY WORKING (no code change)

**F11** [V]: ct-sym click re-roots; ct-meta file:line opens editor.
**F14** [V]: ForceGraph onNodeClick → openMapPanel works.
**F16** [V]: Corpus map sym-link click opens popover in all tabs.

---

## REMAINING OPEN ITEMS

**F12** [?]: Call tree no breadcrumb/back after re-rooting on a callee.
Fix: push current root to a `_ctHistory` array before `ctTrace()`; add ← button
to call-tree toolbar that pops and re-traces. One level of back is enough.

**F15** [?]: Map "to symbol" field (#gx-dst) doesn't reliably receive focus.
Check whether ForceGraph canvas steals focus on background clicks.

---

## WHAT TO DO NEXT SESSION

**1. Fix F12** — call tree back button.
   In `ctTrace(symbol)` (console.html:1630), push the previous root before clearing.
   Add ← button in the call-tree toolbar (`#panel-call_tree .call-tree-toolbar`).

**2. Fix F15** — Map path "to symbol" input focus.
   After gx-src gets a value seeded (e.g. from node click), explicitly call
   `document.getElementById("gx-dst").focus()`.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V this session]
- Call tree: filter callees/callers whose name contains `\n` (raw JS code). [V this session]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
