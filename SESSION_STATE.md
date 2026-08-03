Written at commit: 79d0abc

# SESSION STATE — session 289 handoff

## Active branch: main [V]
## Working tree: clean, no commits this session [V]

---

## WHAT HAPPENED THIS SESSION

**Exploratory UI testing against dj2 corpus** [V]
Goal: exercise the full Workbench UI as if doing real dj2 work,
document all friction/missing/broken behavior before fixing anything.
Server was live at localhost:5050 throughout.

No code was written or committed this session.

---

## EXPLORATORY FINDINGS (18 items)

### CRITICAL — blocks navigation

**F18** [V]: Frontier canvas has no `pointer-events: none` when its tab is not active.
The canvas overlays the *entire* tab bar and content area of adjacent tabs.
All tab clicks and Editor symbol clicks register on the hidden canvas instead.
`document.elementFromPoint` returns `CANVAS#` at tab bar coordinates while on Frontier.
Fix: add `pointer-events: none` to the Frontier canvas when tab is inactive,
or ensure the tab hide path uses `display:none` rather than `visibility:hidden`/opacity.

### HIGH — broken features

**F17** [V]: Editor left symbol list unreachable via mouse (root cause: F18).
Click at (196,188) screen-coords hits Frontier canvas at viewport (451,433).

**F3** [V]: Hyperlinked function names in Ask answers are dead (no Editor navigation).

**F1** [V]: Largest-files card file names are not clickable.

**F11** [V]: Call tree callee names not clickable (no re-root, no Editor navigation).

### MEDIUM — wrong behavior or missing output

**F13** [V]: Resolver pattern miss for `find_hot_callers`.
Pattern `most\s+called` disallows trailing nouns: "most called functions" fails.
"which functions are called most frequently" fails (different word order).
Pipeline trace confirmed: `decompose → llm` → "The facts do not specify."

**F4** [V]: Resolver pattern miss for `find_fetch_calls`.
Pattern requires exact `javascript\s+http\s+calls?` — misses "JS functions make HTTP calls".

**F6** [V]: Workbench output area (`#wb-output-wrap`) sits ~2000px below tool cards.
User runs a tool and sees nothing. Only `scrollIntoView` via JS reveals output.

**F5** [V]: Qwen3 chain-of-thought leaks raw reasoning text into Ask answers.
Visible: "the rule says: 'If the facts say No direct callers found', say so…"

**F2** [V]: Ask LLM response truncates mid-sentence with no visible indicator.

**F7** [V]: Blast radius extended impact includes builtins (Flask, SocketIO, forEach,
catch, str, print). 69 symbols shown; most are noise.

**F15** [V]: Map "to symbol" field doesn't reliably receive focus when clicked.
Both type sequences went into "from symbol". Path-finding itself works once fields set.

### LOW — friction, not broken

**F9** [V]: 5 tools missing from Workbench: `find_large_files`, `find_fetch_calls`,
`find_cross_language_calls`, `find_pure_functions`, `find_hot_callers`.
Tool registry entries already exist; just no card rendered in the HTML.

**F8** [V]: No PERFORMANCE or ARCHITECTURE sections in Workbench for new tools.

**F10** [V]: Call tree shows anonymous fetch callbacks as raw multi-line code blocks.

**F12** [V]: Call tree has no breadcrumb/back after re-rooting on a callee.

**F14** [V]: Map graph nodes have no hover tooltip and no click behavior.
Symbol search + Map button works; node click alone does nothing.

**F16** [V]: Left nav entry point clicks only work in Call tree tab; no-op elsewhere.

---

## WHAT WORKS WELL (confirmed this session)

- Map: symbol highlight search; from→to path finder (2-hop confirmed) [V]
- Map Imports: file-level import graph, hierarchical, 123 files · 261 edges [V]
- Map Topology: text breakdown — stub counts, orphaned-impl (941), ABC gaps (39) [V]
- Call tree: named callee display; ▶ re-roots; left nav loads tree [V]
- Editor: Open ↵ opens files by path; syntax highlighting; read-only [V]
- Knowledge: Artifacts/Pins/Bag/Doc health filters; design notes display [V]
- Workbench: blast_radius, classify_stub, walk_call_chain, feature_shape run correctly [V]
- Ask: routing works for file_size_analysis (pattern hit confirmed via pipeline trace) [V]

---

## WHAT TO DO NEXT SESSION

Fix in priority order — F18 first (unblocks F17 and restores all tab nav).

**1. Fix F18 — Frontier canvas pointer-events (start here)**
Find the canvas in the Frontier tab template/JS.
When Frontier tab is inactive: `canvas.style.pointerEvents = 'none'`
or hide with `display:none` not just opacity/visibility.
Verify: `document.elementFromPoint` at tab bar coords returns tab button, not canvas.

**2. Fix F6 — Workbench output scroll**
After any Run button fires, scroll `#wb-output-wrap` into view.
Or render output inline just below the triggering tool card.

**3. Fix F9/F8 — Add 5 missing tools to Workbench**
Add PERFORMANCE and ARCHITECTURE sections to Workbench HTML.
Render cards for: find_large_files, find_fetch_calls, find_cross_language_calls,
find_pure_functions, find_hot_callers. Tool registry entries already exist.

**4. Fix F13/F4 — Broaden resolver patterns**
find_hot_callers: allow trailing `\s+functions?` and "called most frequently" phrasing.
find_fetch_calls: allow "JS functions.*HTTP" / "javascript.*fetch" variations.
find_pure_functions: allow "functions with no side effects", "stateless functions".
Test with `socket.emit('query', {q: '...'})` in browser console.

**5. Fix F5 — suppress Qwen3 chain-of-thought**
Find LLM call for Ask answers (local_agent.py or pattern_executor.py).
Add `/no_think` token or `thinking: false` param to suppress raw reasoning output.

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
