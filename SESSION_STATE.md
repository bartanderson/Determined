Written at commit: d77de53

# SESSION STATE - session 200
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 200, 2026-07-17)

**classify_stub validated against dj2 AI-layer stubs [V]**
  Five stubs run: process_consequences, _register_world_tools, _get_encounter_context,
  _get_combat_context, on_arc_completed. All correctly classified design-intent-stated.
  Tool derived classifications from signals only -- no steerer knowledge injected.

**classify_stub validated against dj2 RM68 stubs [V]**
  Five stubs run: subraces, get_subraces_for_race, get_race_for_subrace,
  semantic_match_subrace, semantic_match_fighting_style (world/dnd_data.py).
  Expected: concept-not-applicable. Initial result: blocked-on-prerequisite (four stubs),
  genuinely-unknown (one). Two radiative problems identified and fixed.

**Two radiative problems fixed in classify_stub (d77de53) [V]**

  Problem A -- No deliberate-absence signal:
    Added _REMOVAL_RE pattern list. Detects "doesn't have", "for compatibility",
    "return empty", "no X in", etc. Fires has_removal=True -> concept-not-applicable +1.5.
    Suppresses intent signal when both fire (removal is more specific).

  Problem B -- Sibling cluster signal was context-free (count-only):
    Dense cluster was always scoring blocked-on-prerequisite regardless of sibling content.
    Fix: sibling_removal_trend now computed from full all_text per sibling (docstring +
    inline comments via _extract_body) -- same extraction as the main stub.
    In score_hypotheses: if trend >= 0.5, cluster scores concept-not-applicable scaled
    by trend (0.5 + trend*0.8); otherwise scores blocked-on-prerequisite as before.

  Additional: removed corpus-specific r'\bOG [Ss]ystem\b' from _REMOVAL_PATTERNS.
    Both pattern lists now carry explicit rule: no corpus-specific terms ever.
    Added generic r'\bno \w+ in\b' to replace it correctly.

**Post-fix results [V]**
  subraces, get_subraces_for_race, get_race_for_subrace: [0.83] concept-not-applicable
  semantic_match_subrace: [0.40] concept-not-applicable (cluster signal only, no own docstring)
  semantic_match_fighting_style: [0.47] concept-not-applicable
  AI-layer stubs: unchanged, all design-intent-stated at same scores as before.

**27 classify_stub tests pass [V]. Full suite 1095 passed, 1 skipped [V].**

**Key discipline reinforced this session [V]**
  - Calling low-confidence output "appropriate uncertainty" when the known answer is
    wrong is the same discipline violation in the other direction. Don't rationalize.
  - Expense does not determine correctness when the operation is cheap.
  - Fix radiative problems (missing signal type, decontextualized scoring), not symptoms.
  - No corpus-specific terms in tool pattern lists -- ever.

## NEXT SESSION -- start here

**RM69 Phase 2: corpus-level projections [V-next]**
  Single-stub judgment is now validated. Next: aggregate judgments into higher shapes.
  Per TRACKER.md RM69 design:
    - File shape: stub density + dominant classification per file
    - Subsystem shape: clustered blocked stubs = design skeleton; clustered
      concept-not-applicable = dead concept remnant
    - Prerequisite map: N stubs blocked on same X -> X is a build priority
    - Concept ghost map: concepts in stubs absent from live codebase = removal candidates
  Run against dj2 first. Does file shape for dnd_data.py show dead-concept dominant?
  Does file shape for context_builder.py show design-intent/blocked cluster?

**Before Phase 2: consider running classify_stub on Determined's own stubs [V-next]**
  3 real Determined stubs: suggest_tags (Determined + Commonplace), 2 empty __init__.
  Validates tool against a third corpus before building corpus-level aggregation.

## Corpus status [V]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 2,159 | 18,693 | 3 real | 2 empty __init__ (borderline), 1 suggest_tags |
| dj2 (Python+JS) | ~1,400 | 10,071 | 10 real | 5 RM68-remove, 5 AI-layer gaps |
| Commonplace (Python) | 61 | 292 | 1 | suggest_tags |

## Known issues (carried forward)

**agent_tools call pattern trap [V]:** Tools take (assessor, args_dict).
  Entry point: determined/ask.py ask(db_path, question).
**Protocol stub false positive [V]:** FIXED session 196.
**readiness_check name collision [V]:** FIXED session 196.
**DB schema trap [V]:** graph_edges: caller/callee not callee_fqdn; no callee_file for JS.
  knowledge_artifacts uses 'kind'. files uses 'file_path'.
**dj2 ignore dirs trap [V]:** .determinedignore covers all exclusions.
**RM62 callee writeback trap [V]:** callee is qualified FQDN post-resolution.
**function_reference residual noise [V]:** ~10 false edges depth-1 local vars.
**EP inferred count floor [V]:** 331 dj2 / 126 Determined -- dynamic dispatch, not bugs.
**resolved col != unknown callee [V]:** graph_edges.resolved=0 means not annotation-resolved,
  NOT unknown callee. Use LEFT JOIN functions ON name to find truly unknown callees.
**probe_pass2.py duplicate rows [?]:** unknown callee ratio query has LEFT JOIN artifact
  producing duplicate file entries. Fix before next calibration pass.
**classify_stub body_shape [?]:** _extract_body() reads source by line_number + indent.
  Not yet validated against all dj2 files -- inline comment extraction may need tuning.
**classify_stub lookup is bare name [V]:** functions table has no fqdn column.
  extract_signals takes bare function name, not dotted path. Name collisions across
  files are possible -- not yet handled.
**Corpus DB location trap [V]:** DBs live in C:\Users\bartl\dev\Determined\*.db,
  NOT in C:\Users\bartl\dev\*.db.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081.
  Started manually for CLI use; UI starts it on-demand.
