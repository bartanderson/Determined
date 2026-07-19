Written at commit: 0c7855a

# SESSION STATE — session 216
Written at commit: 0c7855a (2026-07-19)

## Active branch: main [V]

## What happened this session

**RM59 confirmed done [V]** — SESSION_STATE said "check RM59", TRACKER shows DONE 2026-07-15. No action.

**FOREWARNING BFS investigation [V]**
Root cause was two separate bugs discovered in sequence:

1. **parse_ast.py caller FQN was always bare [V — 0c7855a]**
   - `visit_FunctionDef` set `current_function = node.name`, dropping class context
   - `WorldAI.__init__` stored as `__init__` in graph_edges caller column
   - Fix: `current_function = f"{class_name}.{name}" if class_name else name`
   - Both `Visitor` (call edges) and `_Visitor` (function-reference edges) fixed
   - `param_type_map` keyed by bare name (FunctionRepresentation has no class_name);
     lookups now fall back to bare name with `.rsplit(".", 1)[-1]`
   - 91 parse_ast regression tests pass [V]
   - dj2 re-ingested via `socket.emit("ingest", {path: "C:\\Users\\bartl\\dev\\dj2"})` [V]
   - Edge confirmed: `WorldAI.__init__ -> WorldAI._register_world_tools` [V]

2. **FOREWARNING BFS context not resolved to FQN [V — 0c7855a]**
   - BFS queried `WHERE caller = '__init__'` — ambiguous, LIMIT 10 cut off before the right edge
   - Fix: resolve context via `functions` table to `ClassName.method` before BFS
   - Also added `OR name = bare` to stub match query (bare names in functions table
     didn't match partially-qualified callees like `WorldAI._register_world_tools`)
   - FOREWARNING fires: `context=WorldAI.__init__` → FOREWARNING: `_register_world_tools` [V]

**Lessons [V]**
- Caller FQN stripping was a design flaw in parse_ast from the beginning — hidden because
  no tool previously queried graph_edges by qualified caller name
- Re-ingest is always required after parse_ast changes; correct method:
  `socket.emit("ingest", {path: "C:\\Users\\bartl\\dev\\dj2"})` in browser console
- HISTORY.md updated with both lessons [V]

**FOREWARNING simplified [V]**
- Removed `_is_blocked` filter from FOREWARNING (was too restrictive — dj2 stubs don't
  have prereq language in docstrings). Now fires on any stub in callee chain.
- LIMIT reverted to 10 (was temporarily raised to 50 during debugging, now correct)

## Tests [V = verified this session, ? = recalled]

- 91 parse_ast regression tests pass [V]
- Full suite not run [?]

## Known issues [V = verified, ? = recalled]

**BFS probe not yet run [V]:** After re-ingest with qualified callers, the 6 canonical
convergence probes have NOT been re-run against dj2. Any tool querying
`WHERE caller = bare_name` may now silently fail. Probe script ready at:
`scratchpad/probe_dj2.py` — run this FIRST next session before anything else.

**RM68 subrace dead code [?]:** dj2 game work, deferred by policy.
**Shape index symbols [?]:** stub names only; prereq map concept names may not be clickable.
**Server start command [V]:** must use `.venv\Scripts\python.exe`, NOT system pyenv Python.

## NEXT SESSION — start here

**Step 1 (CRITICAL — do before any other work):**
Run the convergence probe against freshly re-ingested dj2 to confirm no tools
broke from the caller FQN change:
```
.venv\Scripts\python.exe "C:\Users\bartl\AppData\Local\Temp\claude\C--Users-bartl-dev-Determined\bc35bcad-9ee9-4977-83ab-40abbca24226\scratchpad\probe_dj2.py"
```
Compare results to CLOSURE.md Phase 2 dj2 section (lines 133-154).

**If a probe fails — triage guide:**
The caller FQN change means graph_edges now stores `ClassName.method` as caller.
Any tool that queries `WHERE caller = bare_name` will now miss class method edges.

- `blast_radius` failure: check how it queries graph_edges — if it uses bare symbol
  name as caller, it needs the same FQN resolution added to FOREWARNING in agent_tools.py
- `walk_call_chain` failure: known TS/JS FQN issue (pre-existing, not from this change).
  For Python: same caller FQN resolution needed.
- `graph_path` failure: check src/dst resolution — may need FQN lookup before BFS.
- Entry point counts changed: expected. EPs are inferred, not from graph_edges caller.
  A count shift is informational, not a regression.
- Stub counts unchanged: functions table unaffected, stubs should be identical.

Pattern to fix any tool: look up symbol in `functions` table, build
`ClassName.method` if `class_name` is set, use that as the query key.
Same pattern as the FOREWARNING fix in agent_tools.py:7672-7684.

**Step 2:** UI redesign arc per `docs/UI_VISION.md`
- Ask bar demotion
- GOT model completeness: do surfaces self-present on corpus load?

**Server start (standing note):** always use `.venv\Scripts\python.exe -m determined.ui.ui_server`
from `C:\Users\bartl\dev\Determined`. Never use pyenv/system Python.
