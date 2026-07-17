Written at commit: 028aebe

# SESSION STATE - session 201
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 201, 2026-07-17)

**Validated classify_stub against Determined's own stubs [V]**
  3 real stubs: 2x __init__ (pattern_executor.py, contract_drift_classifier.py),
  1x suggest_tags (examples/commonplace/services/tagger.py).
  Initial result: all three errored with "not a stub" or "symbol not found."

**Two bugs found and fixed [V]**

  Bug A -- Query asked the wrong question:
    WHERE name=? LIMIT 1 picks any function, then checks is_stub in Python.
    Fix: WHERE name=? AND is_stub=1. The filter is the claim; post-hoc check
    can't fix the wrong row. Error message updated: "stub 'X' not found" not
    "X is not a stub" (they mean different things).

  Bug B -- Regex for semantic meaning:
    _INTENT_PATTERNS and _REMOVAL_PATTERNS were brittle keyword lists.
    "STUB: returns empty list until LLM endpoint is wired" scored has_intent=False
    because the phrasing matched no pattern. Root cause: regex is the wrong tool
    for semantic meaning in natural language.

**Replacement: SetFit-trained classifier [V]**
  determined/agent/stub_classifier.py wraps a 3-class SetFit model:
    0=genuinely-unknown  1=design-intent-stated  2=concept-not-applicable
  Training set: 135 labeled examples (45/class) spanning 20+ software domains
  (web, fintech, healthcare, crypto, telecom, insurance, legal, edtech,
  supply chain, CRM, ERP, GIS, media, social, real estate, robotics, AR/VR,
  government). 96.3% eval accuracy.
  Model saved: C:\Users\bartl\models\setfit\stub_classifier\
  Training env: C:\Users\bartl\dev\setfitmodel\ (separate venv, setfit 1.1.3 +
  transformers 4.x -- incompatible with main venv's transformers 5.x).
  Inference: sentence_transformers + sklearn only (no setfit in main venv).
  Fallback: hybrid embedding + modal-verb regex when model dir absent.

**Intermediate step: sentence-level embedding + modal verb hybrid [V]**
  Per the SATD literature: two types of intent signal need two tools.
  Type 1 (semantic incompleteness): embedding similarity per sentence, threshold 0.35.
  Type 2 (grammatical mood): \b(would|should|could|meant to|intended to)\b regex.
  This is the current fallback in stub_classifier._fallback_has_intent().

**Post-fix results on Determined stubs [V]**
  suggest_tags: [0.70] design-intent-stated (correct)
  __init__ x2: UNCERTAIN, no signal (correct -- empty bodies, no docstring)
  Note: __init__ collision still picks pattern_executor.py for both -- LIMIT 1
  among stub rows. Class-context handling is a separate open design item (TRACKER.md).

**27 classify_stub tests pass [V]. Full suite 1095 passed, 1 skipped [V].**

**Future task spawned [V]**
  "Audit codebase for regex-used-for-semantic-meaning" -- chip visible in UI.
  Survey determined/agent/, determined/oracle/, determined/assessor/,
  determined/ingestion/ for pattern lists detecting meaning in natural language.

## NEXT SESSION -- start here

**RM69 Phase 2: corpus-level projections [V-next]**
  Single-stub judgment is validated across three corpora (dj2 AI-layer, dj2 RM68,
  Determined). Next: aggregate judgments into higher shapes.
  Per TRACKER.md RM69 design:
    - File shape: stub density + dominant classification per file
    - Subsystem shape: clustered blocked = design skeleton; clustered
      concept-not-applicable = dead concept remnant
    - Prerequisite map: N stubs blocked on same X -> X is build priority
    - Concept ghost map: concepts in stubs absent from live codebase = removal candidates
  Run against dj2 first. Does file shape for dnd_data.py show dead-concept dominant?
  Does file shape for context_builder.py show design-intent/blocked cluster?

**Python magic method handling -- open design item [V-next]**
  __init__ (and __str__, __repr__, __len__ etc.) can't be classified by bare name.
  Needs (class_name, file_path) lookup + class context signals.
  Five cases documented in HISTORY.md 2026-07-17 and TRACKER.md RM69 open questions.
  Implement before running Phase 2 corpus sweep so magic method stubs are handled.

## Corpus status [V]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 2,159 | 18,693 | 3 real | 2 __init__ (collision), 1 suggest_tags |
| dj2 (Python+JS) | ~1,400 | 10,071 | 10 real | 5 RM68-remove, 5 AI-layer gaps |
| Commonplace (Python) | 61 | 292 | 1 | suggest_tags |

## Known issues (carried forward)

**agent_tools call pattern trap [V]:** Tools take (assessor, args_dict).
  Entry point: determined/ask.py ask(db_path, question).
**DB schema trap [V]:** graph_edges: caller/callee not callee_fqdn; no callee_file for JS.
  knowledge_artifacts uses 'kind'. files uses 'file_path'.
**dj2 ignore dirs trap [V]:** .determinedignore covers all exclusions.
**RM62 callee writeback trap [V]:** callee is qualified FQDN post-resolution.
**function_reference residual noise [V]:** ~10 false edges depth-1 local vars.
**EP inferred count floor [V]:** 331 dj2 / 126 Determined -- dynamic dispatch, not bugs.
**resolved col != unknown callee [V]:** graph_edges.resolved=0 means not annotation-resolved,
  NOT unknown callee. Use LEFT JOIN functions ON name to find truly unknown callees.
**probe_pass2.py duplicate rows [?]:** unknown callee ratio query has LEFT JOIN artifact.
**classify_stub body_shape [?]:** _extract_body() not validated against all dj2 files.
**classify_stub __init__ collision [V]:** LIMIT 1 among stub rows still picks first match.
  Fix: (class_name, file_path) lookup + class context signals. See TRACKER.md.
**SetFit smoke test edge cases [V]:** Two borderline cases:
  "STUB: returns empty list until..." -> concept-not-applicable (returns-empty pulls it).
  "Biometric verification is handled by..." -> design-intent-stated (no explicit absence signal).
  Fallback handles these correctly via embedding similarity.
**Corpus DB location trap [V]:** DBs live in C:\Users\bartl\dev\Determined\*.db,
  NOT in C:\Users\bartl\dev\*.db.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081.
  Started manually for CLI use; UI starts it on-demand.
SetFit model: C:\Users\bartl\models\setfit\stub_classifier\ (sentence_transformers + sklearn).
  Training env: C:\Users\bartl\dev\setfitmodel\.venv (setfit 1.1.3, transformers 4.x).
