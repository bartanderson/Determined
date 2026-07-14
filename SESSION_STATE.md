Written at commit: e60620a

# SESSION STATE - session 172
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 172, 2026-07-14)

**Go/Rust quality validation arc -- all committed [V]:**

tools/lang_quality_probe.py (new): runs LanguageWalker against any corpus,
reports symbol counts, edge density, stub fraction, top callers/callees, random
edge sample. Run: `python tools/lang_quality_probe.py <corpus_root> [--sample N]`

tools/ingest_lang_corpus.py (new): ingests a non-Python corpus via persist_all
directly, bypassing EngineRunner which requires Python files. Run:
`python tools/ingest_lang_corpus.py <corpus_root>`

**language_walker.py fixes [V] (commit e402300):**
- _go_callee_name: now returns None when operand is a call_expression (chained
  builder), only emits receiver.method for identifier and one-level selector.
- _rust_callee_name: same fix for field_expression -- None for call_expression
  receivers, "inner_field.method" for field_expression receivers.
- Impact: Go 3808->3297 edges, Rust 2809->2259 edges. Garbage chain strings gone.
- 831 tests pass [V].

**graph_utils.py fixes [V] (commits b6747ac, 4d44018, e60620a):**
- most_connected file_map: now indexes by both full FQDN and bare name so
  Go "game.SessionAdapter" matches source_id "SessionAdapter".
- most_connected display_name: bare-key entries now show full FQDN.
- most_connected dedup: merges bare+FQDN entries for same symbol/file into one.
  run::run went from two split entries to one correct (in=92 out=51).

**persistence_engine.py fix [V] (commit e60620a):**
- _persist_js_ts_files now inserts rows into files table (file_path, line_count,
  ingested_at) for every file it processes.
- Root cause: files table was Python-only; find_todos/search_files/files_in_directory
  returned empty for all Go/Rust corpora.
- After fix: end-of-eden shows 10 real TODOs (shader hacks, error handling gaps).
  Ruggrogue has zero TODOs (confirmed by grep -- clean codebase).

**identity/symbol_identity.py + agent_tools.py fix [V] (commit e60620a):**
- normalize_symbol now strips :: before . so "Module::Fn" -> "Fn".
- _list_callers_raw now also matches raw (un-normalized) symbol as OR clause.
- FieldOfView::get went from 0 callers to 133 [V].

**Corpora ingested and verified [V]:**
- C_Users_bartl_dev_corpora_end_of_eden.db: 533 symbols, 3305 edges, 109 files
- C_Users_bartl_dev_corpora_ruggrogue.db: 337 symbols, 2259 edges, 46 files

## NEXT SESSION -- start here

**Bart flagged quality concerns at end of session.** Next session should open with
a code audit before any new feature work. Specifically:

1. **Audit the changes made this session** -- four commits touched core identity,
   persistence, and graph analysis. Verify no regressions introduced beyond the
   831-test suite (which doesn't cover Go/Rust integration paths end-to-end).
2. **caller file/line = "? None" for Go/Rust [?]** -- list_callers returns correct
   caller names but file_path and line_number are always null because symbol_references
   is Python-only. Needs fallback to functions.file_path for Go/Rust callers.
3. **Go cluster analysis empty [?]** -- Bubble Tea interface dispatch hides all
   Model.Update/Model.View call edges. Structural fix requires Go interface detection.
4. **Go/Rust interface/trait extraction** -- extract `interface` types (Go) and
   `trait` impls (Rust) so topology analysis is meaningful for these languages.

## Known issues (carried forward)

**RM21 probes not re-run [?]:** Live LLM probe not re-run.

**find_abc_gaps same-file blind spot [V]:** Base + subclasses in same file = false gap.

**GUIDE_DATA sync trap [V]:** guide_commonplace.json and console.html GUIDE_DATA separate.

**Determined corpus DB path [V]:** C_Users_bartl_dev_Determined.db

**RM40 opt-in trap [V]:** resolved_only defaults False. Pass resolved_only=True explicitly.

**RM43 empty-board trap [V]:** Lenses produce nothing on an empty clue board.

**scaffold_from_pattern embedding path [V]:** Silently skipped if embedding unavailable.

**readiness_check T4 off by default [V]:** include_design_check=true required.

**design_note content format [V]:** Pre-existing rows have no [KIND|...] prefix.

**RM42 clue pinned state not persisted [V]:** In-memory only (low priority).

**UI re-ingest via preview browser [V]:** socket.emit("ingest", {path}) works.

**DB schema trap [V]:** graph_edges has no provenance column, no callee_fqdn/caller_fqdn.
knowledge_artifacts uses 'kind' not 'artifact_type'. files uses 'file_path' not 'path'.

**dj2 ignore dirs trap [V]:** Always exclude Lib/, archive/, tools/, tools.old/, og_system/,
recovered_code/, codebase_analyzer/, Scripts/. See reference_dj2_ignore.md memory.

**dj2 DB edge_type not kind [V]:** graph_edges uses edge_type='data_flow', not kind.

**TRACKER.md update rule [V]:** Edit tool for status changes; scratchpad-first for new
multi-line blocks.

**JS/TS _persist_graph_edges ordering trap [V]:** Step 5c MUST come after step 5.

**caller file/line null for Go/Rust [V]:** list_callers returns "? None" for file/line
because symbol_references table is Python-only. Callers are correct, locations missing.

**normalize_symbol strips :: [V]:** After e60620a, "Module::Fn" -> "Fn". This is correct
for target_id lookup but means any tool that calls normalize_symbol on a Rust FQDN loses
the type context. Watch for unintended consequences in Python corpus analysis.

**graph_edges no provenance column [V]:** cross_language linker uses edge_type='cross_language'.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
