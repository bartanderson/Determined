Written at commit: 405bb31

# SESSION STATE - session 169 wrap
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 169, 2026-07-13)

**RM53 fully complete -- all 3 phases committed [V]:**

Phase 1 (JS/TS wire-in) -- commit 857fa6a [V]
- `scan_project_files.py`: `discover_js_ts_files()` added
- `persistence_engine.py`: `_persist_js_ts_files()` + step 5c wire-in
- `test_language_walker_persist.py`: 6 tests
- dnd-dungeon-gen validated: 291 symbols, 974 call edges

Phase 2 (Go) -- commit 36990d8 [V]
- `.go` and `.rs` added to `_JS_TS_EXTENSIONS` in scan_project_files.py
- `_GO_BUILTINS` extended to filter primitive type-cast callees
- 5 new Go call edge tests
- end_of_eden cloned to `C:\Users\bartl\dev\corpora\end_of_eden`
- end_of_eden validated: 529 symbols

Phase 3 (Rust) -- commit 3480d20 [V]
- `_rust_symbols()` + `_rust_fn_ranges()`: impl-block dedup (free fn scan now excludes
  fn_items whose start line falls within an impl block range)
- `_rust_call_edges()` implemented: call_expression walk + `_rust_callee_name()`
- `_RUST_BUILTINS` set added
- 5 new Rust regression tests
- ruggrogue cloned to `C:\Users\bartl\dev\corpora\ruggrogue`

**Post-commit accuracy fixes [V]:**

Go fix -- commit 702dbce [V]
- `_go_call_edges` was calling `_js_callee_name` which checks `member_expression`
  (JS grammar). Go uses `selector_expression` (operand + field). ~95% of Go call
  edges were silently dropped.
- Added `_go_callee_name()` handling `selector_expression`.
- end_of_eden edge count: 211 → 3808 [V]

Rust fix -- commit 405bb31 [V]
- `_rust_callee_name` for `field_expression` was returning only the field name
  (e.g. `init` from `s.init()`). Now emits `s.init` for consistency with Go.
- ruggrogue edge count: 2037 → 2809 [V]

**Final validated numbers [V]:**
- JS/TS (dnd-dungeon-gen): 112 files, 291 symbols, 974 edges
- Go (end_of_eden): 100 files, 529 symbols, 3808 edges
- Rust (ruggrogue): 45 files, 337 symbols, 2809 edges

**Tests [V]:** 814 passed, 1 skipped (last run this session)

**Architecture question raised (not yet acted on):**
Both bugs (Go selector_expression, Rust field_expression) had the same root cause:
callee extraction borrowed JS logic for non-JS languages. A `LangSpec` refactor
would prevent this class of bug by requiring each language to declare its own
callee extractor. Bart has been informed; decision pending next session.

## NEXT SESSION -- start here

**Decision needed first:** LangSpec refactor vs. proceed to RM54/55.
- Refactor: ~100 lines, closes silent-drop bug class, makes new languages cheap
- Skip: bugs are fixed, RM54/55 can proceed on current code
- Recommended: do the refactor first (it's the right foundation before RM54/55 builds on it)

**If refactor:**
- `LangSpec` dataclass in `language_walker.py` with: fn_node_kinds, fn_name_field,
  callee_extractor, fqdn_builder, builtins, scope_specs
- Shared walk loop replaces `_js_call_edges`, `_go_call_edges`, `_rust_call_edges`
- Structural quirks (Go receivers, Rust impl dedup, JS arrow/object-literal) become hooks
- Run regression suite to verify 814 still pass

**If RM54/55 directly:**
- RM54 depends on RM53 (LanguageWalker must exist) -- it does [V]
- Check TRACKER.md for RM54/55 spec

## Known issues (carried forward)

**LangSpec refactor pending [?]:** Both Go and Rust callee extractors had silent-drop
bugs from borrowing JS logic. Fixed individually; systemic fix (LangSpec) not yet done.

**RM21 probes not re-run [?]:** Live LLM probe not re-run this session.

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
multi-line blocks. Documented in CLAUDE.md + memory.

**JS/TS _persist_graph_edges ordering trap [V]:** Step 5c MUST come after step 5.
Empty Python graph hits legacy full-delete path and wipes JS/TS edges if inserted earlier.

**Go selector_expression [V]:** Fixed 702dbce. _go_callee_name() handles it. Do not
use _js_callee_name for Go -- Go grammar uses selector_expression not member_expression.

**Rust field_expression receiver [V]:** Fixed 405bb31. _rust_callee_name emits
"receiver.method" not just "method" for field_expression nodes.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
