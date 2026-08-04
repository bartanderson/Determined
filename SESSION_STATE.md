Written at commit: 1e3ca94

# SESSION STATE — session 292 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

Fixed F12 and F15. 1 fix commit. [V]

---

## FIXES SHIPPED (all verified in browser)

**F12 DONE** [V]: Call tree ← back button. Added `_ctHistory` stack +
`_ctCurrentRoot` tracker. `ctTrace()` pushes prior root before re-rendering;
`_ctRender()` factored out for back button to call without side effects.
← button in `.call-tree-toolbar` (before ct-input); disabled until first
re-root. Wire: `ctBackBtn.addEventListener("click", ...)` pops stack, re-renders,
re-disables when empty. (console.html)

**F15 DONE** [V]: Map "path from" button seeds `gxSrc.value` and explicitly
calls `gxDst.focus()`. Added as final entry in `_mnpButtons` `all` array
(console.html). Shows in secondary actions row of the map node popover.
Bypasses ForceGraph canvas focus-steal because it fires from a button click,
not a canvas interaction. Verified button renders with correct label in panel.

---

## PREVIOUSLY SHIPPED (carried from s291)

F19, F2, F3, F7, F1, F10 — all done. [V s291]
F11, F14, F16 — verified already working. [V s291]

---

## REMAINING OPEN ITEMS

None tracked. All F-series items are DONE. [V]

Check TRACKER.md for any new items that may have been added.

---

## WHAT TO DO NEXT SESSION

**1. Check TRACKER.md** — all F-items are closed; look for RM67 or any new work.

**2. Verify F12/F15 in real use** — the browser JS eval confirmed the mechanics
work, but click through for real: open map tab, click a node, hit "path from",
confirm gx-dst gets focus and is typeable. Then open call tree, trace a symbol,
click a callee to re-root, confirm ← button is enabled and steps back correctly.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n` (raw JS code). [V s291]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
