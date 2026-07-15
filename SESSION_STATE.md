Written at commit: 92fd9b8

# SESSION STATE - session 184
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 184, 2026-07-15)

**dnd-dungeon-gen re-ingested [V]**
291 symbols, 1,384 edges. EP counts now non-zero: utility 290EP, ui 142EP, controller 9EP,
dungeon 7EP. Was all-zero before RM62 fix. Confirmed list_features and development_priorities
return correct results.

**RM60 marked DONE in TRACKER.md [V]**
All 7 corpus checkboxes were already checked; item updated from [ACTIVE] to [DONE 2026-07-15].

**Regression suite: 948 passed, 1 skipped [V]**

## NEXT SESSION -- start here

**Check TRACKER.md** for remaining open items. Active known items:
- RM39-L3: Data flow Level 3 (for-loop + kwarg patterns) -- [TODO], no urgency flagged
- RM21: Small-model reasoning enhancement -- [ACTIVE], some sub-questions deferred

## Corpus status [V]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs = combat layer gaps |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | re-ingested, EP counts correct |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning in list_features |

## Known issues (carried forward)

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

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
