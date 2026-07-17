Written at commit: 8129447

# SESSION STATE - session 197
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 197, 2026-07-17)

**Commonplace re-ingested [V]** (9a50ef8)
  functions: 61, edges: 292 (+51 from cross-file resolution), 1 stub (suggest_tags).

**RM67 filed: Convergence protocol [V]** (b8dd169)
  Standing operating procedure. Convergence definition (structural integrity +
  probe passes + known gap ceiling). Language scope table. Per-session probe loop
  (5 probes, deterministic, no LLM). Three open questions for Bart.
  See TRACKER.md RM67.

**RM67 first probe pass run [V]** (no commit -- probe scripts in scratchpad)
  Ran against Determined, dj2, Commonplace. Found two bad queries:
  - unresolved ratio was measuring annotation-resolution (resolved col), not unknown callees
  - EP query used nonexistent edge types
  Fixed in probe_pass2.py. Key findings surfaced (see below).

**RM68 filed: Remove subrace concept from dj2 [V]** (b8dd169)
  OG system rewrite intentionally dropped subraces. 5 stubs in dnd_data.py are
  dead concept remnants, not implementation gaps. Remove entirely.
  Scope: dnd_data.py, character_generator.py, authority_system.py.
  Capn charted: e9cfb9d1. DEFERRED.

**RM69 filed: Judgment layer design [V]** (8129447)
  classify_stub: scored competing hypotheses (concept-not-applicable,
  blocked-on-prerequisite, design-intent-stated, genuinely-unknown).
  Deterministic signals first (comment patterns, concept presence, caller graph,
  sibling density, body shape). LLM as tie-breaker only.
  Corpus-level projections: file shape, subsystem shape, prerequisite map,
  concept ghost map. Three presentation modes.
  Validation set: dj2 stubs (known answers). UI surface: depends on UI redesign.
  See TRACKER.md RM69.

## NEXT SESSION -- start here

**Continue RM67 probe pass -- remaining dj2 stubs classified:**

dj2 real implementation gaps (5) -- all in AI/adjudication layer:
  - process_consequences    (ai_dungeon_master.py:282) -- design-intent-stated
  - _register_world_tools   (ai_integration.py:219)   -- design-intent-stated (extension point)
  - _get_encounter_context  (context_builder.py:167)  -- blocked-on-prerequisite (EncounterFSM)
  - _get_combat_context     (context_builder.py:172)  -- blocked-on-prerequisite (CombatFSM)
  - on_arc_completed        (narrative_engine.py:52)  -- design-intent-stated

dj2 compatibility stubs (5 in dnd_data.py) -- RM68, remove not implement.

**Three open questions from RM67 (need Bart's input):**
  - [ ] dj2 331 inferred EPs: accept as dynamic-dispatch ceiling?
  - [ ] suggest_tags: implement or permanent demo placeholder?
  - [ ] Go/Rust/TS corpora: important beyond "proof it works"?

**RM69 is next implementation item after probe pass complete:**
  Start with signal extractor pass (deterministic). Use dj2 stubs as test set.
  Do NOT design UI surface yet -- UI redesign not started.

**Probe scripts in scratchpad (reuse next session):**
  probe_pass2.py -- fixed queries, runs against all 3 Python corpora
  reingest_determined.py, reingest_commonplace.py -- for re-ingests

## Key probe findings (session 197) [V]

**Determined:**
  3 real stubs: 2 empty __init__ (borderline), 1 suggest_tags (known)
  EP inferred: 126 (LLM orchestration layer, expected ceiling)
  Docstring missing: 464/1097 (42%, excl __init__ and tests)

**dj2:**
  10 real stubs: 5 OG-compat (RM68 remove), 5 AI-layer gaps
  EP inferred: 331 (ai_boundary.py functions, likely dynamic dispatch ceiling)
  Docstring missing: 566/1116 (50%, JS pulls this up -- JS has 0% docstrings)
  is_tool=23, function_reference=140

**Commonplace:**
  1 real stub: suggest_tags
  Unknown callee ratio varies 72-100% (Flask/SQLite external calls, expected)
  Docstring missing: 40/58 (68%, small corpus)

## Design decisions recorded this session [V]

"Probe before implement" loop validated -- running readiness_check/explore_stub
  found 2 bugs last session before any code was written. Capn entry a99b8bb7.

Judgment layer rationale: differential diagnosis model, abductive reasoning,
  spectrum-based fault localization. Show competing hypotheses with evidence,
  not single confident answer. Developer supplies domain axioms.

Sparse array insight (Bart): individual stub judgments aggregate into corpus
  shapes (subsystem skeletons, concept ghosts, prerequisite maps). This is the
  corpus-level projection layer in RM69.

## Corpus status [V]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 2,159 | 18,693 | 0 real | re-ingested; Protocol fix applied |
| dj2 (Python+JS) | ~1,400 | 10,071 | 10 real | 5 RM68-remove, 5 AI-layer gaps |
| Commonplace (Python) | 61 | 292 | 1 | suggest_tags |
| end-of-eden (Go) | 533 | 7,494 | 0 | probe pending |
| ruggrogue (Rust) | 337 | 2,741 | 0 | probe pending |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | probe pending |
| dungeoncrawler (TS) | 78 | 192 | 0 | probe pending |
| rotjs (TS) | 626 | 2,239 | 6 | probe pending |

## Known issues (carried forward)

**agent_tools call pattern trap [V]:** Tools take (assessor, args_dict).
  Entry point: determined/ask.py ask(db_path, question).
**Protocol stub false positive [V]:** FIXED session 196.
**readiness_check name collision [V]:** FIXED session 196. ORDER BY is_stub DESC.
**DB schema trap [V]:** graph_edges: caller/callee not callee_fqdn; no callee_file for JS.
  knowledge_artifacts uses 'kind'. files uses 'file_path'.
**dj2 ignore dirs trap [V]:** .determinedignore covers all exclusions.
**RM62 callee writeback trap [V]:** callee is qualified FQDN post-resolution.
**function_reference residual noise [V]:** ~10 false edges depth-1 local vars.
**EP inferred count floor [V]:** 331 dj2 / 126 Determined -- dynamic dispatch, not bugs.
**resolved col != unknown callee [V]:** graph_edges.resolved=0 means not annotation-resolved,
  NOT unknown callee. Use LEFT JOIN functions ON name to find truly unknown callees.
**probe_pass2.py duplicate rows [V]:** unknown callee ratio query has LEFT JOIN artifact
  producing duplicate file entries. Fix before next calibration pass.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081.
  Started manually for CLI use; UI starts it on-demand.
