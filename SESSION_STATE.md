Written at commit: 54793f7

# SESSION STATE — session 290 handoff

## Active branch: main [V]
## Working tree: clean, 1 commit this session [V]

---

## WHAT HAPPENED THIS SESSION

**Fixed 7 of the 18 F-items from session 289 exploratory findings** [V]
All fixes committed in one shot (54793f7). 77 targeted tests pass. [V]

---

## FIXES SHIPPED (verified in browser)

**F18 DONE** [V]: Root cause was `position:relative` missing from cytoscape containers.
Cytoscape canvases (`position:absolute`) were positioned relative to `.tab-content`
(the nearest positioned ancestor), not their immediate container — so `top:0,left:0`
placed them at the top of the content area, covering the tab bar.
Fix: added `position:relative;overflow:hidden` to `#fg-cy`, `#gx-cy`, `#ig-cy`.
Verified: `document.elementFromPoint` at tab center returns `BUTTON#` (was `CANVAS#`).
Tab switching works: Editor tab activates, Frontier panel goes `display:none`.

**F6 DONE** [V]: Added `wrap.scrollIntoView({behavior:"smooth",block:"nearest"})`
in `wbRunTool()` (console.html:5724) immediately after making the output wrap visible.

**F9/F8 DONE** [V]: Added 5 tools to `_WORKBENCH_TOOLS` in ui_server.py:
- Performance category: find_large_files, find_fetch_calls, find_hot_callers
- Architecture category: find_cross_language_calls, find_pure_functions
All verified present in live Workbench palette after server restart.

**F13/F4 DONE** [V]: Broadened agent_resolver.py patterns:
- find_hot_callers: now matches "most called functions", "called most frequently"
- find_fetch_calls: now matches "JS functions make HTTP calls", "js http requests"
- find_pure_functions: now matches "no side effects", "stateless functions"
77 regression tests pass including test_agent_resolver.py.

**F5 DONE** [V]: Fixed llm_client.py:
- Added `_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL|re.IGNORECASE)`
- Applied to content in `chat()`: `content = _THINK_RE.sub("", ...).strip()`
- Removed `reasoning_content` fallback (was the main leak path when content empty)

---

## REMAINING OPEN ITEMS (from F1-F18 list)

**F17**: Editor left symbol list — was caused by F18 (canvas overlay). Now that F18
is fixed, re-test: click Editor tab, click a symbol in the left pane. If still broken,
investigate the symbol click handler independently.

**F3** [V still open]: Hyperlinked function names in Ask answers are dead (no navigation).
Look for anchor/span click handlers in local_agent.py output formatting or console.html
`socket.on("ask_result")` handler. Links render but have no click listener.

**F1** [V still open]: Largest-files card file names not clickable.
Find the card renderer for "Largest files" in the Shape tab — probably in the
corpus_projections socket handler. Add click→editor navigation.

**F11** [V still open]: Call tree callee names not clickable.
The ▶ re-root works; the name itself has no click. Look in the call tree node
renderer (search for `tr-line` or `call-tree` in console.html).

**F2** [V still open]: Ask LLM response truncates mid-sentence.
LLM_MAX_TOKENS = 400 in llm_client.py — increase to 800 or 1200 for Ask answers.
Check if local_agent.py passes a separate max_tokens to _llm_chat.

**F7** [V still open]: Blast radius includes builtins. Filter in blast_radius tool
in agent_tools.py — skip callers/callees where file_path is None or is a stdlib path.

**F15** [V still open]: Map "to symbol" field focus unreliable. Look at click handler
for the "to" input — may be sharing focus with "from" input.

**F10** [?]: Call tree anonymous fetch callbacks shown as raw code blocks.
**F12** [?]: Call tree no breadcrumb/back after re-rooting.
**F14** [?]: Map graph node click does nothing.
**F16** [?]: Left nav entry point clicks only work in Call tree tab.

---

## WHAT TO DO NEXT SESSION

Start with F17 verification (should be fixed by F18), then F2 (quick token limit bump),
then F3 (Ask link navigation), then F11 (call tree name clicks).

**1. Verify F17** — open Editor tab, click a symbol in the left symbol pane.
If it now works (F18 fix was the root cause), mark done and move on.

**2. Fix F2** — increase Ask answer token limit.
In llm_client.py, `LLM_MAX_TOKENS = 400`. The Ask path in local_agent.py calls
`_llm_chat(messages, timeout=_LLM_TIMEOUT)` with no max_tokens override, so it
uses the default 400. Change to 1200 (or add a separate constant for Ask).

**3. Fix F3** — Ask answer hyperlinks dead.
Find `socket.on("ask_result"` or equivalent in console.html. The response text
has symbol names as hyperlinks (`<a>` or `<span class="ed-sym-link">`). A click
listener must fire `activateTab("editor")` + editor open. Check if the listener
is attached after the response renders or if innerHTML kills it.

**4. Fix F11** — Call tree callee name click.
Search console.html for `tr-line` — that's the callee name row class. Should have
a click handler to open the symbol in Editor. Likely missing or broken.

---

## KNOWN TRAPS (carried forward)

- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- `_pull_type_defs`: two paths — classes table + functions LIKE 'TypeName::%'. [?]
- export_context session in-memory; resets on server restart. Intentional. [?]
- GAP-5 fix: fetch dead-end detection only finds raw callee strings in graph_edges. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]
- Same-name symbol collision in feature_shape (local_symbols keyed by name). [?]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- llama-server: stateless, no need to kill between UI restarts.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
