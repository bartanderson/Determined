Written at commit: 3f5cb91

# SESSION STATE — session 293 handoff

## Active branch: main [V]
## Working tree: clean [V]

---

## WHAT HAPPENED THIS SESSION

RM67 probe clean. All 3 cross-language remaining tasks shipped. [V]

---

## DONE THIS SESSION

**RM67 probe** [V]: Clean. 12 Determined stubs (3 real, 9 test), 25 dj2 stubs — all match prior probes. No new issues.

**Cross-language tasks — all 3 DONE** [V]:

`target_lang` in stub_projector: auto-detect from file ext (.py/.c/.cpp/.zig/.lua/.rs/.go/.ts/.js); explicit override via `lang=` arg; language-specific prompt framing + signature format. `lang` field in result dict.

`runtime_locator.py` (new module): `check_snippet(lang, snippet)` → `{ok, error, tool}`. `ok=None` = UNVERIFIED (no tool), not invalid. Python always via `ast.parse`. Others via gcc/zig/luac when on PATH (only rustc present on this machine). `check_projection()` wraps project_stub result. project_stub in agent_tools auto-runs check_projection and shows "Syntax check:" line. 18 tests in test_runtime_locator.py. [V]

`survey_corpus_chain()` + `format_corpus_chain()` in graph_utils: scans all *.db files, detects primary language from file extensions, returns stats per corpus (symbols, stubs, edges, unresolved%, EPs), grouped by family (Systems/Modern/Scripting/Web). Handles old schemas (pre http_route/is_tool). 22 corpora surveyed correctly. Workbench "Cross-Corpus → Corpus chain" tool, oracle-independent. [V]

TRACKER cross-language section updated to all [x]. [V]

---

## REMAINING OPEN ITEMS

**RM-Perf static tier** (next): `find_pure_functions` already covers purity. Two remaining:
1. Stable object layouts — classes where `__init__` attrs never mutated. AST-only, no prereq. ~half session.
2. Dead event handlers — functions registered as callbacks with no callee edges. Needs function-reference edge type in parse_ast.py first.

**RM21** — gated on real multi-hop failure. Don't start.
**RM76** — gated on Bart saying "record this decision." Don't start.
**RM73, RM77** — FUTURE.

---

## WHAT TO DO NEXT SESSION

1. Read TRACKER.md — confirm RM-Perf is next, check for new items.
2. Start RM-Perf static tier with stable object layouts (no prereq). Or ask Bart if different priority.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n` (raw JS code). [V s291]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns — handle gracefully. [V s293]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
