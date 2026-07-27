Written at commit: 7954807

# SESSION STATE — session 262 (end)

## Active branch: main [V]

## This session (committed) [V]

- `7954807` — docs: tiered reasoning ladder + RM71 export_context [V]

(Session 261 commits carried forward for reference:)
- `bf907be` — docs: RM70 design + session 261 handoff prep
- `2f25408` — feat(sketch_stub): solution candidate generator for classified stubs
- `b2159b6` — fix(classify_stub): config-layer stubs and test file calibration
- `61d9c44` — fix(ui): guide completion stuck + sidebar label affordance

---

## WHAT HAPPENED THIS SESSION

**RM70 architectural reframe — tiered reasoning ladder** [V]

Core insight (Bart's): the local LLM was never the point. Determined is the
corpus intelligence layer. A capable external LLM is the reasoning layer. The
missing piece was the bridge — and the complexity gate that decides when to
use it.

Three tiers:
1. Local LLM (Qwen3-8B) — always tried first. Most stubs, most questions.
2. Web LLM (Deepseek, ChatGPT) — when complexity signal exceeds local ceiling.
   Context packet + tool manifest; interactive not one-shot.
3. Claude — architectural arbitration; packet includes prior reasoning chain.

Complexity signal computed from corpus facts before invoking any LLM:
caller body size, referenced type count, pattern sibling availability,
classify_stub confidence, unresolved edge ratio. Composite → threshold.

**RM71 — export_context (new, DESIGN DONE)** [V]

The escalation mechanism. Clipboard-ready packet:
- Section 1: function + corpus signals + classify_stub verdict
- Section 2: neighbor context (caller bodies, callees, siblings)
- Section 3: complexity score + which signals drove escalation
- Section 4: tool API manifest (what Determined can answer if asked)

Also useful standalone — human reviewer paste-in even when local LLM succeeds.

Connection to RM21 Technique 6 (large-model fallback, tools.old/bridge/):
that was always the placeholder for this. Complexity gate is the missing spec.

Full design: `docs/RM70_DESIGN.md` (Tiered reasoning ladder section).
TRACKER: RM71 block added between RM70 and RM72.

---

## WHAT TO DO NEXT SESSION

1. **RM67 probe** — run at session start (standing rule).

2. **RM70 Step 1 — V1+V2 verification baseline**
   Add `_verify_candidate(code, oracle)` to `determined/agent/sketch_stub.py`:
   - V1: `ast.parse(code)` — hard gate
   - V2: walk AST for `Name`/`Attribute` nodes, query `functions` table;
     return fraction that resolve
   Run against all 25 dj2 stubs. Record baseline V2 scores.
   This is the yardstick for all RM70 retrieval improvements.

3. **RM70 Step 2 — Caller body reader**
   In `_caller_context()`: replace docstring pull with `_read_function_body()`.
   Re-run V2 scores; measure improvement.

4. **RM70 Step 3 — Pattern sibling search (corpus-scoped)**
   Replace `_style_siblings()` (file-scoped) with `_pattern_siblings()`:
   - Strip common prefixes, Levenshtein on remainder, corpus-wide query
   - Verify: `_get_encounter_context` → `_get_combat_context` as top match

5. **RM71 build** (after RM70 Step 1 baseline exists)
   `export_context(symbol)` tool in `determined/agent/export_context.py`.
   Complexity signal calibration requires real V2 scores to set threshold.
   Register in TOOLS, workbench, tool_registry, FILE_MAP.

---

## RESOURCE / PROCESS RULES [V]

- Pre-flight: `Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force`
- Duplicate server trap: `netstat -ano | Select-String ":5050"` — two LISTENING = old process alive
- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- Tour tab is under ⚙ Utilities dropdown — not directly visible in tab bar.
- Extended corpus DB: `C_Users_bartl_dev_Determined_examples_commonplace_extended.db`

## Known issues (carried)

- CUDA stubs: dim3 vars [?] — accepted ceiling
- C++ pure virtual not captured [?] — deferred to RM73
- Walker dispatch resolution (RM73) [?] — FUTURE
- `_extract_body()` unusual body patterns (nested defs, decorators) not validated [?]
- sketch_stub LLM quality: current brief → placeholder-level code; RM70 retrieval is the fix
- RM71 complexity threshold: uncalibrated until V2 baseline scores exist [?]
