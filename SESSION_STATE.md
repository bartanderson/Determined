Written at commit: 42f786a

# SESSION STATE - session 179
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 179, 2026-07-15)

**RM59 fully done [V]**
- Phase 1 (prior session): list_features, feature_shape -- 15 tests
- Phase 2 (this session): development_priorities -- 9 new tests (24 total)
- Priority score = (1 - completeness) x entry_point_caller_count
- Cross-feature blocker flag: stubs called from other features rank higher
- All 3 tools in TOOLS dict and tool_registry
- 917 passed, 1 skipped [V]

**RM60 filed [V]**
- Ran audit_corpora.py against all 7 corpus DBs
- Found 2 structural problems before per-corpus work could start (see RM60)
- Depth reference table written to TRACKER.md RM60 for all corpora
- Phase 0 (prefix fix + missing inflation fix) must happen before Phase 1 eval

## NEXT SESSION -- start here

**RM60 Phase 0 (two fixes, do both before corpus eval):**

**Fix 1: Absolute path / prefix auto-strip**
- `list_features`, `feature_shape`, `development_priorities` all need a `prefix` param
- If omitted: auto-detect as the longest common path prefix across all `functions.file_path`
- Strip prefix from path before computing depth and display labels
- Goal: `list_features()` on any real corpus returns meaningful feature names like
  `determined/agent` not `C:/Users/bartl/dev/Determined/determined/agent`
- Where to add: extract a `_norm_and_strip(fp, prefix)` helper used by all three tools
- Test: absolute-path corpus produces same feature names as equivalent relative-path corpus

**Fix 2: External vs local "missing" callees**
- Current: any callee not in functions table is "missing" -- inflates count hugely
- Best proxy: callee name containing `.` is external (os.path.join, json.loads);
  bare names without `.` are likely local gaps
- Alternative (cleaner): drop "missing" from completeness% entirely; only stub count
  drives the score. External deps are never actionable.
- Whichever approach: test that stdlib/pip callees do not count as missing

**RM60 Phase 1 evaluation order (after Phase 0):**
1. end-of-eden (Go) - simplest, 0 stubs, verify entry point topology
2. dungeoncrawler (TS) - small, 0 stubs, verify architecture match
3. dnd-dungeon-gen (JS) - confirm 0-entry-point bug, file JS resolution gap item
4. ruggrogue (Rust) - flat layout issue, evaluate file-level feature utility
5. rotjs (TS library) - lib/src split, verify stubs and public API
6. Determined (Python) - run depth=6 and depth=7, evaluate real gaps vs test noise
7. dj2 (Python+JS) - feature_shape for world/ and dungeon/, find real stubs

**70% = after item 5 (rotjs). Flag for session switch after rotjs evaluation.**

## Pre-audit findings [V]

**Absolute path depth bug [V]:** All 7 corpus DBs store Windows absolute paths.
`depth=1` produces single feature `C:` -- useless. Per-corpus correct depths:
  | Corpus | Common prefix | Feature depth |
  | Determined | C:/Users/bartl/dev/Determined | 6 |
  | dj2 | C:/Users/bartl/dev/dj2 | 6 |
  | end-of-eden | C:/Users/bartl/dev/corpora/end-of-eden | 7 |
  | ruggrogue | C:/Users/bartl/dev/corpora/ruggrogue/src | 8 |
  | dnd-dungeon-gen | C:/Users/bartl/dev/corpora/dnd-dungeon-gen/app | 8 |
  | dungeoncrawler | C:/Users/bartl/dev/corpora/dungeoncrawler/src | 8 |
  | rotjs | C:/Users/bartl/dev/corpora/rotjs | 7 |

**dnd-dungeon-gen JS 0 entry points [?]:** All features show 0 entry points despite
multi-directory structure. Likely JS cross-file call resolution is broken. Needs
verification by checking a known cross-dir call exists in the source.

**development_priorities score always 0.0 [V]:** Symptom of absolute path bug --
everything in one `C:` feature means no cross-feature edges. Fixed by Fix 1.

## Corpus status [V]

| Corpus | Syms | Edges | data_flow | Docs% | Typed% | Notes |
|--------|------|-------|-----------|-------|--------|-------|
| Determined (Python) | 1,904 | 16,588 | 2,503 | 39% | 100% | [V session 177] |
| dj2 (Python+JS) | 1,399 | 9,931 | 1,336 | 43% | 94% | [V session 178] |
| end-of-eden (Go) | 533 | 7,494 | 4,148 | 40% | 89% | [V session 178] |
| ruggrogue (Rust) | 337 | 2,741 | 439 | 30% | 83% | [V session 178] |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 410 | 86% | 0% (N/A) | plain JS |
| dungeoncrawler (TS) | 78 | 192 | 29 | 88% | 56% | TypeScript |
| rotjs (TS) | 626 | 2,239 | 353 | 37% | 31% | TypeScript library |

## Known issues (carried forward)

**ingest route trap [V]:** Python corpora use EngineRunner. ingest_lang_corpus.py is Go/Rust/JS/TS only.
**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.
**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.
**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db
**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.
**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.
**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.
**readiness_check T4 off by default [V]:** include_design_check=true required.
**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
  knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
**dj2 ignore dirs trap [V]:** .determinedignore in dj2 repo covers all exclusions.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.
**RM59 tools need prefix param [V]:** list_features/feature_shape/development_priorities
  assume relative paths; absolute Windows paths break depth=1. Fix is RM60 Phase 0.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
