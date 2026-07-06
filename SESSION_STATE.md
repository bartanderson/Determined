Written at commit: 437679f
# SESSION STATE - session 94 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 94, 2026-07-06)

1. Session start checklist completed. Drift check: handoff SHA d482f27, HEAD 437679f.
   One commit of drift (session 93 wrap only, no .py changes). [V]

2. Gap 2 investigation: [V]
   - decorator capture (decorators_json column) and UI-side orphan filter ALREADY shipped
     in commit 3f61ab9 (RM18 session prior).
   - find_orphaned_impls() and detect_topology() in agent_tools.py do NOT use
     decorators_json yet -- they still report Flask route handlers as orphans.
   - Started adding _has_framework_decorator() helper to agent_tools.py, but wrap
     signal came before wiring the two callers. Reverted partial change -- left repo clean.

3. No .py files committed this session. [V]

## Gap 2 status (PARTIAL -- not done)

UI orphan view: done (3f61ab9). [V]
agent_tools.py (find_orphaned_impls, detect_topology): NOT done. [V]

## NEXT SESSION -- start here

**Gap 2 completion (agent_tools.py side):**

Add to agent_tools.py near _is_entry_point_hint (~line 1021):

```python
_STRUCTURAL_DECORATORS = {"property", "staticmethod", "classmethod"}

def _has_framework_decorator(decorators_json):
    if not decorators_json:
        return False
    import json as _json
    try:
        decs = _json.loads(decorators_json)
    except Exception:
        return False
    return any(d.split("(")[0].split(".")[-1] not in _STRUCTURAL_DECORATORS for d in decs)
```

Then:
- find_orphaned_impls(): add `f.decorators_json` to SELECT, post-filter rows with
  `if not _has_framework_decorator(row[decorators_idx])`.
- detect_topology(): orphaned_impl COUNT query can't easily be post-filtered in SQL.
  Change to fetch rows (name, file_path, decorators_json), subtract framework-decorated.

**After Gap 2:** Gap 1 re-check (check_design_violations on capture/browse.py routes),
then Gap 3 (_call_llm dead-code distinction), then Gap 4 (capture role fix).

## Test count: 436 passed, 1 skipped [V - verified this session end run]
