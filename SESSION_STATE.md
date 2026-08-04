Written at commit: 7b86ecf

# SESSION STATE — session 294 handoff

## Active branch: main [V]
## Working tree: one unstaged edit (TRACKER.md — RM-Perf static tier note)

---

## WHAT HAPPENED THIS SESSION

RM-Perf static tier complete. Both remaining items shipped. [V]

---

## DONE THIS SESSION

**`find_stable_layouts`** (commit bf478f8) [V]:
AST-based. Queries `classes` table, reads source files, walks `__init__` and
all other methods, collects `self.attr` assignments. Classes where no init attr
is mutated elsewhere = stable layout = `__slots__`/frozen-dataclass candidate.
- `_is_self_attr` / `_collect_self_attrs` helpers (scope-aware, don't cross nested defs)
- `_fp_label` module-level helper (last 2 path components, shared by both tools)
- On Determined: 47/57 stable, 10 mutable. `BagStore`, `ClassificationContract`, etc.
  flagged `[slot]`. `Assessor`, `DBOracle`, `Visitor` correctly mutable.
- TOOL_REGISTRY + tool_registry.py REGISTRY + Workbench "Architecture" tile
- 5 tests pass [V]

**`find_dead_event_handlers`** (commit 7b86ecf) [V]:
Queries `function_reference` edges (Thread/kwarg callbacks; filters dotted-name
noise like `judgment.verdict` by requiring bare callee names) and `decorator`
edges (`__js_client__`/`__http_client__` synthetic callers from parse_ast.py
for Socket.IO/Flask). Subtracts functions that also have any non-callback edge.
Tags `[dec]` (decorator-registered) vs `[ref]` (argument-passed).
- On Determined: 58 results — all 50+ socket.io `handle_*` and Flask routes
  (`[dec]`), plus `_run`, `_auto_orient`, `_start_llm_server` Thread targets (`[ref]`)
- Prereq (`function_reference` + `decorator` edge types) was already in DB from a prior session
- TOOL_REGISTRY + tool_registry.py REGISTRY + Workbench "Architecture" tile
- 4 tests pass [V]

TRACKER.md RM-Perf section updated: static tier marked DONE 2026-08-04. [?] (not committed yet)

---

## REMAINING OPEN ITEMS

**RM-Perf profile-grounded tier** (next for RM-Perf): hot-path dominance,
repeated recomputation on hot edges. Requires cProfile instrumentation hook
producing `call_samples` table. No design yet. Estimated 2-3 sessions.

**RM21** — gated on real multi-hop failure. Don't start.
**RM76** — gated on Bart saying "record this decision." Don't start.
**RM73, RM77** — FUTURE.

---

## WHAT TO DO NEXT SESSION

1. Commit the TRACKER.md edit (or fold into the session wrap commit).
2. Ask Bart: start profile-grounded tier (cProfile hook), or different priority?
   If profile-grounded: first step is designing `call_samples` table schema and
   a cProfile injection wrapper, likely a new `determined/profiling/` module.

---

## KNOWN TRAPS (carried forward)

- Cytoscape containers need `position:relative;overflow:hidden`. [V s290]
- `llm_client.chat()` reasoning_content fallback removed — don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains `\n` (raw JS code). [V s291]
- `_wrap_body()` must be in sketch_stub.py wherever body fragments are parsed. [?]
- `line_number=0` trap: exclude from ORDER BY queries on functions table. [?]
- pytest `-m` on CLI REPLACES addopts — never pass `-m` by hand. [V]
- Old corpus DBs may lack `http_route`/`is_tool`/`is_stub` columns — handle gracefully. [V s293]
- `find_dead_event_handlers`: dotted callee names (e.g. `judgment.verdict`) are
  false positives from dict-literal detection in `_extract_function_references`
  in parse_ast.py. Filtered at query time by `'.' not in callee`. The source-level
  visitor remains noisy — tighten in a future session if needed. [V s294]
- `classes` DB table has duplicate rows for the same class in some files (e.g.
  commonplace `extractor.py` appears 3x). `find_stable_layouts` deduplicates by
  name per file (first-occurrence wins). [V s294]

## RESOURCE / PROCESS RULES [V]

- Test runner: `tools/run_tests.py` only. Never pytest directly, never full suite.
- UI server restart: kill PID on 5050, then preview_start {name: "Determined UI"}.
- Duplicate server trap: `netstat -ano | Select-String "TCP.*:5050.*LISTENING"`.
