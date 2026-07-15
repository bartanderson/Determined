Written at commit: bc7ae69

# SESSION STATE - session 182
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 182, 2026-07-15)

**RM62 fix committed [V]** (bc7ae69)

Root cause confirmed in session 181: `list_features` and `development_priorities` compared
`graph_edges.callee` (bare JS names like 'generateDungeon') against `functions.name`
(module-qualified like 'dungeon.generateDungeon') — no match, so 0 entry points everywhere.

Fix: build a `callee_feat_map` with both full names AND bare suffixes. Also added
`_resolve_sym()` and `_in_known()` helpers to `development_priorities` for consistent
bare-suffix lookup in stub blocker detection and local-missing counts.

2 new regression tests added. 40/40 pass in test_feature_shape.py. [V]
**Full regression suite NOT run this session** — deferred to next session. [?]

## NEXT SESSION -- start here

**Step 1: Run full regression suite**
```
.venv\Scripts\pytest tests/regression/ -x -q -m "not slow"
```
All tests must pass before proceeding. If failures: diagnose — the RM62 change
touches `list_features` and `development_priorities` inner loops.

**Step 2: Fix RM61 (language builtins as local-missing)**
Add per-language builtin lists to `_is_external_callee()` in `agent_tools.py`.
Python: `import builtins; set(dir(builtins))` gives the full list.
Go: make/len/cap/new/append/copy/delete/close/panic/recover + primitive type names
    (uint8, int64, float64, string, bool, byte, rune, etc.)
Rust: common macros (vec!, println!, format!, panic!, assert!, etc.) — lower priority.
After fix: re-run development_priorities on dj2 and Determined to confirm Miss counts drop.
Add regression tests for at least: Python builtins (len, print, range) classified external.

**RM60 Phase 2 remaining items (after RM61):**
- Test-directory noise filter for development_priorities
- Flat-layout auto-detection for Rust src/

## Corpus status [V from session 181]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs = combat layer gaps |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | RM62 fixed -- EP now non-zero [V] |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src dual-rep, Term.computeFontSize blocking |

## Known issues (carried forward)

**RM61 [V]:** Language builtins counted as local-missing -> inflates Miss counts. Next fix.
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

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
=== RECALL: active and logging to .recall/history.md ===
