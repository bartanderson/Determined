Written at commit: 89d55e2

# SESSION STATE - session 174
_Overwrite completely each session. Not authoritative -- see docs/TRACKER.md for truth._

## Active branch: main [V]

## What happened this session (session 174, 2026-07-14)

**18607fc -- External interface annotation [V]**
- load_external_interfaces(root_path): reads external_interfaces.json at corpus root,
  returns {language: {iface_name: [methods]}}. Go uses ".", Rust uses "::".
- _external_interface_dispatch_pass(): finds corpus types implementing ALL declared methods,
  inserts interface_dispatch edges.
- Wired into _persist_js_ts_files after Go/Rust dispatch passes.
- 13 new tests in test_external_interface_dispatch.py.

**4a20155 -- RM38 done: JS addEventListener bindings [V]**
- extract_js_addEventListener_bindings(js_src, file_path): named function refs only
  (not inline arrow fns). Returns (elem_var, basename.handler, 'js_event_binding').
- Wired into run_cross_language_link.
- 6 new tests in test_dynamic_edges.py. RM38 marked DONE in TRACKER.md.

**All 877 tests pass [V]. No open items in TRACKER.md [V].**

**Corpus evaluation (read-only, no DB changes) [V]:**

| Corpus | Symbols | Edges | Resolution | Orphans | Data flow | Dispatch |
|--------|---------|-------|-----------|---------|-----------|----------|
| end-of-eden (Go) | 533 | 3,346 | 15.6% | 51.8% | 0 | 41 iface |
| ruggrogue (Rust) | 337 | 2,331 | 7.5% | 73.3% | 0 | 4 trait |
| dj2 (Python+JS) | 1,321 | 9,860 | 13.4% | 52.3% | 1,611 | 0 |
| Determined (Python) | 1,403 | 10,677 | 6.0% | 77.3% | 0 | 18 poly |

## NEXT SESSION -- start here

**Step 0 (do first): re-ingest dj2 and Determined**

dj2 DB mtime 2026-07-13 14:18 -- predates commits 32165fe (cross_language fix) and 4a20155
(addEventListener bindings). Currently shows http_fetch=32 but cross_language=0, which is
wrong. Re-ingest via UI (load corpus → ingest dj2 path) to get:
  - cross_language edges (was 0, should match http_fetch count)
  - js_event_binding from addEventListener (new this session)

Determined DB also stale: shows data_flow=0 despite Python data_flow being fully implemented.
Re-ingest Determined corpus to populate data_flow edges.

**Gaps to address after re-ingest (in priority order):**

1. **Go/Rust typed params** -- LanguageWalker needs _go_param_types() and _rust_param_types()
   so param_types_json is populated (currently 0% for both). Enables type-guided resolution.
   Pattern: `func (r ReceiverType) Method(arg ArgType)` → param_types_json stores ArgType.
   Mirrors _ts_param_types() added for TypeScript.

2. **Go/Rust data_flow** -- LanguageWalker has no data_flow_edges() for Go/Rust.
   L1 (inline arg): `fnB(fnA())`, L2 (var bind): `x := fnA(); fnB(x)`.
   Mirrors the JS data_flow implemented in RM55.

3. **JS corpora not ingested** -- dnd-dungeon-gen, dungeoncrawler, rotjs exist at
   C:\Users\bartl\dev\corpora\ but have no DBs. Ingest via UI to validate JS/TS pipeline.

4. **external_interfaces.json for ruggrogue** -- common Rust stdlib traits (Iterator, Display,
   From, Into) declared externally would add trait_dispatch edges. Currently only 4.

5. **Resolution rate improvement** -- Go/Rust resolution at 7-16% is mostly external stdlib
   calls (expected unresolved) but also includes in-corpus method calls that fail to match
   because receiver type isn't tracked. Typed params (item 1 above) would help here.

## Known issues (carried forward)

**dj2 DB stale [V]:** cross_language=0 despite http_fetch=32. Re-ingest fixes.
**Determined DB stale [V]:** data_flow=0 despite Python data_flow implemented. Re-ingest fixes.
**JS corpora not ingested [V]:** dnd-dungeon-gen, dungeoncrawler, rotjs have no DBs.
**Go/Rust orphan rate inflated [V]:** High orphan % partly caused by unresolved edges not
  counting for in-degree. Not a false positive -- genuine external calls are unresolved.

**interface_dispatch caller_file empty [V]:** Interface types not in functions table.
**addEventListener arrow fn not captured [V]:** Inline arrow callbacks not statically linkable.
**RM21 probes not re-run [?]:** Live LLM probe not re-run.
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

LLM server: llama-server.exe on port 8081 with Qwen3-8B-Q4_K_M.gguf, --ctx-size 32768.
