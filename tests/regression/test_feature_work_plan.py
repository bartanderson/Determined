"""
Regression tests for RM63: feature_work_plan.
Uses in-memory SQLite seeded with a multi-directory fixture.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock
from determined.agent.agent_tools import feature_work_plan, explore_stub


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_assessor(conn):
    oracle = MagicMock()
    oracle.conn = conn
    assessor = MagicMock()
    assessor.oracle = oracle
    return assessor


def _seed_db(conn):
    """
    Feature layout:
      world/combat.py    -> resolve_combat (stub), apply_damage (stub)
      world/ai.py        -> choose_action (stub)
      engine/rules.py    -> roll_dice, check_hit (complete)
      engine/state.py    -> get_state (complete)
      main.py            -> run_game (complete, entry point)

    Call edges (resolved):
      run_game -> resolve_combat   (entry -> stub: establishes EP weight)
      run_game -> choose_action    (entry -> stub)
      resolve_combat -> roll_dice  (stub -> engine: axis = engine)
      resolve_combat -> check_hit  (stub -> engine)
      apply_damage -> get_state    (stub -> engine)
      choose_action -> get_state   (stub -> engine)

    Unresolved edges (missing callees):
      resolve_combat -> missing_helper   (unknown callee)
    """
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            line_number INTEGER,
            is_stub INTEGER DEFAULT 0,
            param_types_json TEXT,
            arguments_json TEXT,
            return_type TEXT,
            docstring TEXT
        );
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            source_id TEXT,
            target_id TEXT,
            caller TEXT,
            callee TEXT,
            line_number INTEGER,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            edge_type TEXT DEFAULT 'static'
        );
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            file_path TEXT
        );
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            base_classes_json TEXT,
            methods_json TEXT
        );
        CREATE TABLE IF NOT EXISTS symbol_references (
            id INTEGER PRIMARY KEY,
            caller TEXT,
            callee TEXT,
            file_path TEXT,
            line_number INTEGER
        );
    """)

    fns = [
        # (name, file_path, line, is_stub, param_types_json, arguments_json, return_type, docstring)
        ("resolve_combat",  "C:/proj/world/combat.py",  10, 1, '{"attacker":"str","defender":"str"}', '["attacker","defender"]', "dict",  "Resolve a combat round between two units."),
        ("apply_damage",    "C:/proj/world/combat.py",  30, 1, '{"target":"str","amount":"int"}',     '["target","amount"]',     "None",  None),
        ("choose_action",   "C:/proj/world/ai.py",      10, 1, '{"unit":"str"}',                     '["unit"]',                "str",   "Choose the next action for an AI unit."),
        ("roll_dice",       "C:/proj/engine/rules.py",  5,  0, '{"sides":"int"}',                    '["sides"]',               "int",   "Roll a die with given sides."),
        ("check_hit",       "C:/proj/engine/rules.py",  15, 0, '{"attack":"int","defense":"int"}',   '["attack","defense"]',    "bool",  "Return True if attack beats defense."),
        ("get_state",       "C:/proj/engine/state.py",  5,  0, '{"key":"str"}',                     '["key"]',                 "Any",   "Retrieve a value from global state."),
        ("run_game",        "C:/proj/main.py",           1,  0, '{}',                                '[]',                      "None",  "Main game loop entry point."),
        ("no_params_stub",  "C:/proj/world/combat.py",  50, 1, '{}',                                '[]',                      "None",  "No parameters stub."),
    ]
    conn.executemany(
        "INSERT INTO functions (name,file_path,line_number,is_stub,param_types_json,arguments_json,return_type,docstring) VALUES (?,?,?,?,?,?,?,?)",
        fns,
    )

    edges = [
        # (caller, callee, caller_file, target_id, resolved)
        ("run_game",       "resolve_combat", "C:/proj/main.py",          "resolve_combat", 1),
        ("run_game",       "choose_action",  "C:/proj/main.py",          "choose_action",  1),
        ("resolve_combat", "roll_dice",      "C:/proj/world/combat.py",  "roll_dice",      1),
        ("resolve_combat", "check_hit",      "C:/proj/world/combat.py",  "check_hit",      1),
        ("apply_damage",   "get_state",      "C:/proj/world/combat.py",  "get_state",      1),
        ("choose_action",  "get_state",      "C:/proj/world/ai.py",      "get_state",      1),
        ("resolve_combat", "missing_helper", "C:/proj/world/combat.py",  None,             0),
    ]
    conn.executemany(
        "INSERT INTO graph_edges (caller,callee,caller_file,target_id,resolved) VALUES (?,?,?,?,?)",
        edges,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def assessor():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    return _make_assessor(conn)


def test_feature_work_plan_returns_stubs(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    assert "resolve_combat" in result
    assert "apply_damage" in result
    assert "choose_action" in result


def test_feature_work_plan_excludes_complete_functions(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    # roll_dice is complete, should never appear as a work item
    assert "roll_dice" not in result
    # run_game may appear as a caller, but should not appear as a stub item header
    lines_with_run_game = [l for l in result.splitlines() if "run_game" in l]
    assert all("Called by" in l or "called by" in l for l in lines_with_run_game), \
        "run_game should only appear as a caller, not as a work item"


def test_feature_work_plan_shows_axes(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    # stubs with no unresolved callees land in the feature's own axis;
    # resolve_combat has missing_helper -> [external] axis
    assert "Axis:" in result
    assert "world" in result.lower() or "[external]" in result


def test_feature_work_plan_shows_callers(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    assert "run_game" in result


def test_feature_work_plan_shows_signature(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    assert "attacker" in result
    assert "dict" in result


def test_feature_work_plan_shows_contract_from_docstring(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    assert "Resolve a combat round" in result


def test_feature_work_plan_infer_flag_when_no_docstring(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    # apply_damage has no docstring -> should emit [infer: ...]
    assert "[infer:" in result


def test_feature_work_plan_shows_missing_callee(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    assert "missing_helper" in result


def test_feature_work_plan_no_stubs_message(assessor):
    result = feature_work_plan(assessor, {"feature_path": "engine"})
    assert "No stubs found" in result


def test_feature_work_plan_missing_feature_path():
    conn = sqlite3.connect(":memory:")
    assessor = _make_assessor(conn)
    result = feature_work_plan(assessor, {})
    assert "ERROR" in result


def test_feature_work_plan_rerun_footer(assessor):
    result = feature_work_plan(assessor, {"feature_path": "world"})
    assert "Re-run after re-ingest" in result


def test_feature_work_plan_empty_params_shows_parens_not_question(assessor):
    # no_params_stub has param_types_json='{}' — should show () not (?)
    result = feature_work_plan(assessor, {"feature_path": "world"})
    lines = [l for l in result.splitlines() if "no_params_stub" in l or
             (result.splitlines().index(l) > 0 and
              "no_params_stub" in result.splitlines()[result.splitlines().index(l)-2:result.splitlines().index(l)])]
    # simpler: the output must not contain (?) anywhere
    assert "(?)" not in result


# ---------------------------------------------------------------------------
# explore_stub tests
# ---------------------------------------------------------------------------

@pytest.fixture
def explore_assessor():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    return _make_assessor(conn)


def test_explore_stub_basic_output(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "resolve_combat"})
    assert "Explore: resolve_combat" in result
    assert "combat.py" in result
    assert "Resolve a combat round" in result


def test_explore_stub_shows_signature(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "resolve_combat"})
    assert "attacker: str" in result
    assert "dict" in result


def test_explore_stub_shows_callers(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "resolve_combat"})
    assert "run_game" in result


def test_explore_stub_no_callers_message(explore_assessor):
    # no_params_stub has no callers in graph_edges
    result = explore_stub(explore_assessor, {"symbol": "no_params_stub"})
    assert "none resolved" in result


def test_explore_stub_sibling_stubs(explore_assessor):
    # resolve_combat and no_params_stub are siblings in world/combat.py
    result = explore_stub(explore_assessor, {"symbol": "resolve_combat"})
    assert "no_params_stub" in result


def test_explore_stub_design_questions_when_no_callers(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "no_params_stub"})
    assert "Design questions" in result
    assert "dead code" in result.lower() or "dynamically" in result.lower()


def test_explore_stub_next_step_hint(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "resolve_combat"})
    assert "completion_contract" in result


def test_explore_stub_missing_symbol(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "nonexistent_fn"})
    assert "not found" in result


def test_explore_stub_requires_symbol_arg(explore_assessor):
    result = explore_stub(explore_assessor, {})
    assert "ERROR" in result


def test_explore_stub_rejects_non_stub(explore_assessor):
    result = explore_stub(explore_assessor, {"symbol": "roll_dice"})
    assert "not a stub" in result


def test_explore_stub_empty_params_shows_parens(explore_assessor):
    # no_params_stub has param_types_json='{}' — should show () not (?)
    result = explore_stub(explore_assessor, {"symbol": "no_params_stub"})
    assert "(?)" not in result
    assert "Signature: ()" in result
