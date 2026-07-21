Written at commit: 959c343 (2026-07-21)

# SESSION STATE — session 233

## Active branch: main [V]

## What happened this session

**Signal fusion — per-stub, spotlight panel [V]**

Designed and shipped the first fusion layer: per-stub signal aggregation in the
spotlight panel. Two commits:

**f934815 — RM-FUSION-1: convention + chain + outlier signals**

- New `_get_convention_for_symbol(conn, name)` in agent_tools.py.
  Runs the full 3-gate cluster analysis; returns `{family, family_size, is_outlier}`
  for the queried symbol. Same logic as `_compute_outlier_stub_set` but richer output.
- Socket handler `handle_classify_stub_spotlight` extended: imports
  `_get_chain_positions`, `_compute_outlier_stub_set`, `_get_convention_for_symbol`;
  emits `fusion` field with convention_family, convention_size, convention_is_outlier,
  chain_position, chain_bonus, outlier_bonus.
- Frontend: SIGNAL CONVERGENCE table renders below hypothesis chips when any fusion
  signal present. Convention row shows family + size + "⚠ outlier" in orange.
  Chain position row shows +N priority. Outlier bonus row.
- 5 new tests in test_detect_conventions.py (27 total).

**959c343 — knowledge artifact signals**

- New `_get_artifact_signals(conn, name)` in agent_tools.py. Three DB queries:
  dead markers (`kind='dead' AND subject LIKE '%{name}'`),
  inline notes (`kind='inline_note' AND subject=name`),
  design note coverage (`kind='design_note' AND content LIKE '%{name}%'`).
- Fusion payload gains: artifact_dead, artifact_inline_notes, artifact_design_note.
- Frontend: dead row (blue, "corpus flagged as dead code — supports concept-not-applicable"),
  design note row (green), inline notes count.
- 8 new tests in test_agent_tools.py.

**Verified live on dj2::process_consequences [V]:**
- fusion: convention_family=prefix:process (11 members), convention_is_outlier=true,
  outlier_bonus=3, artifact_dead=true, artifact_inline_notes=2
- All four rows render in spotlight DOM (SIGNAL CONVERGENCE, dead, inline, outlier)
- 132 tests pass across classify_stub + detect_conventions + agent_tools suites

## Known issues [V = verified, ? = recalled]

**dead artifact LIKE over-match [V]:** `WHERE subject LIKE '%{name}'` over-matches
when name is a suffix of another symbol. Real subjects are `dead::symbol_name`
so over-match is rare in practice. Documented in test, not fixed.

**load_db auto-orient blocks screenshot [V]:** background LLM thread fires on
corpus load; 10s timeout causes screenshot tool to hang. Workaround: DOM reads
via javascript_tool. classify_stub_spotlight is pure DB and unaffected.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Server start command [V]:** `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

Run: `git log --oneline -5` first.

**Continue signal fusion.** Next signal candidates from TRACKER (FUTURE — Untapped
classify_stub signals):

1. **return_type existence check** (moderate value) — for stubs returning a named
   type (not dict/None/primitives), check whether that type exists as a class.
   `List['Race']` with no Race class = concept-not-applicable signal.
   Already in signals dict as return_type — just needs a scoring rule and fusion wire.
   Add to `_get_artifact_signals` or a new `_get_return_type_signal(conn, name)`.
   Query: check `classes` table for the return type name.

2. **imports table check** (highest value per TRACKER) — if the stub's docstring
   mentions CombatFSM but no file imports CombatFSM, strong concept-not-applicable.
   Query: `SELECT * FROM imports WHERE name LIKE '%{base}%'`.

3. **Visual projection surface** — after 2-3 more signals are wired, the TRACKER
   FUTURE section calls for designing the visual projection: layered table with
   drill-through, Venn/overlap concepts, thread-pulling workspace. Design review
   before coding per TRACKER guidance.

The fusion field shape is stable (`fusion` dict in classify_stub_spotlight_result).
New signals are additive — add to `_get_artifact_signals` or a peer helper,
wire into the handler, add a row to the convergence table.
