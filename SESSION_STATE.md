Written at commit: 81decfb (2026-07-22)

# SESSION STATE — session 235

## Active branch: main [V]

## What happened this session

**Visual projection — all three phases shipped** (session 235):
- Phase 1 (1972baa): row click → spotlight + graph pre-loaded in Map tab (background,
  no forced tab switch). Added `data-family` attribute to `.fusion-row` elements.
- Phase 2+3 (81decfb): family grouping with clickable header rows (filter/clear),
  convergence summary line above table ("Signals: 7/10 outlier · 5 dead artifact").
  All frontend-only — no backend changes, no new socket events.
- Verified in browser via DOM checks (screenshot blocked by known load_db LLM thread
  constraint): 5 family headers, 10 rows, convergence visible, filter/clear cycle correct.

All changes in `determined/ui/templates/console.html` only. [V]

## Signal fusion + visual projection state [V]

All signals wired and projected:
- Convention (family, size, is_outlier)
- Chain (position, bonus)
- Artifact (dead, inline_notes, design_note)
- return_type existence check
- Import concept cross-check
- Breadth view: signal table with family grouping, convergence summary, graph pre-load
- Depth view: spotlight SIGNAL CONVERGENCE table

`docs/VISUAL_PROJECTION.md` — spec fully implemented. No remaining phases.

## NEXT SESSION — start here

Visual projection is done. Check TRACKER.md for the next open item.

The active item in CLAUDE.md is **RM59** (feature shape analysis — `list_features`,
`feature_shape`, `development_priorities`). Check TRACKER.md RM59 for current phase
status before starting.

First command:
```
python scripts/capn.py ask "what have we already implemented for RM59 feature shape tools"
```
Then read TRACKER.md RM59 block.

## Known issues [V = verified, ? = recalled]

**dead artifact LIKE over-match [V]:** `WHERE kind='dead' AND subject LIKE '%{name}'`
over-matches when name is a suffix of another symbol. Documented in test. Fix if noisy.

**load_db auto-orient blocks screenshot [V]:** background LLM thread on corpus load
causes screenshot tool to hang. Workaround: DOM reads via javascript_tool.

**Corpus switch UI flow [V]:** `socket.emit("load_db", {path: "..."})` is the direct
load path. "Switch corpus" button (resumeBtn) is only visible when a corpus is already
loaded; it emits `list_dbs` which returns a picker modal. To load from a fresh server
start: emit load_db directly with the absolute .db path.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.
