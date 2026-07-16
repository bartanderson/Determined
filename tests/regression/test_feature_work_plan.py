"""
Regression tests for RM63: feature_work_plan.
Uses in-memory SQLite seeded with a multi-directory fixture.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock
from determined.agent.agent_tools import feature_work_plan


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
        ("resolve_combat",  "C:/proj/world/combat.py",  10, 1, '{"attacker":"str","defender":"str"}', "dict",  "Resolve a combat round between two units."),
        ("apply_damage",    "C:/proj/world/combat.py",  30, 1, '{"target":"str","amount":"int"}',     "None",  None),
        ("choose_action",   "C:/proj/world/ai.py",      10, 1, '{"unit":"str"}',                     "str",   "Choose the next action for an AI unit."),
        ("roll_dice",       "C:/proj/engine/rules.py",  5,  0, '{"sides":"int"}',                    "int",   "Roll a die with given sides."),
        ("check_hit",       "C:/proj/engine/rules.py",  15, 0, '{"attack":"int","defense":"int"}',   "bool",  "Return True if attack beats defense."),
        ("get_state",       "C:/proj/engine/state.py",  5,  0, '{"key":"str"}',                     "Any",   "Retrieve a value from global state."),
        ("run_game",        "C:/proj/main.py",           1,  0, '{}',                                "None",  "Main game loop entry point."),
    ]
    conn.executemany(
        "INSERT INTO functions (name,file_path,line_number,is_stub,param_types_json,return_type,docstring) VALUES (?,?,?,?,?,?,?)",
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
