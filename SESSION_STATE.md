Written at commit: 4c41a5f

# SESSION STATE - session 177
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 177, 2026-07-14)

**Determined corpus re-ingested [V]**
- Used `python -m determined.engine.run_engine C:\Users\bartl\dev\Determined` (EngineRunner).
- ingest_lang_corpus.py was wrong path for Python corpora -- only works for pure Go/Rust/JS.
- Result: 1,904 functions, 16,588 edges (static 13,890 + data_flow 2,503), docs 39%, min.js 0.
- Prior session had 2,048 fns / 23,499 edges -- reduction is correct (cytoscape/socket.io noise gone).

**SESSION_STATE data_flow_edges table reference was wrong [V]**
- data_flow has always lived in graph_edges with edge_type='data_flow'. No separate table exists.
- The "data_flow_edges table missing" error was querying a non-existent table name. Fixed in check.

**Language routing documented in PRACTICES.md [V]**
- New "LANGUAGE ROUTING" section covers all 4 languages across 6 dimensions:
  discovery, symbol extraction, call edges, data_flow, dispatch post-passes, persist path.
- Standing rule: update the table when any feature changes for any language.
- 6-step recipe for adding a new language.
- 891 tests passed, 1 skipped [V].

## NEXT SESSION -- start here

**dj2 re-ingest still pending:**
`python tools/ingest_lang_corpus.py C:\Users\bartl\dev\dj2`
(applies builtin data_flow filter from session 176; use .determinedignore to exclude Lib/, archive/, etc.)

**Remaining quality gaps (priority order):**
1. Python 36-43% docstring coverage -- real source gap. RM49 annotate_function can fill via LLM.
2. Go typed params 60% -- receiver types not extracted from method declarations.
3. dnd-dungeon-gen JS typed params 0% -- plain JS, no JSDoc @param types in source.

**Active work arc per CLAUDE.md: items 6, 20, 1** (no change this session)

## Corpus status [V for Determined; ? for others not re-checked this session]

| Corpus | Syms | Edges | data_flow | Docs% | Resolved% |
|--------|------|-------|-----------|-------|-----------|
| Determined (Python) | 1,904 | 16,588 | 2,503 | 39% | ? |
| dj2 (Python+JS) | ? | ? | ? | ? | ? (needs re-ingest) |
| end-of-eden (Go) | 533 | 7,494 | 4,148 | 39% | 15% |
| ruggrogue (Rust) | 337 | 2,741 | 439 | 29% | 14% |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 410 | 85% | 65% |
| dungeoncrawler (JS) | 78 | 192 | 29 | 88% | 61% |
| rotjs (JS) | 626 | 2,239 | 353 | 37% | 21% |

## Known issues (carried forward)

**ingest route trap [V]:** Python corpora use EngineRunner (`python -m determined.engine.run_engine`).
  ingest_lang_corpus.py is for pure Go/Rust/JS only -- passes empty file_analyses, gets 0 symbols for Python.
**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**RM21 probes not re-run [?]:** Live LLM probe not re-run this session.
**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.
**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.
**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db
**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.
**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.
**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.
**readiness_check T4 off by default [V]:** include_design_check=true required.
**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
  knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.
**dj2 ignore dirs trap [V]:** Always exclude Lib/, archive/, tools/, tools.old/, og_system/,
  recovered_code/, codebase_analyzer/, Scripts/.
**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Watch for Rust FQDN collisions.
**Go resolution 15% [V]:** Correct -- unresolved are external libs (bubbletea, lipgloss).

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
