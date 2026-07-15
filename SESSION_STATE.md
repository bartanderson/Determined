Written at commit: 6973114

# SESSION STATE - session 181
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 181, 2026-07-15)

**RM60 Phase 1 done [V]** - Per-corpus evaluation of all 7 corpora

Ran list_features, development_priorities, and feature_shape against every corpus DB.
Confirmed or filed findings for each. Two new bugs filed (RM61, RM62).

### Per-corpus findings [V]

**end-of-eden (Go)**
- system (270EP) and game (200EP) correctly most-connected [V]
- 0 stubs confirmed [V]
- Cross-feature calls (game -> assets via fs.ReadFile, system/audio -> assets) real [V]
- Finding: Go builtins (make, len, string, uint64) counted as local-missing -> RM61

**dungeoncrawler (TS)**
- rendering (9EP), entities (8EP), ui (8EP) correctly most-called [V]
- 0 stubs confirmed [V]
- Architecture matches TS dungeon crawler structure [V]

**dnd-dungeon-gen (JS)**
- 0 EP bug CONFIRMED [V]
- Root cause: JS resolution sets resolved=1 but target_id stays as bare callee name
  ('generateDungeon') instead of canonical_id ('...dungeon/generate.js:function:...')
- 640 resolved edges, 0 join to canonical_id, 0 entry points across all features
- Suffix match (s.name LIKE '%.' || ge.callee) correctly resolves -> fix path clear
- Filed RM62 [V]

**ruggrogue (Rust)**
- File-level grouping correct for Rust one-concept-per-file layout [V]
- map.rs (31EP), experience.rs (28EP), gamekey.rs (1 sym, 17EP) make sense [V]
- 0 stubs confirmed [V]

**rotjs (TS library)**
- lib/ (290sy, 297EP) = compiled output; src/ (271sy, 0EP) = TS source [V]
- Pattern: all imports target lib/ -> lib/ accumulates EP, src/ shows 0 EP [V]
- 3 stubs in lib/: Room.createRandomCenter, Room.createRandom, RNG.getItem [V]
- Term.computeFontSize is src/ blocking stub [V]
- Pattern documented: for TS libs, analyze src/ for architecture, lib/ for public surface

**Determined (Python) depth=2**
- determined/agent: 173EP, 83% complete, 1 stub [V]
- determined/ingestion: 48EP, 72% complete, 0 stubs [V]
- determined/graph: 1 stub - structural_score (blocking) [V]
- determined/resolution: 20% complete, 1 stub - genuinely low [V]
- Inconsistency: feature_shape completeness% (14%) vs dev_priorities% (83%)
  Because: feature_shape counts all edge instances, dev_priorities counts distinct callees
  This is a display inconsistency worth documenting, not a data error

**dj2 (Python+JS) world/**
- world/ 10 stubs are REAL implementation gaps [V]
- Class methods called but not defined: AIDungeonMaster (dialog, narrative),
  ActionQueue (dequeue, is_empty), AdjudicationEngine (process, start_encounter, _handle_*)
- Blocking stub: _get_combat_context
- world_app.py (160EP) correctly identified as primary entry file [V]
- Python builtins (print 188x, range 116x, len 113x) inflate local-missing -> RM61

### New bugs filed [V]

**RM62** - JS ingester loses callee file on resolution. Fix: after setting resolved=1,
also update target_id = s.canonical_id. High priority. Re-ingest JS corpora after fix.

**RM61** - Language builtins classified as local-missing. Fix: add per-language builtin
list to _is_external_callee() in agent_tools.py. Medium priority.

## NEXT SESSION -- start here

**RM62 fix (recommended first)**
Find the JS resolution post-pass in determined/ingestion/. Grep for `resolved` and
`target_id` in ingestion files. After setting `resolved=1`, also set
`target_id = s.canonical_id` for the matched symbol. Re-ingest dnd-dungeon-gen
and verify entry points appear (should show controller as high-EP feature).

**RM61 fix (second)**
Add builtin lists to `_is_external_callee()` in agent_tools.py.
Python: `import builtins; set(dir(builtins))` gives the full list plus common exceptions.
Go: make/len/cap/new/append/copy/delete/close/panic/recover + all primitive type names.
Re-run development_priorities on dj2/world/ and Determined -- Miss counts should drop dramatically.

**RM60 Phase 2 remaining (lower priority)**
- Test-directory noise filter for development_priorities
- Flat-layout auto-detection for Rust src/

## Corpus status [V]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking [V] |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs = combat layer gaps [V] |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete [V] |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete [V] |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | 0 EP everywhere due to RM62 bug [V] |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete [V] |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src dual-rep, Term.computeFontSize blocking [V] |

## Known issues (carried forward)

**RM62 [V]:** JS target_id mismatch -> 0 entry points for all JS features. Fix in ingester.
**RM61 [V]:** Language builtins counted as local-missing -> inflates Miss counts.
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
  graph_edges.target_id = bare name for JS (not canonical_id) -- this IS RM62.
**dj2 ignore dirs trap [V]:** .determinedignore in dj2 repo covers all exclusions.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
=== RECALL: active and logging to .recall/history.md ===
