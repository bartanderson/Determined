Written at commit: 8621717

# SESSION STATE — session 230
Written at commit: 8621717 (2026-07-21)

## Active branch: main [V]

## What happened this session

**RM67 adversarial probe — Determined corpus [V]**

Ran all 6 canonical questions against C_Users_bartl_dev_Determined.db.
All passed. Two bugs found and fixed in the same session.

Q1 Entry points: PASS with finding — HTTP routes were Commonplace example routes
  (examples/commonplace/), not Determined-native routes. Path display showed
  only 2 segments so source was ambiguous. Fixed.
Q2 Blast radius: PASS with finding — ground_question listed 25× (one edge per
  call-site). Fixed with dedup.
Q3 Feature shape: PASS — determined/agent: 329 syms, 1 stub, 39% completeness.
Q4 Stubs: PASS — 3 stubs, 0 false positives. Both __init__ stubs (pattern_executor,
  contract_drift_classifier) surface correctly after session 229 fix.
Q5 Design drift: PASS (not testable — no layer rules defined, no confabulation).
Q6 Call chains: PASS — main→cmd_ask→run_question correct; walk_call_chain(dispatch)
  returns 160-node breadth-first expansion of all tool handlers.

**blast_radius dedup fix [V]**

_list_callers_raw returns one row per call-site. blast_radius was listing the same
caller N times. Fixed: group by caller name in blast_radius(), display as
`ground_question (×25)`. 124 edges → 12 unique callers. agent_tools.py:195.

**list_entry_points HTTP route path depth fix [V]**

_short(fp) used last 2 segments → `routes/api.py` (ambiguous). Bumped to 3 segments
→ `commonplace/routes/api.py` (clear). Local function inside list_entry_points.
agent_tools.py:9625.

**tool_registry gap fixed [V]**

find_isolated_modules, find_phantom_factories, find_orphaned_interfaces were in TOOLS
but missing from REGISTRY. test_tool_registry_covers_all_tools was failing.
Added full registry entries to tool_registry.py. 57/57 tests pass.

**TRACKER: stub-targeted editing FUTURE item added [V]**

Monaco at the projection site — editing surfaces at the stub when classify_stub
produces a solution candidate. Not a general editor. Deferred until solution
generation exists.

**57/57 test_agent_tools.py pass [V]**

## Known issues [V = verified, ? = recalled]

**find_isolated_modules — test files are noisy [V]:** 67/68 moderate isolations
in dj2 are test files. Correct signal but visually noisy. Future: test-path
suppression tier or `exclude_tests` arg.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Prose false positives in shape scanner [?]:** SESSION_STATE.md and history.md
detected as directed_graph from -> arrows. Normalizer errors on these. Acceptable.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**RM67 adversarial probe is complete. All convergence probes done across all corpora.**

Update TRACKER RM67 convergence status to reflect this session's adversarial probe
result before doing anything else (not done yet — only in-session notes above).

**Remaining open items in TRACKER:**

RM70 convention detector — DESIGN phase. No implementation started. Next feature arc.
Read RM70 in TRACKER before designing anything.

RM68 subrace removal in dj2 — deferred, low priority.

**Run capn report when session count reaches 5.**
Counter resets after report. Next auto-notice at session 14.
