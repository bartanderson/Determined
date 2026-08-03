Written at commit: d885222

# SESSION STATE — session 290 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

Fixed 8 of the 18 F-items from session 289 exploratory findings. [V]
One substantive commit (54793f7) + two SESSION_STATE/HISTORY commits. [V]
77 targeted regression tests pass. [V]

---

## FIXES SHIPPED (verified in browser)

**F18 DONE** [V]: Cytoscape canvas was positioned relative to `.tab-content` (nearest
positioned ancestor) instead of its own container, placing the canvas at the top of
the content area and intercepting all tab bar clicks. Fix: `position:relative;
overflow:hidden` on `#fg-cy`, `#gx-cy`, `#ig-cy`. Verified with `document.elementFromPoint`
returning `BUTTON#` at tab center (was `CANVAS#`).

**F17 DONE** [V]: Verified this session — was blocked by F18. Opened world/dm_tools.py,
clicked `add_overlay` (line 400), editor scrolled to pos 427. Symbol navigation works.

**F6 DONE** [V]: Added `wrap.scrollIntoView({behavior:"smooth",block:"nearest"})` in
`wbRunTool()` in console.html immediately after the output wrap becomes visible.

**F9/F8 DONE** [V]: Added 5 tools to `_WORKBENCH_TOOLS` in ui_server.py:
- Performance: find_large_files, find_fetch_calls, find_hot_callers
- Architecture: find_cross_language_calls, find_pure_functions
All 5 confirmed present in live Workbench palette.

**F13/F4 DONE** [V]: Broadened agent_resolver.py patterns (77 tests pass):
- find_hot_callers: now matches "most called functions", "called most frequently"
- find_fetch_calls: now matches "JS functions make HTTP calls", "js http requests"
- find_pure_functions: now matches "no side effects", "stateless functions"

**F5 DONE** [V]: llm_client.py — added `_THINK_RE` to strip `<think>...</think>` from
chat() content; removed `reasoning_content` fallback (was the main leak path).

---

## NEW FINDING THIS SESSION

**F19** [V]: Editor sym list renders each symbol twice. Opened world/dm_tools.py —
5 distinct symbols shown as 10 rows. Root cause likely in the socket handler that
populates `#ed-sym-list` — double-append on re-render or duplicate socket event fire.
Investigate the `editor_open` or equivalent socket.on handler in console.html.

---

## REMAINING OPEN ITEMS

**F2** [V still open]: Ask LLM response truncates mid-sentence.
`LLM_MAX_TOKENS = 400` in llm_client.py. local_agent.py calls `_llm_chat` with no
override so uses the 400-token default. Bump to 1200. Quick fix.

**F3** [V still open]: Hyperlinked function names in Ask answers do nothing when clicked.
Find `socket.on("ask_result"` or equivalent in console.html. Links render (as `<a>` or
`.ed-sym-link` spans) but have no click listener attached. Add listener to fire
`activateTab("editor")` + editor open for the symbol name.

**F1** [V still open]: Largest-files card file names not clickable (Shape tab).
Find the corpus_projections socket handler that renders the card. Add click→editor nav.

**F11** [V still open]: Call tree callee names not clickable (no re-root via name, no
editor nav). Search console.html for `tr-line` — the callee row class. Click handler
missing or broken; ▶ re-root button works but the name text itself doesn't.

**F7** [V still open]: Blast radius extended impact includes builtins (Flask, SocketIO,
forEach, catch, str, print). 69 symbols shown; most are noise. Filter in blast_radius
in agent_tools.py — skip where file_path is None or is an external lib path.

**F15** [?]: Map "to symbol" field doesn't reliably receive focus.
**F10** [?]: Call tree anonymous fetch callbacks shown as raw multi-line code blocks.
**F12** [?]: Call tree no breadcrumb/back after re-rooting on a callee.
**F14** [?]: Map graph node click does nothing (hover + click have no handler).
**F16** [?]: Left nav entry point clicks only work in Call tree tab; no-op elsewhere.

---

## WHAT TO DO NEXT SESSION

**1. Fix F19** — duplicate sym list entries (quick, high visibility).
   In console.html find where `#ed-sym-list` is populated. Look for the event that
   fires it — likely `socket.on("editor_symbols"` or similar. Check if it appends
   without clearing first, or if the event fires twice.

**2. Fix F2** — bump Ask token limit (one-liner).
   `llm_client.py` line: `LLM_MAX_TOKENS = 400` → `LLM_MAX_TOKENS = 1200`
   Or add `LLM_ASK_MAX_TOKENS = 1200` and pass it from local_agent._call_llm.

**3. Fix F3** — Ask answer hyperlinks.
   Find the ask_result handler in console.html. Symbols appear as clickable spans
   already — check if click listeners are attached after `innerHTML` replaces the
   content (listeners on replaced nodes are lost). Use event delegation on the
   output container instead.

**4. Fix F11** — call tree callee name click.
   Grep console.html for `tr-line`. Should add click → `activateTab("editor")` +
   open symbol in editor.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden` — otherwise canvases
  escape to nearest positioned ancestor and overlay the UI. [V this session]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V]
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
