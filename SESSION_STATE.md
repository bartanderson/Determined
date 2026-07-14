Written at commit: 94a1d71

# SESSION STATE - session 173
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 173, 2026-07-14)

**Four Go/Rust analysis bug fixes -- all committed [V]:**

**c0cfe75 -- Rust self.method() calls silently dropped [V]**
- Root cause: "self" was in _RUST_BUILTINS; the base-left-of-dot filter
  hit "self" for any self.method() call and dropped the edge entirely.
- Fix: _rust_callee_name now special-cases val_kind == "self" -- checks
  the method name (right side) against _RUST_BUILTINS; returns bare method
  name if not stdlib. Removed "self" from _RUST_BUILTINS.
- Impact: ruggrogue 2259 -> 2327 edges after re-ingest.

**1a7a085 -- caller/callee file_path and line_number null for Go/Rust [V]**
- Root cause: _list_callers_raw and _list_callees_raw joined only on
  symbol_references (Python-only table); Go/Rust rows returned NULL.
- Fix: added LEFT JOIN on functions keyed by caller/callee name; COALESCE
  picks sr.file_path first, falls back to f.file_path. Same for line_number.
- After fix: Go/Rust callers show real file paths and function definition lines.

**096713f -- find_clusters returning empty for Go/Rust [V]**
- Root cause: file_map keyed by FQDN (functions.name) but source_id in
  graph_edges is normalized bare name -- 0 matches, 0 clusters.
- Fix: file_map now indexed by FQDN AND bare name (like most_connected);
  uses caller column (FQDN, always matches functions.name) for source file,
  target_id (bare) for dest file via bare-name entries.
- After fix: end-of-eden returns 155 clusters (lua.go<->session.go at 75).

**94a1d71 -- Go interface dispatch [V]**
- LanguageWalker.interface_types(): parses Go "type X interface { }" nodes,
  returns {iface_name: [method_names]}. Called per file during ingestion.
- _go_interface_dispatch_pass(): after all files ingested, finds concrete
  types that fully implement each interface, inserts interface_dispatch edges.
  target_id stores FQDN (not bare) so list_callers matches specific type.
- end-of-eden: 41 dispatch edges from 2 interfaces:
  Settings -> Browser, Viper, empty, settings (10 methods each)
  Menu -> MenuBase (1 method)
- Browser.LoadSettings now shows Settings.LoadSettings as caller [V].
- tea.Model is external (bubbletea library) -- not in corpus, not detectable.
  ChoicesModel.Update etc. remain in_degree=0; that's an honest gap.

**Corpora after this session [V]:**
- end-of-eden: 533 symbols, 3346 edges, 109 files
- ruggrogue: 337 symbols, 2327 edges, 46 files

**All 831 tests pass [V].**

## NEXT SESSION -- start here

No specific next tasks flagged. Carry-forward options in order of value:

1. **Rust trait dispatch** -- same pattern as Go interface dispatch but for
   Rust "trait Foo { fn method(...) }" + "impl Foo for Type { }". Would
   connect trait implementors the way Go interfaces now work.
2. **External interface annotation** -- add a way to declare external interfaces
   (e.g. tea.Model: Init/Update/View) in virtual_edges.json so that
   ChoicesModel.Update etc. get interface_dispatch callers even for library
   interfaces not in the corpus.
3. **Active work arc items 6, 20, 1** -- see CLAUDE.md for details.

## Known issues (carried forward)

**caller file/line null for Go/Rust [V]:** FIXED this session (1a7a085).
  File and line now fall back to functions table for Go/Rust callers.

**find_clusters empty for Go/Rust [V]:** FIXED this session (096713f).

**Rust self.method() dropped [V]:** FIXED this session (c0cfe75).

**interface_dispatch caller_file empty [V]:** Interface types are not in
  functions table, so caller_file on interface_dispatch edges is "". These
  edges are skipped by find_clusters source-file lookup. Callers of concrete
  implementations do show the interface as caller in list_callers [V].

**Bubble Tea tea.Model external [V]:** ChoicesModel/DamageAnimationModel etc.
  Update/View/Init methods remain in_degree=0. External library interface --
  requires annotation or structural inference to fix.

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

**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Correct for target_id lookup
but loses type context on Rust FQDNs. Watch for unintended consequences.

**graph_edges no provenance column [V]:** cross_language linker uses edge_type='cross_language'.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
