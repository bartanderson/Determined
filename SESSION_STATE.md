Written at commit: 38a6586
# SESSION STATE - session 98 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 98, 2026-07-06)

RM18 Gap work: acted on three of the four top RM17 findings.

**Gap 1 [V] DONE (2031f90):** Deterministic layer-import violation detection.
- Added `_check_import_layer_violations(conn, file_path)` in agent_tools.py
- Queries `imports` table against CONSTRAINT design_notes (already in DB from ingest_design_docs)
- Extracts forbidden layer prefixes from backtick-quoted paths in constraint text
- `check_design_violations` now shows CONFIRMED violations first, cosine suggestions second
- Tested: routes/capture.py and routes/browse.py both surface confirmed storage violations
- 2 new regression tests

**Gap 3 [V] DONE (1e90d7f):** ready-but-blocked distinction in find_orphaned_impls.
- Non-stub, 0-caller functions in files that also contain stubs → labeled "ready-but-blocked"
- Previously labeled "anticipatory" (indistinguishable from dead code)
- _call_llm in tagger.py now correctly surfaces as ready-but-blocked (suggest_tags is stub)
- 2 new regression tests

**Gap 4 [V] DONE (38a6586):** COORDINATOR/INTERFACER pattern description update.
- COORDINATOR: now explicitly covers use-case orchestrators and HTTP route handlers (4+ callees)
- INTERFACER: narrowed to thin 1-to-1 adapters (1-3 callees), with explicit rule "4+ steps = COORDINATOR"
- _ensure_pattern_library changed from insert-only to upsert (propagates to existing DBs)
- NOTE: actual capture() reclassification [?] -- requires Qwen3-8B live to verify; no 3B model
  exists; spot-check via UI with live server after Commonplace reingest

## Test count: 440 passed, 1 skipped [V] (run at end of session)

## Gaps NOT addressed this session

**Gap 2** was already done in session 95 (decorator filter). [V]

**Gap 10** (design doc auto-discovery on corpus load) -- filed in RM17, not yet acted on.
Commonplace has a DESIGN.md that ingest_design_docs should auto-discover. Currently user
must know to run it manually.

## Commonplace DB state

Commonplace DB (`C_Users_bartl_dev_Determined_examples_commonplace.db`) is STALE:
- Missing `decorators_json` column on functions table (added in Gap 2, session 95)
- design_notes from ingest_design_docs were written this session (27 DESIGN.md rules)
- Needs full reingest via UI to pick up all schema changes

## NEXT SESSION -- start here

1. **Verify Gap 4 (capture role):** Start UI server, load Commonplace corpus (reingest),
   run `infer_behavior` on `capture`. Expect COORDINATOR. If still INTERFACER, LLM is
   not responding to the pattern text changes -- escalate to structural signal in context assembly.

2. **Gap 10 (auto-discovery):** After reingest confirmed working, implement auto-discover
   of DESIGN.md on corpus load. `discover_docs` already exists; wire it to fire on ingest
   completion and surface "found X markdown files -- run ingest_design_docs?" in corpus panel.

3. **RM15 (Commonplace guided journey):** Once Gap 10 is in, the full RM15 arc is unblocked
   (journey works end-to-end with design docs auto-discovered).
