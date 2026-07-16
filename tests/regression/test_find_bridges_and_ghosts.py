"""
Regression tests for RM65 (find_missing_bridges) and RM66 (find_concept_ghosts).
Uses in-memory SQLite seeded with controlled fixtures.
"""
import sqlite3
import json
import pytest
from unittest.mock import MagicMock
from determined.agent.agent_tools import (
    find_missing_bridges,
    find_concept_ghosts,
    _extract_docstring_concepts,
    _concept_base,
)


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
    Fixture layout:
      world/context.py:
        _get_encounter_context(session_id: str) -> dict  [stub]
            docstring: "Query active EncounterFSM for context."
        _get_combat_context(session_id: str) -> dict     [stub]
            docstring: "Query active CombatFSM for context."
        _get_player_info(player_id: str) -> dict         [stub]
            docstring: "Return PlayerState for the given player."

      world/encounter.py:
        generate_encounter(context: dict) -> Encounter   [non-stub]
        Encounter class

      world/player.py:
        get_player(player_id: str) -> PlayerState        [non-stub]
        PlayerState class

    Bridge analysis:
      _get_encounter_context: session_id -> Encounter -- NO bridge (no fn takes session_id and returns Encounter)
      _get_combat_context:    session_id -> Combat    -- NO bridge + NO class (ghost, RM66)
      _get_player_info:       player_id -> PlayerState -- HAS bridge (get_player takes player_id -> PlayerState)
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
            caller TEXT,
            callee TEXT,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            source_id TEXT,
            target_id TEXT,
            line_number INTEGER,
            edge_type TEXT DEFAULT 'static'
        );
        CREATE TABLE classes (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            line_number INTEGER,
            methods_json TEXT,
            base_classes_json TEXT,
            docstring TEXT
        );
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            file_path TEXT
        );
    """)

    stubs = [
        ("_get_encounter_context", "C:/repo/world/context.py", 10, 1,
         json.dumps({"session_id": "str"}), "dict",
         "Query active EncounterFSM for context."),
        ("_get_combat_context", "C:/repo/world/context.py", 20, 1,
         json.dumps({"session_id": "str"}), "dict",
         "Query active CombatFSM for context."),
        ("_get_player_info", "C:/repo/world/context.py", 30, 1,
         json.dumps({"player_id": "str"}), "dict",
         "Return PlayerState for the given player."),
    ]
    conn.executemany(
        "INSERT INTO functions(name, file_path, line_number, is_stub, param_types_json, return_type, docstring) "
        "VALUES(?,?,?,?,?,?,?)", stubs
    )

    non_stubs = [
        ("generate_encounter", "C:/repo/world/encounter.py", 5, 0,
         json.dumps({"context": "dict"}), "Encounter", "Generate a random encounter."),
        ("get_player", "C:/repo/world/player.py", 10, 0,
         json.dumps({"player_id": "str"}), "PlayerState", "Fetch player by id."),
    ]
    conn.executemany(
        "INSERT INTO functions(name, file_path, line_number, is_stub, param_types_json, return_type, docstring) "
        "VALUES(?,?,?,?,?,?,?)", non_stubs
    )

    classes = [
        ("Encounter", "C:/repo/world/encounter.py", 1),
        ("PlayerState", "C:/repo/world/player.py", 1),
    ]
    conn.executemany(
        "INSERT INTO classes(name, file_path, line_number) VALUES(?,?,?)", classes
    )

    conn.commit()


# ---------------------------------------------------------------------------
# _extract_docstring_concepts tests
# ---------------------------------------------------------------------------

def test_extract_compound_camelcase():
    result = _extract_docstring_concepts("Return PlayerState for the given player.")
    assert "PlayerState" in result

def test_extract_fsm_suffix():
    result = _extract_docstring_concepts("Query active CombatFSM for context.")
    assert "CombatFSM" in result

def test_extract_manager_suffix():
    result = _extract_docstring_concepts("Use the SessionManager to retrieve data.")
    assert "SessionManager" in result

def test_extract_excludes_single_word_verbs():
    result = _extract_docstring_concepts("Process pending consequences from past choices")
    assert "Process" not in result

def test_extract_excludes_register():
    result = _extract_docstring_concepts("Register world-specific tools")
    assert "Register" not in result

def test_extract_excludes_system():
    result = _extract_docstring_concepts("OG System doesn't have subraces, return empty list")
    assert "System" not in result

def test_extract_empty():
    assert _extract_docstring_concepts("") == []
    assert _extract_docstring_concepts(None) == []


# ---------------------------------------------------------------------------
# _concept_base tests
# ---------------------------------------------------------------------------

def test_concept_base_strips_fsm():
    assert _concept_base("CombatFSM") == "Combat"

def test_concept_base_strips_manager():
    assert _concept_base("SessionManager") == "Session"

def test_concept_base_no_suffix():
    assert _concept_base("Encounter") == "Encounter"

def test_concept_base_strips_controller():
    assert _concept_base("WorldController") == "World"


# ---------------------------------------------------------------------------
# find_missing_bridges tests
# ---------------------------------------------------------------------------

@pytest.fixture
def assessor(tmp_path):
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    return _make_assessor(conn)


def test_missing_bridges_finds_encounter_gap(assessor):
    result = find_missing_bridges(assessor, {"feature_path": "world/"})
    assert "MISSING_BRIDGE" in result
    assert "_get_encounter_context" in result
    assert "session_id" in result
    assert "Encounter" in result

def test_missing_bridges_no_gap_for_player(assessor):
    # _get_player_info has a bridge (get_player takes player_id -> PlayerState)
    result = find_missing_bridges(assessor, {"feature_path": "world/"})
    assert "_get_player_info" not in result

def test_missing_bridges_combat_not_flagged_as_bridge(assessor):
    # _get_combat_context should NOT appear in missing_bridges because CombatFSM
    # has no matching class (it's a ghost, not a bridge gap)
    result = find_missing_bridges(assessor, {"feature_path": "world/"})
    assert "_get_combat_context" not in result

def test_missing_bridges_no_scope_filter(assessor):
    # Without feature_path, all stubs checked
    result = find_missing_bridges(assessor, {})
    assert "MISSING_BRIDGE" in result

def test_missing_bridges_unknown_path_returns_no_stubs(assessor):
    result = find_missing_bridges(assessor, {"feature_path": "nonexistent/"})
    assert "No stubs found" in result

def test_missing_bridges_all_bridges_present():
    # Corpus where bridge exists for every stub concept
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY, name TEXT, file_path TEXT, line_number INTEGER,
            is_stub INTEGER DEFAULT 0, param_types_json TEXT, return_type TEXT, docstring TEXT
        );
        CREATE TABLE classes (id INTEGER PRIMARY KEY, name TEXT, file_path TEXT, line_number INTEGER,
            methods_json TEXT, base_classes_json TEXT, docstring TEXT);
        CREATE TABLE graph_edges (id INTEGER PRIMARY KEY, caller TEXT, callee TEXT, caller_file TEXT,
            resolved INTEGER, source_id TEXT, target_id TEXT, line_number INTEGER, edge_type TEXT);
        CREATE TABLE files (id INTEGER PRIMARY KEY, file_path TEXT);
    """)
    # Stub: session_id -> Encounter, and bridge exists
    conn.execute(
        "INSERT INTO functions(name, file_path, line_number, is_stub, param_types_json, return_type, docstring) "
        "VALUES(?,?,?,?,?,?,?)",
        ("get_enc", "C:/x/world/a.py", 1, 1, json.dumps({"session_id": "str"}), "dict",
         "Query active EncounterFSM.")
    )
    conn.execute(
        "INSERT INTO functions(name, file_path, line_number, is_stub, param_types_json, return_type, docstring) "
        "VALUES(?,?,?,?,?,?,?)",
        ("fetch_encounter", "C:/x/world/b.py", 5, 0, json.dumps({"session_id": "str"}), "Encounter", "")
    )
    conn.execute("INSERT INTO classes(name, file_path, line_number) VALUES('Encounter','x.py',1)")
    conn.commit()
    a = _make_assessor(conn)
    result = find_missing_bridges(a, {})
    assert "No missing bridges" in result


