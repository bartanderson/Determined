Written at commit: 8b6ab5c

# SESSION STATE - session 176
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 176, 2026-07-14)

**JS data_flow was 0 -- diagnosed and fixed [V]**
- Root cause: JS corpora were ingested before f2d1553 wired data_flow into persist layer.
- Fix: re-ingest all three JS corpora. Now: dnd-dungeon-gen=410, dungeoncrawler=29, rotjs=353.

**Cross-corpus quality analysis [V]**
- Queried all 7 corpus DBs for stubs, docstrings, typed params, orphans, edge density,
  unresolved callees, data_flow hubs.
- Key findings: Go/Rust/JS had 0% docstrings (extractor gap), dnd-dungeon-gen 99% unresolved
  (name format mismatch + template literal bug), Python data_flow hubs dominated by builtins,
  Determined DB has .min.js noise (cytoscape, socket.io), Rust tuple-field callee garbage.

**0780c65 -- Quality fixes round 1 [V]**
- scan_project_files: skip *.min.js / *.min.ts from JS discovery.
- language_walker: add _preceding_comment() helper; extracts Go // lines, Rust /// lines,
  JS/TS JSDoc above declarations. Wired into _go_symbols, _rust_symbols, _js_symbols.
- language_walker: _go_param_types now also captures variadic_parameter_declaration.
- language_walker: _js_callee_name rejects multi-line or >120-char text (template literal
  bug storing raw array join expressions as callee names in dnd-dungeon-gen).
- Results after re-ingest: Go 0%->39% docs, Rust 0%->29% docs, dnd-dungeon-gen 0%->85%,
  dungeoncrawler 0%->88%, rotjs 0%->37%.

**8b6ab5c -- Quality fixes round 2 [V]**
- parse_ast.py: _PY_BUILTINS module-level frozenset; filter builtins from data_flow callers.
  len/list/isinstance were producing 65-229 phantom data_flow edges each.
- language_walker: _rust_callee_name filters tuple-field callees (self.0.method() -> None).
  Removed 41 garbage edges from ruggrogue (2782->2741 edges).
- persistence_engine: resolution post-pass extended to handle :: separator for Rust.
  Rust resolution rate: 7% -> 14%.
- 891 tests passed, 1 skipped [V].

## Corpus status after this session [V]

| Corpus | Syms | Edges | data_flow | Docs% | Typed% | Resolved% |
|--------|------|-------|-----------|-------|--------|-----------|
| dj2 (Python+JS) | 1,399 | 10,206 | 1,611 | 43% | 33% | ~4% (needs re-ingest) |
| Determined (Python) | 2,048 | 23,499 | 3,157 | 36% | 33% | 3% (min.js noise, needs re-ingest) |
| end-of-eden (Go) | 533 | 7,494 | 4,148 | 39% | 60% | 15% |
| ruggrogue (Rust) | 337 | 2,741 | 439 | 29% | 83% | 14% |
| dnd-dungeon-gen (JS) | 291 | 1,384 | 410 | 85% | 0% | 65% |
| dungeoncrawler (JS) | 78 | 192 | 29 | 88% | 56% | 61% |
| rotjs (JS) | 626 | 2,239 | 353 | 37% | 30% | 21% |

## NEXT SESSION -- start here

**Two corpora need re-ingest to pick up this session's fixes:**
1. Determined: close the UI first (DB locked), then:
   `python tools/ingest_lang_corpus.py C:\Users\bartl\dev\Determined`
   Drops cytoscape.min.js + socket.io.min.js (currently 163 fns, 6,453 edges of noise).
2. dj2: re-ingest to apply builtin data_flow filter:
   `python tools/ingest_lang_corpus.py C:\Users\bartl\dev\dj2`
   Must use .determinedignore to exclude Lib/, archive/, tools/, etc.

**Remaining quality gaps (priority order):**
1. Python 36-43% docstring coverage -- real source gap. RM49 annotate_function can fill via LLM.
2. Go typed params 60% -- receiver types still not extracted from method declarations.
3. dnd-dungeon-gen JS typed params 0% -- plain JS, no JSDoc @param types in source.
4. No new TRACKER items filed this session. Next work per CLAUDE.md: nothing open.

## Known issues (carried forward)

**ingest_lang_corpus.py for non-Python corpora [V]:** Use tools/ingest_lang_corpus.py.
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
**Rust tuple-field callees fixed [V]:** self.0.method() now returns None.
**Determined min.js noise [?]:** Still present until re-ingest after UI closed.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
