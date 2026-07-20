Written at commit: 6e75f76

# SESSION STATE — session 226
Written at commit: 6e75f76 (2026-07-20)

## Active branch: main [V]

## What happened this session

**detect_conventions calibration — design decision made [V]**

Swept min_family 3→15. Conclusion: min_family=3 is correct and stays as default.
The "<20 families" target from prior session was a display convenience, not a signal
quality threshold. Three co-occurrences = non-coincidental pattern. For incomplete
code, small families are MORE informative — they are emerging conventions, and stubs
diverging from them are stranded mid-pattern. Raising the floor loses exactly the
signal classify_stub needs.

**detect_conventions gains sort param [V]**

Two modes:
- `established` (default): largest families first — dominant patterns, corpus topology view
- `emerging`: smallest families first — nascent conventions, stub analysis view

Sort by member count. Output header shows active sort mode.
11/11 tests passing. Committed 27580dc.

**Signal fusion + multi-modal visual projection — TRACKER item added [V]**

FUTURE design review item written covering:
- Per-concept signal aggregation across all tools (naming family + call graph +
  FSM + knowledge artifacts + classify_stub confidence)
- Visual projection paradigms: Venn overlap, layered drill-through tables,
  color encoding, thread-pulling workspace, adjacency/convergence maps
- Time-axis trajectory: accelerating family growth = momentum that stopped =
  stub priority signal stronger than raw size
Gate: needs calibration stable + one more per-concept tool before designing.

**Cap'n Hook — per-session economics tracking [V]**

Three commits (c9b9036, 6e75f76):
- log.jsonl: append-only log of every ask (query text, hit/miss, tokens), chart,
  session_start. Persists across sessions for pattern analysis.
- Session IDs: context generates UUID, all subsequent asks/charts tagged to it.
- tokens_wasted: misses estimated at max(mean_saved_per_hit, 300 floor).
  Dynamic — self-calibrates as hit history grows. Economics not physics.
- report command: per-session hits/misses/saved/wasted, missed query text listed.
  `--sessions N` controls window (default 10).
- session_count in stats.json, incremented each context call.
- Report-due notice fires at session 5 (first), then every 10 (15, 25, ...).
  Appears at end of context output — surfaces in session checklist, doesn't block.
- session_count currently at 1. Report due at session 5.

## Known issues [V = verified, ? = recalled]

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as FQNs;
tool queries bare names. Workaround: use graph_path.

**Prose false positives in shape scanner [?]:** .recall/history.md and SESSION_STATE.md
detected as directed_graph from -> arrows in prose. Normalizer errors on these.
Acceptable for now.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**Thread convention outlier score into rank_stubs (optional but natural next step).**
detect_conventions emerging sort surfaces stubs diverging from small families.
Wire that signal into rank_stubs priority mode composite score.
Currently: caller_count * confidence + chain_bonus.
Add: outlier_bonus if stub appears as outlier in a naming family.

**Run capn report after a few sessions accumulate.**
Session counter is at 1. Notice fires automatically at session 5.
When it fires: `python scripts/capn.py report` — look at repeated miss queries
as highest-value charting candidates.

**RM69 open design questions (from TRACKER, low urgency):**
- Hypothesis count cap (3? all above threshold?)
- Prerequisite map: match named concepts across blocked-on comments
- Ranking formula calibration needs more real cases
