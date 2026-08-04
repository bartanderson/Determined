Written at commit: a9f60db

# SESSION STATE — session 292 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

Fixed F12 and F15. Browser-verified both. 1 fix commit + 1 wrap commit. [V]

---

## FIXES SHIPPED (verified in browser this session)

**F12 DONE** [V]: Call tree ← back button. Added `_ctHistory` stack +
`_ctCurrentRoot` tracker. `ctTrace()` pushes prior root before re-rendering;
`_ctRender()` factored out. ← button in `.call-tree-toolbar`; disabled until
first re-root; re-disables when stack empties. (console.html)
Browser test: re-rooted to `card.addEventListener`, ← re-enabled, click ←
returned to `CharacterCreator.renderStep`, ← disabled. [V]

**F15 DONE** [V]: Map "path from" button in node popover seeds `gxSrc.value`
and calls `gxDst.focus()`. Added as final entry in `_mnpButtons` all array.
(console.html)
Browser test: opened map panel, clicked "path from" — `gx-src` = symbol,
`document.activeElement.id === "gx-dst"` confirmed. [V]

---

## PREVIOUSLY SHIPPED (carried from s291)

F19, F2, F3, F7, F1, F10 — all done. [V s291]
F11, F14, F16 — verified already working. [V s291]

---

## REMAINING OPEN ITEMS

No F-series items remain. Check TRACKER.md for RM67 or new work. [V]

---

## WHAT TO DO NEXT SESSION

**1. Read TRACKER.md** — all F-items closed; pick up RM67 or whatever is next.

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
