Written at commit: 89510d7

# SESSION STATE - session 186
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 186, 2026-07-16)

**RM39-L3 TRACKER cleanup [V]** (in 04cd225)
Stale [TODO] block for RM39-L3 deleted from TRACKER.md. Code was done in session 167
(commit 486dbf2). SESSION_STATE had carried it forward as [TODO] in error.

**RM21 Fix A: confabulated-symbol detection [V]** (04cd225)
claim_verifier.verify_claim now checks functions table when a CALLS subject has no
outgoing edges. If symbol doesn't exist in corpus at all -> emit correction ("does not
exist in this codebase. Do not reference it."). Same check for HAS_METHOD when class
not in classes table. Both checks wrapped in try/except for graceful degradation if
table missing (older fixtures). 4 new regression tests. 985 passed [V].

**RM21-B filed as gated TODO [V]** (59ced74)
Prose-style confabulation escape ("the request flows through query_router" without
"calls" keyword) added to RM21 block in TRACKER.md. Gated: implement only if live
Q5 probe still shows prose confabulation after Fix A.

**RM21 noise words expanded [V]** (89510d7)
Added "what", "who", "where", "how", "why", "via", "its", "any", "all" to _NOISE_WORDS.
Prevents followup suggestion text ("what calls Entry") from being parsed as CALLS claims.

**Live Q5 probe: PASS [V]**
Ran "what is the path from the web route to the database for a new entry?" against
C_Users_bartl_dev_Determined_examples_commonplace.db. Answer: capture_post ->
extractor/tagger -> enrich_entry -> queries.insert. No query_router, no query_session,
no Determined internals. Claim verifier fired no corrections after noise words fix.
RM21-B gate: prose confabulation not observed -> RM21-B stays gated.

## NEXT SESSION -- start here

Priority order:
1. **RM21 remaining techniques** -- Technique 3 (prompt chaining/decomposition) is next
   tractable layer. Tractability order: 1 -> 3 -> 2 -> 5 -> 4 -> 6. Only pursue if a
   real multi-hop query still fails after Technique 1.
2. **RM21-B** -- prose confabulation scan, gated on observing it in practice. Not yet seen.
3. **RM64 follow-ons** -- gated, use after more real-world exercise of feature_work_plan.
4. **RM10** -- DeRe-CoT recomposition pass in goal_intake, long-horizon.

## Corpus status [?]

(Unchanged from session 185 -- no re-ingest this session)

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs; 1 UNGROUNDABLE (CombatFSM), 1 MISSING_BRIDGE (session->Encounter), 8 BLOCKED |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested, EP counts correct |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |

## Known issues (carried forward)

**concept extraction scope [V]:** _extract_docstring_concepts uses compound-CamelCase regex
  + architectural-suffix regex. Single-word capitalised English words (Process, Register, System)
  are excluded by design -- they match prose verbs, not class-like concept names.
**feature_shape vs dev_priorities% inconsistency [V]:** Different counting methods, not a bug.
**ingest route trap [V]:** Python corpora use EngineRunner. ingest_lang_corpus.py is Go/Rust/JS/TS only.
**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.
**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.
**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db
**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.
**DB schema trap [V]:** graph_edges: caller/callee cols not callee_fqdn; no callee_file for JS.
  knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
**dj2 ignore dirs trap [V]:** .determinedignore in dj2 repo covers all exclusions.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.
**RM62 callee writeback trap [V]:** After resolution post-pass, callee is qualified FQDN.
  Tests asserting bare JS callee names on resolved edges will fail.
**feature_work_plan axis grouping [V]:** Axes derived from unresolved callees only. Stubs
  with no unresolved callees land in the feature's own axis, not a destination axis.
**claim_verifier prose escape [V]:** Verifier only catches confabulation expressed as "X calls Y".
  Prose-style confabulation escapes. Filed as RM21-B, gated on observing it in live probe.
  Not yet observed.

LLM server: llama-server.exe at C:\Users\bartl\models\llama-server\llama-server.exe,
  model: C:\Users\bartl\models\gguf\Qwen_Qwen3-8B-Q4_K_M.gguf, port 8081, --ctx-size 32768.
  Started manually for CLI use; UI starts it on-demand.
