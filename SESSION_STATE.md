Written at commit: 6380448

# SESSION STATE — session 205
_Overwrite completely each session. Not authoritative — see docs/TRACKER.md and docs/CLOSURE.md for truth._

## Active branch: main [V]

## What happened this session (2026-07-18)

**Phase 2: ALL corpora convergence probes -- complete [V]**
All 8 corpora probed. All 6 canonical questions answered for each.
See CLOSURE.md for full per-corpus results.

**Corpora probed this session [V]:**
  rotjs -- Q1-Q5 PASS, Q6 graph_path PASS / walk_call_chain FAIL (TS FQN).
  dungeoncrawler -- Q1-Q4 PASS, Q5 BUG FOUND/FIXED, Q6 PASS.
  dnd-dungeon-gen -- Q1-Q6 PASS (re-ingest not needed, RM62 fix already applied).
  end-of-eden -- Q1-Q6 PASS. Clean Go corpus.
  ruggrogue -- Q1-Q6 PASS. 0 stubs.

**Bug found and fixed: evaluator.py param_names (Bug E) [V]**
  TS ingestion stores param_types_json as [{name,type}] dicts.
  evaluator.py:341 joined them as strings -> TypeError crash in check_design_violations.
  Fixed: extract "name" key from dict params.
  1144 pass, 1 skip (confirmed post-fix). [V]

**Known patterns (not fixed) [V]:**
  walk_call_chain broken for TS/JS FQN callers -- returns chain len 0 or 1.
    Use graph_path instead for TS/JS chain queries.
  classify_stub file_path_hint fails for TS corpora -- omit file_path, name-only works.
  graph_path FQN inconsistency for JS module.method -- some pairs find path, others don't.
  Rust ::new display: all constructors resolve to "new" -- ambiguous display, not a bug.

## NEXT SESSION -- start here

**Phase 2 is fully complete [V]**
CLOSURE.md Phase 2 section: all corpora probed, all checkboxes filled.

**Next: Phase 3 -- Housekeeping before UI redesign**
  Three items in CLOSURE.md Phase 3:
  1. RM68 -- Remove subrace concept from dj2 (blast_radius first, then remove 5 stubs)
  2. Regex-for-semantic-meaning audit (determined/agent/, oracle/, assessor/, ingestion/)
  3. Commonplace guided journey -- walk the journey with current tool, update stale steps

  Pick up RM68 first: blast_radius on subrace stubs, then remove from dnd_data.py etc.
  dj2 is at C:\Users\bartl\dev\dj2

## Known issues (carried forward)

**arg name asymmetry [V]:** blast_radius=`target`; graph_path=`src`/`dst`; classify_stub=`symbol`.
**classify_stub file_path_hint [V]:** fails for TS; workaround: omit file_path.
**walk_call_chain TS/JS [V]:** chain length 0/1 due to FQN callers; use graph_path.
**graph_path JS FQN [V]:** inconsistent for JS module.method; some pairs fail.
**Dead graph edges Determined DB [V]:** query_router / query_session ghost edges.
**SetFit model [V]:** C:\Users\bartl\models\setfit\stub_classifier\. Inference only.
**Suite: 1144 pass, 1 skip [V]:** confirmed post evaluator.py fix.
