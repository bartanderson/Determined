Written at commit: 3dad538

# SESSION STATE — session 263 (end)

## Active branch: main [V]

## This session (committed) [V]

- `56d05b5` — feat(sketch_stub): V1+V2 verification baseline (RM70 Step 1) [V]
- `db2e515` — feat(sketch_stub): caller body reader (RM70 Step 2) [V]
- `3dad538` — feat(sketch_stub): pattern sibling search (RM70 Step 3) [V]

---

## WHAT HAPPENED THIS SESSION

**RM67 probe — dj2 (2026-07-27)** [V]
25 stubs, stable. 12 FSM config / 5 subrace dead concept / 3 test mocks / 5 real gaps.
No regression. Probe done.

**Architecture discussion — tiered reasoning ladder clarified** [V]
- Local LLM is default, not fallback. External path is overflow only.
- Complexity gate decides tier; not preference.
- export_context packet is the bridge (RM71).
- `_get_encounter_context` is first-of-its-kind — no implemented corpus sibling exists.
  Pattern sibling search correctly returns empty and falls back for this stub.

**Design principle stated by Bart:** tests verify mechanisms, not specific data outcomes.
Encoding expected match names into tests is wrong. Calibration (threshold tuning from
observed patterns) is legitimately data-driven. These are different things.

**RM70 Step 1 — V1+V2 verification baseline** [V]
Added `_verify_candidate(code, oracle)` to sketch_stub.py.
- V1: ast.parse() — hard gate
- V2: corpus call check, builtins excluded, composite = V2 * 0.6

Baseline (dj2, 11 stubs scored):
  V1 pass: 4/11 (36%) | avg V2: 0.36 | avg composite: 0.22
  Dominant failure: syntax errors (V1), not corpus alignment.
  All 5 real world/ gaps either V1-fail or produce no candidate.

**RM70 Step 2 — Caller body reader** [V]
`_caller_context()` now fetches full source body (cap 20 lines) instead of docstring.
Bug found and fixed: showing caller bodies as `def` blocks caused completion model to
fill the CALLER instead of the target stub. Fixed by showing as commented lines (#   line).
FSM stubs have no Python callers → no effect on them; their variance is pure LLM noise.
Single-sample measurement too noisy to confirm improvement — `_register_world_tools`
improved (V1-FAIL → V1-PASS), others within noise floor.

**RM70 Step 3 — Pattern sibling search (corpus-wide)** [V]
Replaced file-scoped `_style_siblings()` with corpus-wide `_pattern_siblings()`.
- `_normalize_name()`: strips `_` prefix + verb prefix (_get_, _build_, etc.)
- Dunder bug: `lstrip("_")` on `__init__` → `init__`. Fixed: detect `__` prefix first.
- `_PATTERN_FLOOR = 0.4` — below this, not a real pattern match
- `is_stub=0` invariant — stubs have nothing to show, never returned as siblings
- Falls back to `_style_siblings()` when nothing exceeds floor
- `_style_siblings()` kept as the fallback implementation

Sample matches verified sensible (mechanism check, not outcome assertion):
  get_player_by_session → _get_player_id_for_session (sim=0.79)
  process_consequences → create_consequence_system (sim=0.80)

105 tests pass after each step.

---

## WHAT TO DO NEXT SESSION

1. **RM67 probe** — run at session start (standing rule).

2. **RM70 Step 4 — Return-shape inference**
   AST walk on caller bodies to infer what shape the stub must return.
   Look for subscript access (`result["key"]`), attribute access (`result.state`),
   unpacking patterns. Three confidence levels: STRONG / WEAK / NONE.
   STRONG: direct subscript or attribute access found in caller body.
   WEAK: result passed to another function (keys unknown) — show as "(uncertain)".
   NONE: pattern not parseable — omit from brief.
   Add to `build_brief()` return dict; include in prompt as comment before target def.
   File: `determined/agent/sketch_stub.py`, new `_infer_return_shape(callers)` function.

3. **RM70 Step 5 — Type definition pull** (after Step 4)
   For named classes in signature/docstring that resolve in DB:
   pull `__init__` signature + public non-stub methods as available APIs.

4. **RM71 — export_context tool** (can start after Step 1 baseline)
   `determined/agent/export_context.py` — clipboard-ready context packet.
   Complexity signal calibration: use V2 baseline scores to set threshold.
   Register in TOOLS, workbench, tool_registry, FILE_MAP.

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Tour tab is under ⚙ Utilities dropdown — not directly visible in tab bar.
- Extended corpus DB: `C_Users_bartl_dev_Determined_examples_commonplace_extended.db`
- LLM sweep script: scratchpad/run_baseline.py — starts/stops llama-server, scores all 25 stubs

## Known issues (carried)

- CUDA stubs: dim3 vars [?] — accepted ceiling
- C++ pure virtual not captured [?] — deferred to RM73
- Walker dispatch resolution (RM73) [?] — FUTURE
- LLM sweep variance: single-sample per stub too noisy; multi-sample needed for fine measurement [?]
- RM71 complexity threshold: uncalibrated [?]
