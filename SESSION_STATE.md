Written at commit: c1a0497

# SESSION STATE - session 199
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 199, 2026-07-17)

**RM67 probe pass complete [V]** (ae92ab6)
  All three open questions deferred to RM69 (tool should answer them itself).
  TRACKER language scope + convergence status updated.

**Key discipline established [V]**
  Tool findings = what tool derives from graph + corpus only.
  My knowledge = used to steer, never injected as tool output.
  "Don't spoil the tool's enjoyment of season 2 episode 3."

**RM69 Phase 1 shipped [V]** (c1a0497)
  determined/agent/classify_stub.py:
    extract_signals(oracle, fqdn) -> dict  -- pure DB + source read, no LLM
      signals: body_shape, has_intent, intent_text, caller_count,
               callee_count, concept_presence, sibling_stub_count,
               sibling_stubs, file_character, docstring_quality
    score_hypotheses(signals) -> list[dict]  -- weighted evidence scoring
      four hypotheses: concept-not-applicable, blocked-on-prerequisite,
                       design-intent-stated, genuinely-unknown
    classify_stub(assessor, args) -- tool entry point, wired into TOOLS + registry
  27 regression tests. 1095 pass, 1 skipped.

  Key scoring decision: absent concepts + callers → blocked-on-prerequisite
  (not concept-not-applicable). Callers mean something is waiting. See HISTORY.md.

## NEXT SESSION -- start here

**Run classify_stub against dj2 AI-layer stubs [V-next]**
  Do NOT seed it with what we know. Read the tool's output cold.
  Five stubs to run:
    process_consequences      (world/ai_dungeon_master.py)
    _register_world_tools     (world/ai_integration.py)
    _get_encounter_context    (world/context_builder.py)
    _get_combat_context       (world/context_builder.py)
    on_arc_completed          (world/narrative_engine.py)
  Then evaluate: does the tool's classification match reality?
  Where it misses, that's signal weight calibration work.

**Also run against dj2 RM68 stubs (concept-not-applicable expected):**
    subraces, get_subraces_for_race, get_race_for_subrace,
    semantic_match_subrace, semantic_match_fighting_style  (world/dnd_data.py)

**After validation:**
  If signal weights need calibration, adjust score_hypotheses() weights.
  If body_shape extraction is missing inline comments correctly, check
  _extract_body() indent logic against real dj2 files.
  Then consider corpus-level projections (RM69 Phase 2: file shape,
  subsystem shape, prerequisite map) -- but only after single-stub
  judgment is validated.

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
  Not yet validated against real dj2 files -- inline comment extraction may need tuning.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081.
  Started manually for CLI use; UI starts it on-demand.
