Written at commit: da5a1cb

# SESSION STATE — session 217
Written at commit: da5a1cb (2026-07-19)

## Active branch: main [V]

## What happened this session

**UI redesign arc — working through docs/UI_EVAL.md fixes [V]**

Session picked up after session 216 FOREWARNING/parse_ast work. CLOSURE.md was
fully checked off (Phases 1–3 done as of 2026-07-18). This session did the
UI fix pass against the six canonical probe questions.

**Fixes shipped (all [V] — in commits):**

| Fix | Commit | What |
|-----|--------|------|
| A1 | 189096b | "Show all EPs" link below Roots → opens frontier filtered to EPs |
| B1 | 189096b | Renamed blast radius shortcut label ("Blast radius — who calls this...") |
| C1 | 189096b | Feature areas block in Navigate sidebar — list_features on corpus load |
| E1 | 189096b | Design mode violations → inline symbol form (not bare chat submit) |
| F1 | 189096b | Path-from-to input pair in Graph tab toolbar (graph_path src/dst) |
| D1 | ded2e14 | Stub classification label inline in frontier rows (from corpus_shape data) |
| E2 | ded2e14 | Design mode hint when design_note_count == 0 |
| G2 | ded2e14 | Global symbol search (⌘K style) → opens Spotlight directly |
| A2 | da5a1cb | EP type badges: 🌐 HTTP route vs ⚙ inferred (via decorators_json check) |
| B2 | da5a1cb | Risk badge color on caller rows in blast radius result |

A2 required a backend change: ui_server.py now checks decorators_json for
@app.route / @socketio.on to classify ep_type. Client renders 🌐/⚙ prefix.
Verified: dj2 top EPs all show ⚙ (inferred), correct — Flask routes need high
fan-out to rank in top 8 and dj2's are correct.

**Session was cut before SESSION_STATE was written** — this file reconstructed
from git log + UI_EVAL.md + context from Bart.

## Tests [V = verified, ? = recalled]

- UI changes only — no Python engine changes this session.
- 91 parse_ast regression tests still passing [?] (not re-run, engine unchanged).
- Full suite not run [?].

## Known issues [V = verified, ? = recalled]

**Convergence probe not yet run [?]:** SESSION_STATE 216 flagged this as CRITICAL.
The probe script was at a session-specific scratchpad path that is now stale:
`C:\Users\bartl\AppData\Local\Temp\claude\C--Users-bartl-dev-Determined\bc35bcad...\scratchpad\probe_dj2.py`
That path likely does not exist in a new session. Re-derive the probe or check
CLOSURE.md Phase 2 dj2 section (lines 133-154) to re-run manually.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs (Class.method); tool queries bare names → chain length 0/1. Workaround: use
graph_path. Not fixed (separate RM item).

**classify_stub file_path_hint [?]:** path matching fails for TS corpora when
file_path given. Workaround: omit file_path, rely on name-only lookup.

**list_stubs test fixtures [?]:** test stubs surface in stub list. Filed in
CLOSURE.md Phase 2 Determined findings. Not yet fixed.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`. Never use pyenv/system Python.

## NEXT SESSION — start here

**Remaining UI_EVAL.md items:**

| Fix | What | Size |
|-----|------|------|
| A3 | Module filter chips above Roots section | Medium |
| B3 | Extended blast radius expandable (N symbols list) | Medium |
| G1 | Promote Workbench to primary tab bar + full tool forms | Large |

G3 (corpus switch loses context — session snapshot) and G4 (tool transparency)
and L1-L4 (cloud model routing) are deferred/architectural — do not start these
until A3/B3/G1 are done or explicitly deprioritized.

**After UI_EVAL.md is done:** Step back and assess the GOT model completeness
question from UI_VISION.md — do surfaces self-present on corpus load without
any user action? That is the redesign gate criterion.

**UI_EVAL.md is the work driver.** Read it at session start instead of CLOSURE.md
(CLOSURE.md is fully checked off).

**Server start (standing note):** always use `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`. Never use pyenv/system Python.
