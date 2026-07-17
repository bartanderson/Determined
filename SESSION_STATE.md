Written at commit: 117849d

# SESSION STATE - session 198
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 198, 2026-07-17)

**RM67 probe pass run against all 3 Python corpora [V]**
  Reused probe_pass2.py from prior session scratchpad.
  Results stable -- match SESSION_STATE 197 findings exactly.

**RM67 open questions resolved [V]**
  All three deferred to RM69 judgment layer:
  - 331 dj2 inferred EPs: accepted as dynamic-dispatch ceiling
  - suggest_tags: defer -- tool may classify it itself
  - Go/Rust/TS corpora: defer -- not blocking anything now
  Updated in TRACKER.md.

**dj2 AI-layer stubs discussed -- NOT tool findings [V]**
  We read dj2 source directly to understand the 5 AI-layer stubs.
  This is Bart's knowledge, not the tool's knowledge.
  Distinction established: I use this knowledge to drive the tool;
  I do not record it as tool findings or let it spoil RM69's conclusions.
  Key insight: emit/consume pattern is dj2's architectural spine.
  EncounterFSM exists (GenericFSM + config/fsms/encounter.json).
  CombatFSM does not exist yet (no schema, no emit-source).
  context_builder can't reach active_fsms -- wiring gap, not concept gap.
  NONE of this goes in TRACKER as tool findings.

**Key discipline established [V]**
  Tool findings = what the tool derives from graph + corpus.
  My knowledge = used to steer, not to answer for the tool.
  Do not record manual code archaeology as tool output.

## NEXT SESSION -- start here

**RM69 is the next implementation item.**
  Start with signal extractor pass (deterministic signals only):
  - body shape (pass / trivial return)
  - comment/docstring intent language
  - caller count
  - concept presence (grep-based, not embedding)
  - sibling stub density in class/file
  Use dj2 AI-layer stubs as validation set -- but verify tool's
  conclusions independently, do not seed it with what we already know.

**dj2 5 RM68 stubs** -- concept-not-applicable (docstrings say so).
  Remove pass deferred. Not blocking RM69.

**Probe pass script location:**
  C:\Users\bartl\AppData\Local\Temp\claude\C--Users-bartl-dev-Determined\
  7953a29e-8f62-49cf-bf6e-2cf465e1b091\scratchpad\probe_pass2.py
  (session scratchpad -- may not survive; easy to recreate from SESSION_STATE 197)

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

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081.
  Started manually for CLI use; UI starts it on-demand.
