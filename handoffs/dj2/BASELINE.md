# dj2 baseline (tasks 1.1 - 1.4)

Measured 2026-10-04 in a Linux cloud session. dj2 is public; the clone is read-only.

- `base_sha` (dj2 origin/main): `598ed551d0538c1129c75aec0f708b20205c80af`  (matches the proposal)
- dj2 clone status after all test runs: clean (`git status --short` empty), HEAD == base_sha

## 1.1 Determined on Linux

- OS: Linux 6.18 (cloud container), Python 3.11.15, venv at `.venv/` (gitignored)
- Install: `pip install -e ".[dev]"`. Not declared in pyproject but needed by tests:
  `ast-grep-py`, `tree-sitter`, `tree-sitter-lua`, `flask`, `flask-socketio`.
- `tools/run_tests.py --files determined/agent/agent_tools.py`:
  first run 1 failed / 374 passed (missing ast-grep-py, not a Windows issue);
  after installing the packages above: **471 passed, 8 deselected**.
- `tools/run_tests.py --list` with no changes: "No changed source files detected."
- Note: `determined/agent/graph_utils.py` has no FILE_MAP entry in `tools/run_tests.py`.

## 1.3 Ingest and dj2 test classification

- Ingest: `python tools/ingest_lang_corpus.py <dj2 clone>` -> 156 Python files, 1411 symbols, 492 edges.
  DB `home_user_bartanderson_dj2.db` (gitignored); paths resolve on Linux.
- TRAP: `tools/ingest_lang_corpus.py` does NOT run the FSM-config pass (`ingest_fsm_pass`);
  only `EngineRunner` does. Without it the 12 FSM stubs are invisible. Ran the pass by hand
  (45 FSM symbols added). Fix or use EngineRunner before relying on the numbers.
- dj2 has no declared minimal test deps; `requirements.txt` is a full freeze. Tests were run with
  only pytest, pyyaml and simpleeval installed (no psycopg2, PIL, pgvector, mcp).

41 test files: 5 pass headless, 30 need a dep, 6 fail. 5 + 30 + 6 = 41.

| result | files |
|---|---|
| passes headless (5) | tests/unit/test_event_log.py (8), tests/integration/test_escalation_edge_cases.py (3), test_multi_rules.py (1), test_reputation_chain.py (1), test_rule_ordering.py (1) |
| needs psycopg2 / Postgres (4) | tests/integration/test_economy.py, tests/unit/test_context_builder.py, tests/unit/test_dm_chat_handler_creation.py (psycopg2); tests/test_ai.py, tests/test_tool_system.py (pgvector) |
| import a module that does not exist (3) | test_encounter_fsm.py -> `world.fsm.encounter_machine`; tests/test_trade_fsm.py -> `world.fsm.trade_machine`; tests/test_intent_classification.py -> `world.dm_chat_ai` |
| import `tools` / `world.intent_manager` etc. (legacy) | root test_*.py (context_packet, dependency_graph, local_graph, module_resolution, query_entry, symbols, visualize_graph, intent), tests/test_all_tools, test_deepseek, test_test_read, test_tools_basic, tools.old/* |
| needs PIL / mcp | test_terrain.py (PIL), tools.old/future/test_server.py (mcp) |
| fails (6) | dungeon_neo/test_campaign.py, tests/test_character_builder.py (8 failed), tests/test_encounter_gen.py, tools.old/analysis/test_templates.py, tools.old/test_ollama_simple.py (no tests collected), tests/unit/test_escalation_engine.py (3 failed: `EscalationEngine.__init__() missing 'world_controller'`, stale test) |

Raw per-file output: not committed (scratch). Re-run with the classifier if needed.

## 1.4 Wave re-measure (after the FSM pass)

| | proposal | measured now |
|---|---|---|
| incomplete symbols (`implementation_order`) | 25 | 25 |
| FSM guards/actions | 12 | 12 (barter 3, encounter 5, trade 4) |
| context-builder stubs | 2 | 2 (`_get_combat_context` :196, `_get_encounter_context` :191) |
| other | 11 | 11 (3 FSM-test mocks/tests, `_register_world_tools`, `on_arc_completed`, `process_consequences`, 5 `dnd_data.py` subrace/fighting-style) |

No difference from the proposal; design D5 order is unchanged.

## New facts that affect the design

1. `world/fsm/` holds only `builtins.py`, `generic_fsm.py`, `schemas/`. The tests
   `test_encounter_fsm.py` and `tests/test_trade_fsm.py` import `encounter_machine` / `trade_machine`
   modules that do not exist. The FSMs are generic and JSON-driven, so those modules may be the
   expected home for guards/actions or the tests may be stale. Decide before work order 002.
2. Only `test_event_log.py` plus 4 escalation integration tests run headless. That is the regression
   floor for the prefix check (task 4.1a).
