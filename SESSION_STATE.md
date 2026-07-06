Written at commit: f879f1c
# SESSION STATE - session 95 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 95, 2026-07-06)

1. Gap 2 (agent_tools.py side) completed. [V]
   - Added `_has_framework_decorator(decorators_json)` helper near line 1023
     (after `_is_entry_point_hint`). Filters any decorator that is not in
     _STRUCTURAL_DECORATORS = {property, staticmethod, classmethod}.
   - `find_orphaned_impls()`: added `f.decorators_json` to SELECT (col index 6),
     post-filters raw rows with `_has_framework_decorator`. Loop unpacks 7-tuple.
   - `detect_topology()`: changed orphaned_impl from COUNT query to row fetch
     (name, file_path, decorators_json), subtracts framework-decorated rows.
   - 436 passed, 1 skipped. [V]
   - Committed as f879f1c. [V]

## Gap 2 status: DONE [V]

UI orphan view: done (3f61ab9). [V]
agent_tools.py (find_orphaned_impls, detect_topology): done (f879f1c). [V]

## NEXT SESSION -- start here

**Gap 1 re-check:** run `check_design_violations` on Commonplace capture/browse.py routes.
These are the Flask route handlers that RM17 flagged as potential layer-import violations.
Now that Gap 2 is done (decorators filter), the orphan noise is gone and violations
should be signal only.

Steps:
1. Start UI server, load Commonplace corpus.
2. Run `check_design_violations` on `capture` and `browse` route symbols in the
   Determined Ask bar (or via agent tool directly).
3. Compare findings against RM17_findings.md Gap 1 description.
4. If violations surface: fix the detection or file as a Determined improvement item.

**After Gap 1:** Gap 3 (_call_llm dead-code distinction), then Gap 4 (capture role fix).

## Test count: 436 passed, 1 skipped [V]
