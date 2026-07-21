Written at commit: af0fe58 (2026-07-21)

# SESSION STATE — session 231

## Active branch: main [V]

## What happened this session

**detect_conventions calibration on dj2 [V]**

Ran detect_conventions against dj2. Output: 114 families, no calibration issues.
Key findings:
- prefix:generate (63 members) — canon callees=0 correctly separates AI-wrapper
  functions from orchestrators (generate_encounter, generate_loot, etc.)
- prefix:is (30 members) — canon param_count=0 correctly IDs property-style predicates
  vs parameterized checks
- prefix:semantic (10 members) — 2 stubs (semantic_match_subrace,
  semantic_match_fighting_style) surface as body_weight outliers. Direct RM68 relevance.
- prefix:test (5 members) — Flask web endpoints in world_app.py, not pytest functions.
  No noise issue (dj2 has no test_*.py files in scope).
No calibration fixes required. Tool behavior is correct on dj2.

**test_detect_conventions.py written [V]**

22 tests. Covers all three gates, outlier detection (param divergence, stub tagging,
>40% suppression), scope, sort modes, test-file exclusion, dunder exclusion,
suffix detection, prefix-over-suffix precedence. All 22 pass.
TEST_MAP.md updated: test_detect_conventions.py added to agent_tools.py row.

## Known issues [V = verified, ? = recalled]

**find_isolated_modules — test files are noisy [?]:** 67/68 moderate isolations
in dj2 are test files. Future: exclude_tests arg.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

RM70 (detect_conventions) is complete: implemented, calibrated on both corpora, tested.

Step 1: mark RM70 done in TRACKER.md.
Step 2: check TRACKER.md for next open item. RM59 (feature shape analysis) is listed
as active. RM68 (subrace removal in dj2) is deferred low priority.

Verify: `.venv\Scripts\pytest tests/regression/test_detect_conventions.py` — should be 22 pass.
