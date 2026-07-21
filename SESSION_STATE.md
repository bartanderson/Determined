Written at commit: f91ff8a

# SESSION STATE — session 229
Written at commit: f91ff8a (2026-07-20)

## Active branch: main [V]

## What happened this session

**find_abc_gaps scope param fixed [V]**

Scope arg was accepted but silently ignored — all scopes returned identical output.
Added `AND file_path LIKE ?` filter to three queries: abc_classes, all_classes,
all_class_names. Pattern consistent with other structural gap tools.
20/20 tests pass (test_structural_gap_tools.py).

**RM69 open design questions resolved [V]**

Calibration run across dj2 (8 stubs) and Determined (12 stubs) answered all
outstanding questions:

- Hypothesis count cap: moot. Max 2 hypotheses observed in practice across both
  corpora. Theoretical concern, doesn't occur.
- Threshold calibration: scores reading correctly. _get_combat_context [0.43]
  blocked-on-prerequisite, _get_encounter_context [0.70] design-intent-stated.
  No misfires on real stubs.
- Concept presence: already grep-based in extract_signals (lines 291-304).
- Prerequisite map: stub_prerequisite_map() already built, registered, tested.
  Smoke-tested on dj2: CombatFSM surfaces as GHOST, EncounterFSM as live.
- All four corpus projections (stub_file_shape, stub_subsystem_shape,
  stub_prerequisite_map, stub_concept_ghost_map) were already complete.
  42 tests pass (test_corpus_projections.py).

RM69 is functionally complete. Only remaining open item: UI/flow surface —
explicitly deferred, not designed.

**classify_stub stateless __init__ false positive fixed [V]**

PatternExecutor and ContractDriftClassifier both have `pass` __init__ and are
correctly stateless. Were misfiring as blocked-on-prerequisite [0.40].
Fix: in score_hypotheses lifecycle branch, when impl_sibling_count >= 1 and
no instance vars assigned, override blocked-on-prerequisite to 0.0 and score
toward genuinely-unknown. Both now return UNCERTAIN (correct).
42 tests pass (test_classify_stub.py).

**Test harness fake stubs — documented, closed [V]**

9 stubs in tests/regression/ are fake/mock class methods (return []). Ingester
correctly flags them is_stub=1; they are expected noise. Decision: do not add
class-name pattern matching (Fake*, Mock*) to the ingester — too tailored.
Documented in HISTORY.md. Do not re-investigate.

**104 tests pass across all three touched test files [V]**

## Known issues [V = verified, ? = recalled]

**find_isolated_modules — test files are noisy [V]:** 67/68 moderate isolations
in dj2 are test files. Correct signal but visually noisy. Future: test-path
suppression tier or `exclude_tests` arg.

**walk_call_chain broken for TS/JS corpora [?]:** graph_edges stores callers as
FQNs; tool queries bare names. Workaround: use graph_path.

**Prose false positives in shape scanner [?]:** SESSION_STATE.md and history.md
detected as directed_graph from -> arrows. Normalizer errors on these. Acceptable.

**Server start command [V]:** always `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`.

## NEXT SESSION — start here

**RM69 is done. All structural gap tools complete. Corpus projections complete.**

**Remaining open items in TRACKER:**

RM67 convergence probe loop — adversarial probe (6 canonical questions) against
Determined itself not yet run. This is the self-model gate in RM67. Low urgency
but is the stated next step for Determined-analyzing-Determined convergence.

RM68 subrace removal in dj2 — deferred, low priority. Remove subraces,
get_subraces_for_race, get_race_for_subrace, semantic_match_subrace,
semantic_match_fighting_style from dj2. Blast radius already confirmed low.

**Run capn report when session count reaches 5.**
Counter resets after report. Next auto-notice at session 14.
