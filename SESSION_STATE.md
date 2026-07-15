Written at commit: 8452d9d

# SESSION STATE - session 183
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 183, 2026-07-15)

**Step 1: Full regression suite passed [V]** (938 tests at session start, exit 0)

**RM61 fixed [V]** (15469fb)
Added _PY_BUILTINS, _GO_BUILTINS, _RUST_BUILTINS frozensets and _detect_corpus_lang(conn)
that detects dominant file extension and returns the right builtin set. _is_external_callee()
gains optional `builtins` param; feature_shape and development_priorities detect lang once
per call and pass it through. Fallback: if files table absent, try functions table.
5 new regression tests. 938 passed.

**RM60 Phase 2 completed [V]** (f96557e, 6347c2c)
- Test-directory noise filter: exclude_tests=True default in list_features and
  development_priorities. _is_test_feature() matches tests/, test/, spec/, __tests__/,
  test_*.py etc. 5 new tests.
- Flat-layout (Rust src/): closed as already resolved by Phase 0 prefix auto-detect.
- rotjs lib/src warning: list_features appends Note when lib/dist/build/out EP >= 5x
  src/ EP and src/ has >10 syms. Suggests scope=src. 3 new tests.
- All Phase 2 items closed. 943/946 passed at various checkpoints.

**RM62 ingester fix [V]** (8452d9d)
Root cause: resolution post-pass SET resolved=1 but left callee/target_id as bare name.
Fix: same UPDATE now also sets callee and target_id to functions.name (qualified FQDN).
Binding count: 4x file_paths (callee subquery, target_id subquery, WHERE caller_file,
EXISTS subquery). 2 existing tests updated (bare -> qualified assertions). 2 new tests
verifying writeback. 948 passed. [V]

**RM61 and RM62 marked DONE in TRACKER.md [V]**

## NEXT SESSION -- start here

**Step 1: Re-ingest dnd-dungeon-gen** to pick up qualified callee names from RM62 fix.
```
python tools/ingest_lang_corpus.py --corpus C:\Users\bartl\dev\corpora\dnd-dungeon-gen
```
(Use ingest_lang_corpus.py NOT EngineRunner -- JS-only corpus, see HISTORY.md.)

**Step 2: Verify EP counts non-zero for dnd-dungeon-gen**
```python
from determined.oracle.db_oracle import DBOracle
from determined.agent.agent_tools import list_features, development_priorities
oracle = DBOracle('C_Users_bartl_dev_corpora_dnd_dungeon_gen.db')
print(list_features(oracle, {"depth": 1}))
print(development_priorities(oracle, {"depth": 1}))
```
Expected: dungeon/, generate/, controller/ show non-zero EP (was 0 before fix).

**Step 3: Run full regression suite**
```
.venv\Scripts\pytest tests/regression/ -x -q -m "not slow"
```

**Step 4: Check TRACKER.md** for remaining open items after RM60/61/62 all done.

## Corpus status [V from session 181, except dnd-dungeon-gen needs re-ingest]

| Corpus | Syms | Edges | Stubs | Notes |
|--------|------|-------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 4 real | agent 83%, structural_score blocking |
| dj2 (Python+JS) | 1,399 | 9,931 | 13 | world/ 10 stubs = combat layer gaps |
| end-of-eden (Go) | 533 | 7,494 | 0 | complete |
| ruggrogue (Rust) | 337 | 2,741 | 0 | complete |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 6 | NEEDS RE-INGEST for RM62 fix [?] |
| dungeoncrawler (TS) | 78 | 192 | 0 | complete |
| rotjs (TS) | 626 | 2,239 | 6 | lib/src warning now in list_features |

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
  Tests asserting bare JS callee names on resolved edges will fail. Updated this session.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
