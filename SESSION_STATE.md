Written at commit: f7e14dc

# SESSION STATE - session 180
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 180, 2026-07-15)

**RM59 Phase 2 done [V]** (carried from session 179)
- development_priorities: 9 tests, 917 passed

**RM60 Phase 0 done [V]**
- Fix 1: _detect_prefix / _strip_prefix / _dir_key_fn helpers added to agent_tools.py
  list_features, feature_shape, development_priorities all auto-detect corpus root prefix
  and strip it from labels. depth=1 on real corpora now yields 'determined/', 'game/', etc.
- Fix 2: _is_external_callee() -- dotted names (os.path.join, json.loads, bubbletea.Run)
  classified as external library calls, excluded from local-missing count and completeness%
  feature_shape labels edges as 'external' vs 'local-missing' vs 'cross-feature'
- 14 new regression tests (38 total in test_feature_shape.py)
- 931 passed, 1 skipped [V]

**Verified on real corpora [V]**
- Determined: 89% complete (was 50% with inflation bug), 4 stubs, top blocker: structural_score
- end-of-eden: 0 stubs across all 7 features (system, game, internal, ui, cmd, debug, assets)
- dj2: world/ has 10 stubs (largest incomplete feature), world_app.py 160 entry points

## NEXT SESSION -- start here

**RM60 Phase 1: Per-corpus evaluation**

Phase 0 is done. Tools now produce correct output. Run evaluation in this order:

1. **end-of-eden (Go)** -- `list_features(depth=1)` [already seen: system/game/internal/ui/cmd]
   Verify entry point topology is architecturally correct. Are system(270 EP) and game(200 EP)
   the right most-connected features? Spot-check 2-3 actual cross-feature calls in the source.
   Check: does feature_shape for 'game' or 'system' show sensible paths?

2. **dungeoncrawler (TS)** -- `list_features(depth=1)` [rendering 9EP, entities 8EP, etc.]
   Verify architecture matches actual TS source. 0 stubs confirmed. Any local-missing?

3. **dnd-dungeon-gen (JS)** -- ALL features show 0 entry points. CONFIRM the bug:
   Pick a known cross-directory call in the source (e.g. controller/ calling dungeon/).
   Check graph_edges in the DB -- is the edge absent? If absent -> JS cross-file resolution
   is broken. File a new RM item for the gap.

4. **ruggrogue (Rust)** -- depth=1 gives individual .rs files (flat src/ layout).
   Evaluate: is file-level feature grouping useful or noisy? Check if map.rs(31EP),
   experience.rs(28EP) make sense. Consider whether depth=2 or a different strategy helps.

5. **rotjs (TS library)** -- lib/(290 syms, 297EP) vs src/(271 syms, 0EP).
   lib/ is compiled output. Are the 3 stubs in lib/ real? Check if they match src/.
   Document the lib/src dual-representation as a known pattern.

**FLAG FOR NEW SESSION after rotjs (item 5 = 70% of Phase 1).**

6. **Determined (Python)** -- depth=1 shows determined/(89%, 4 stubs), tests/(9 stubs noise).
   At depth=2: run list_features(depth=2) to see determined/agent, determined/ingestion, etc.
   Which sub-package has highest priority? Are the 4 stubs (structural_score + 3 others)
   real implementation gaps? Run feature_shape for 'determined/agent' and 'determined/ingestion'.

7. **dj2 (Python+JS)** -- world/ has 10 stubs. Run feature_shape('world') to trace paths.
   Which stubs block game systems? Are the 10 stubs in world/ real implementation gaps?

**How to run evaluations (scratchpad script pattern):**
```python
import sqlite3; from unittest.mock import MagicMock; import sys
sys.path.insert(0, r"C:\Users\bartl\dev\Determined")
from determined.agent.agent_tools import list_features, feature_shape, development_priorities
def oracle(path): o = MagicMock(); o.conn = sqlite3.connect(path); return o
```
DB paths are in the depth reference table below.

## Corpus status [V]

| Corpus | Syms | Edges | data_flow | Docs% | Typed% | Stubs | Notes |
|--------|------|-------|-----------|-------|--------|-------|-------|
| Determined (Python) | 1,904 | 16,588 | 2,503 | 39% | 100% | 4 real | 89% complete [V] |
| dj2 (Python+JS) | 1,399 | 9,931 | 1,336 | 43% | 94% | 13 | world/ has 10 [V] |
| end-of-eden (Go) | 533 | 7,494 | 4,148 | 40% | 89% | 0 | complete [V] |
| ruggrogue (Rust) | 337 | 2,741 | 439 | 30% | 83% | 0 | complete [V] |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 410 | 86% | 0% (N/A) | 6 | 0 EP bug [?] |
| dungeoncrawler (TS) | 78 | 192 | 29 | 88% | 56% | 0 | complete [V] |
| rotjs (TS) | 626 | 2,239 | 353 | 37% | 31% | 6 | lib/src split [?] |

## RM60 depth reference [V]

| Corpus | DB file | Auto-detected prefix | Feature depth |
|--------|---------|---------------------|---------------|
| Determined | C_Users_bartl_dev_Determined.db | C:/Users/bartl/dev/Determined | 1 -> top pkgs |
| dj2 | C_Users_bartl_dev_dj2.db | C:/Users/bartl/dev/dj2 | 1 -> top dirs |
| end-of-eden | C_Users_bartl_dev_corpora_end_of_eden.db | C:/Users/bartl/dev/corpora/end-of-eden | 1 |
| ruggrogue | C_Users_bartl_dev_corpora_ruggrogue.db | C:/Users/bartl/dev/corpora/ruggrogue/src | 1 -> .rs files |
| dnd-dungeon-gen | C_Users_bartl_dev_corpora_dnd_dungeon_gen.db | C:/Users/bartl/dev/corpora/dnd-dungeon-gen/app | 1 |
| dungeoncrawler | C_Users_bartl_dev_corpora_dungeoncrawler.db | C:/Users/bartl/dev/corpora/dungeoncrawler/src | 1 |
| rotjs | C_Users_bartl_dev_corpora_rotjs.db | C:/Users/bartl/dev/corpora/rotjs | 1 |

## Known issues (carried forward)

**ingest route trap [V]:** Python corpora use EngineRunner. ingest_lang_corpus.py is Go/Rust/JS/TS only.
**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.
**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.
**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db
**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.
**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
  knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
**dj2 ignore dirs trap [V]:** .determinedignore in dj2 repo covers all exclusions.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).
**JS typed params N/A [V]:** Plain JS has no type syntax. 0% is correct, not a gap.
**dnd-dungeon-gen 0 entry points [?]:** All features show 0 EP despite multi-directory
  structure. Likely JS cross-file resolution gap. Needs verification in Phase 1 item 3.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
