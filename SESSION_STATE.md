Written at commit: 4c466be

# SESSION STATE - session 174
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 174, 2026-07-14)

**Drift from prior handoff (94a1d71 → 42bb97c, 3 commits already in repo):**
- 657dd87: Rust trait dispatch (was next-session item 1, done by prior session)
- 32165fe: JS cross-language bridge improvements
- 42bb97c: TypeScript type annotations + typed receiver call resolution

**18607fc -- External interface annotation [V]**
- load_external_interfaces(root_path) in dynamic_edges.py: reads external_interfaces.json,
  returns {language: {iface_name: [methods]}}. Missing/malformed file returns {}.
- _external_interface_dispatch_pass(cursor, ext_ifaces, language, file_paths): finds corpus
  types implementing ALL declared methods; inserts interface_dispatch edges.
  Go uses "." separator, Rust uses "::". Partial implementors skipped.
- Wired into _persist_js_ts_files after Go/Rust dispatch passes.
- To close tea.Model gap: drop external_interfaces.json at corpus root with tea.Model entry,
  re-ingest → ChoicesModel.Init/Update/View etc. get interface_dispatch callers.
- 13 new tests in test_external_interface_dispatch.py.

**4a20155 -- RM38: JS addEventListener bindings [V]**
- extract_js_addEventListener_bindings(js_src, file_path) in dynamic_edges.py:
  regex _ADDEVENTLISTENER_RE captures elem.addEventListener('event', namedFn) only for
  named function refs (not inline arrow fns). Returns (elem_var, basename.handler, 'js_event_binding').
- Wired into run_cross_language_link: iterates JS files already, now also extracts
  addEventListener bindings and inserts js_event_binding edges.
- Stale JS-file-sourced js_event_binding edges cleared before re-insertion.
- Completes static-linkable DOM→JS handler chain in dj2:
  chatSend.addEventListener('click', sendToAI)
  → js_event_binding: chatSend → world.sendToAI
  → http_fetch: world.sendToAI → flask_handler (pre-existing)
- 6 new tests in test_dynamic_edges.py.
- RM38 marked DONE in TRACKER.md.

**All 877 tests pass [V].**

## NEXT SESSION -- start here

No open items in TRACKER.md. CLAUDE.md active arc items (6, 20, 1) are all done.

Options in order of value:

1. **File new items** -- the Go/Rust/JS/TS arc (RM53-58) is complete. Natural next arc:
   - Better JS call graph for inline arrow functions (currently skipped for addEventListener)
   - Python class attribute call graph (self.x.method() → concrete type via class_attributes table)
   - RM21 probe re-run against dj2/Determined corpora to find remaining LLM reasoning gaps

2. **Validate end-of-eden tea.Model gap** -- create external_interfaces.json at corpus root,
   re-ingest, verify ChoicesModel.Update shows tea.Model.Update as caller.

3. **Add new corpora** -- Java, C#, Kotlin analysis via LanguageWalker (ast-grep supports all,
   zero new plumbing, just pattern sets).

## Known issues (carried forward)

**interface_dispatch caller_file empty [V]:** Interface types not in functions table,
  so caller_file on interface_dispatch edges is "". Skipped by find_clusters source-file lookup.

**Bubble Tea tea.Model external [V]:** Fixed by external_interfaces.json (see above).
  No file created yet for end-of-eden corpus -- needs a re-ingest to activate.

**addEventListener arrow fn not captured [V]:** inline arrow callbacks to addEventListener
  are not extractable statically. Named fn refs only. Known limitation.

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
multi-line blocks.

**JS/TS _persist_graph_edges ordering trap [V]:** Step 5c MUST come after step 5.

**normalize_symbol strips :: [V]:** "Module::Fn" -> "Fn". Correct for target_id lookup
but loses type context on Rust FQDNs. Watch for unintended consequences.

**graph_edges no provenance column [V]:** cross_language linker uses edge_type='cross_language'.

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