# ---------------------------------------------------------------------------
# find_concept_ghosts tests
# ---------------------------------------------------------------------------

def test_concept_ghosts_finds_combat_fsm(assessor):
    result = find_concept_ghosts(assessor, {"feature_path": "world/"})
    assert "CONCEPT_GHOST" in result
    assert "_get_combat_context" in result
    assert "CombatFSM" in result

def test_concept_ghosts_encounter_not_ghost(assessor):
    # EncounterFSM's base "Encounter" exists as a class -> not a ghost
    result = find_concept_ghosts(assessor, {"feature_path": "world/"})
    assert "_get_encounter_context" not in result

def test_concept_ghosts_player_state_not_ghost(assessor):
    # PlayerState class exists -> not a ghost
    result = find_concept_ghosts(assessor, {"feature_path": "world/"})
    assert "_get_player_info" not in result

def test_concept_ghosts_unknown_path(assessor):
    result = find_concept_ghosts(assessor, {"feature_path": "nonexistent/"})
    assert "No stubs found" in result

def test_concept_ghosts_no_ghosts_when_all_classes_exist():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY, name TEXT, file_path TEXT, line_number INTEGER,
            is_stub INTEGER DEFAULT 0, param_types_json TEXT, return_type TEXT, docstring TEXT
        );
        CREATE TABLE classes (id INTEGER PRIMARY KEY, name TEXT, file_path TEXT, line_number INTEGER,
            methods_json TEXT, base_classes_json TEXT, docstring TEXT);
        CREATE TABLE graph_edges (id INTEGER PRIMARY KEY, caller TEXT, callee TEXT, caller_file TEXT,
            resolved INTEGER, source_id TEXT, target_id TEXT, line_number INTEGER, edge_type TEXT);
        CREATE TABLE files (id INTEGER PRIMARY KEY, file_path TEXT);
    """)
    conn.execute(
        "INSERT INTO functions(name, file_path, line_number, is_stub, param_types_json, return_type, docstring) "
        "VALUES(?,?,?,?,?,?,?)",
        ("do_combat", "C:/x/world/a.py", 1, 1, json.dumps({"s": "str"}), "dict",
         "Run the CombatFSM.")
    )
    conn.execute("INSERT INTO classes(name, file_path, line_number) VALUES('Combat','x.py',1)")
    conn.commit()
    a = _make_assessor(conn)
    result = find_concept_ghosts(a, {})
    assert "No concept ghosts" in result
