# SESSION STATE - session 35 handoff
_Overwrite completely each session. Not authoritative - see Determined/docs/TRACKER.md for truth._

## What happened this session (session 35)

**Item 6 done: incremental per-file re-ingest.**
**Item 20 done: call graph accuracy via annotation exploitation.**

### Item 6
- `determined/ingestion/reingest_file.py`: FileDelta in-memory scratchpad,
  compute_file_delta, apply_file_delta, reingest_file entry point
- Inserts new symbol rows first, deletes stale old rows after -- no broken
  intermediate state during update
- Inbound edges to removed symbols become honest dangling references
- Fixed _insert_symbol to INSERT OR IGNORE (was plain INSERT -- latent bug)
- Wired as agent tool reingest_file(file_path), CLI --reingest-file FILE, REGISTRY
- 6 new regression tests

### Item 20
- Phase 1a: _extract_functions captures arg annotations -> param_types dict on
  FunctionRepresentation; persisted as param_types_json in functions table
- Phase 1b: _extract_class_attributes extracts self.x: Foo and self.x = Foo()
  from __init__; stored in new class_attributes table; DBOracle.get_class_attribute_type()
- Phase 2: Visitor tracks current_class; obj.method() with annotated param ->
  TypeName.method (resolved=True); self.method() -> ClassName.method (resolved=True);
  self.attr.method() with known attr type -> Type.method (resolved=True)
  SymbolReference.resolved, GraphEdge.resolved, graph_edges.resolved column all wired
- Phase 3: list_callers/list_callees tag annotation-resolved edges; describe_file
  shows % resolved stat
- 13 new regression tests

### Totals
296 pass, 1 pre-existing Windows file-handle flake

## FIRST THING NEXT SESSION

Pick from TRACKER.md open items. Only small items remain:
- Item 1 (files.role) -- small, low risk; parse_ast.py sets role=None
- Items 2, 3 -- LOW, revisit only if needed in real use

Per CLAUDE.md: read docs/sots.md before planning (already read this session).

## Current state

Branch: main (Determined), committed (not pushed - Bart pushes)
Tests: 296 pass (+ 1 pre-existing Windows file-handle flake in test_intent_layer_ab.py)
Items done: 22, 23, 24, 25, 8, 14, 15, 9, 10, 19, knowledge.db elimination, 7, 6, 20
Remaining open items: 1 (LOW), 2 (LOW), 3 (LOW), 11/13/14 (FUTURE)

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
dj2: C:\Users\bartl\dev\dj2, separate venv
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Use PowerShell tool (not Bash) for all server/Python commands.
Active branch: main (Determined)
