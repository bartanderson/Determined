Written at commit: 874c6d3

# SESSION STATE — session 230
Written at commit: 874c6d3 (2026-07-21)

## Active branch: main [V]

## What happened this session

**RM67 adversarial probe — Determined corpus [V]**

All 6 canonical questions passed. Two bugs found and fixed:
- blast_radius: 124 edges → 12 unique callers with (×N) dedup. agent_tools.py:195.
- list_entry_points: _short() 2→3 segments; commonplace/routes/api.py now unambiguous.
- tool_registry: find_isolated_modules, find_phantom_factories, find_orphaned_interfaces
  added to REGISTRY. 57/57 test_agent_tools.py pass.
TRACKER updated: Determined adversarial probe DONE.

**detect_conventions (RM70) — calibration run on Determined corpus [V]**

Tool was already implemented (not noted in prior SESSION_STATE). Two calibration fixes:
1. Filter test files from fetch query (NOT LIKE '%/test_%') — prefix:test 850 members gone.
2. Outlier rate cap 40% in _analyse_cluster — prefix:get 84/160 outliers collapses correctly.
Same pattern, two fixes. Family count Determined: 173→83. 57/57 tests pass.
Notable finding: prefix:handle (50 socket handlers) leads; 4 HTML parser outliers correctly
surface as naming coincidences not convention members.

**detect_conventions NOT yet tested on dj2 [V]**

Calibration against dj2 is the next step. Do NOT write tests until dj2 run is done —
behavior may need further adjustment. Tests codify stable behavior; not stable yet.

## Known issues [V = verified, ? = recalled]

**detect_conventions dj2 calibration pending [V]:** Next session starts here.
Run detect_conventions against dj2. Look for new calibration issues. Fix, then write tests.

**find_isolated_modules — test files are noisy [?]:** 67/68 moderate isolations
in dj2 are test files. Future: exclude_tests arg.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

Run detect_conventions against dj2. Use this script as starting point:

  .venv\Scripts\python.exe scratchpad/run_conventions.py

(Script is in session scratchpad — may not persist. If gone, run:)

  from determined.oracle.db_oracle import DBOracle
  from determined.agent.agent_tools import detect_conventions
  oracle = DBOracle(r"C:\Users\bartl\dev\Determined\C_Users_bartl_dev_dj2.db")
  print(detect_conventions(oracle, {"min_family": 3}))
  print(detect_conventions(oracle, {"min_family": 3, "sort": "emerging"}))

Look for: noisy families, wrong outlier judgments, mis-grouped members, anything
that doesn't match your intuition about dj2's conventions. Fix, then write tests.

**After dj2 calibration:** write test_detect_conventions.py. Model on test_structural_gap_tools.py.
See docs/TEST_MAP.md for the pattern.

**RM68** (subrace removal in dj2) — deferred, low priority.
**RM70** (convention detector) — implementation done, calibration in progress.
