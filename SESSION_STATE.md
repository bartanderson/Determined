Written at commit: 15ad109

# SESSION STATE — session 291 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

Fixed 5 of the remaining F-items. Verified 4 others already working. [V]
3 commits: F19+F2+F3 (92dda64), F7 (ef13686), F1 (15ad109). [V]
450 regression tests pass after agent_tools changes. [V]

---

## FIXES SHIPPED (verified in browser)

**F19 DONE** [V]: Editor sym list duplicated symbols because two files share the same
filename (dungeon_neo/dm_tools.py + world/dm_tools.py) and `LIKE '%dm_tools.py'` hit
both. Fixed in `handle_open_file` in ui_server.py:2287-2296 — use exact equality
`replace(file_path,'\\','/') = fp_fwd` instead of LIKE.

**F2 DONE** [V]: `LLM_MAX_TOKENS` bumped 400 → 1200 in llm_client.py:38. Ask answers
no longer truncate mid-sentence.

**F3 DONE** [V]: `fp-link` elements (file paths in backtick spans from Ask answers)
had no click handler. Added in `attachSymbolHandlers()` in console.html:2770-2773 —
calls `edOpenFile(el.textContent.trim()); activateTab("editor")`.

**F7 DONE** [V]: Blast radius extended impact included builtins (str, print, Flask,
forEach). Fixed in `blast_radius()` in agent_tools.py:197-208 — filter raw_extended
through `SELECT name FROM functions/classes WHERE name IN (...)` to keep project
symbols only.

**F1 DONE** [V]: Largest-files card filenames were basename-only; _shapeIndex.files
uses relative paths as keys so colorization never matched. Fixed in `find_large_files()`
in agent_tools.py:2811-2816 — compute `fp_rel` from project root via `oracle.get_project_root()`.

---

## VERIFIED ALREADY WORKING (no code change)

**F11** [V]: ct-sym name click re-roots call tree; ct-meta file:line click calls
`edOpenFile` which includes `activateTab("editor")`. Both work correctly.

**F14** [V]: ForceGraph `onNodeClick` handler at console.html:1902 calls `_fgSelect`
which calls `openMapPanel`. Node click + panel open confirmed in browser.

**F16** [V]: Corpus map sym-link click opens popover (openPopover) in all tabs.
Was blocked by F18 canvas overlay in s290; no code change needed this session.

---

## REMAINING OPEN ITEMS

**F10** [?]: Call tree anonymous fetch callbacks shown as raw multi-line code blocks.
Occurs when the callee name is a JS anonymous function `function(data){...}`. The
name text becomes the full function body rendered in the ct-sym span.

**F12** [?]: Call tree no breadcrumb/back after re-rooting on a callee. ct-sym click
re-roots to the callee, but there's no history stack to go back to the previous root.
Would need a `_ctHistory` array pushed/popped with re-root.

**F15** [?]: Map "to symbol" field (#gx-dst) doesn't reliably receive focus. Possibly
a timing issue when the graph canvas captures click events before the input can focus.

---

## WHAT TO DO NEXT SESSION

**1. Fix F10** — anonymous callbacks in call tree.
   The call tree `data.children[].symbol` for JS anonymous functions is the full
   function source code. Truncate or replace with `<anonymous>` when symbol contains
   `{` or newlines. Look at how `c.symbol` is built server-side in
   `handle_call_tree_expand` in ui_server.py.

**2. Fix F12** — call tree back button.
   In `ctTrace(symbol)` (console.html:1630), push the current root to a history array
   before clearing. Add a ← back button to the call-tree toolbar that pops from history
   and re-traces. One-level back is enough for now.

**3. Fix F15** — Map path "to symbol" input focus.
   In the gx-path-go click handler and the gx-src keydown handler, explicitly call
   `gxDst.focus()` after setting `gxSrc.value`. Also check whether the ForceGraph
   canvas is stealing focus on background clicks.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden` — otherwise canvases
  escape to nearest positioned ancestor and overlay the UI. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: use exact path equality, not LIKE basename, in DB queries. [V this session]
- `find_large_files` outputs relative paths from project root (not basename-only). [V this session]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- `_pull_type_defs`: two paths — classes table + functions LIKE 'TypeName::%'. [?]
- export_context session in-memory; resets on server restart. Intentional. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- llama-server: stateless, no need to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
