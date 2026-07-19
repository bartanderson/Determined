# tests/regression/test_corpus_projections.py
#
# Regression tests for RM69 Phase 2: corpus-level projections.
# Uses in-memory SQLite — no live corpus required.

import json
import sqlite3
import pytest

from determined.agent.corpus_projections import (
    stub_file_shape,
    stub_subsystem_shape,
    stub_prerequisite_map,
    stub_concept_ghost_map,
    _extract_prerequisites,
    _dominant,
    _dir_key,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_db(stubs=None, non_stubs=None, classes=None):
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE functions (
            name TEXT, file_path TEXT, line_number INTEGER,
            docstring TEXT, param_types_json TEXT, return_type TEXT,
            is_stub INTEGER DEFAULT 0, is_tool INTEGER DEFAULT 0,
            decorators_json TEXT, arguments_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE classes (
            name TEXT, file_path TEXT,
            base_classes_json TEXT, docstring TEXT, methods_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT, callee TEXT, caller_file TEXT,
            edge_type TEXT DEFAULT 'static', resolved INTEGER DEFAULT 0,
            source_id TEXT, target_id TEXT
        )
    """)
    conn.execute("CREATE TABLE files (file_path TEXT, line_count INTEGER)")

    for s in (stubs or []):
        conn.execute(
            "INSERT INTO functions VALUES (?,?,?,?,?,?,1,0,NULL,NULL)",
            (s.get("name"), s.get("file_path", "world/test.py"),
             s.get("line_number", 10), s.get("docstring"),
             json.dumps(s.get("params", {})), s.get("return_type"))
        )
    for n in (non_stubs or []):
        conn.execute(
            "INSERT INTO functions VALUES (?,?,?,?,?,?,0,0,NULL,NULL)",
            (n.get("name"), n.get("file_path", "world/test.py"),
             n.get("line_number", 1), n.get("docstring"),
             json.dumps(n.get("params", {})), n.get("return_type"))
        )
    for c in (classes or []):
        conn.execute(
            "INSERT INTO classes VALUES (?,?,?,?,?)",
            (c.get("name"), c.get("file_path", "world/test.py"),
             json.dumps(c.get("base_classes", [])),
             c.get("docstring"), json.dumps(c.get("methods", [])))
        )
    conn.commit()
    return conn


class _FakeOracle:
    def __init__(self, conn):
        self.conn = conn
    def get_project_root(self):
        return "C:/fake"


class _FakeAssessor:
    def __init__(self, conn):
        self.oracle = _FakeOracle(conn)


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def test_extract_prerequisites_blocked_on():
    results = _extract_prerequisites("blocked on AIDungeonMaster to handle responses")
    assert "AIDungeonMaster" in results


def test_extract_prerequisites_until_built():
    results = _extract_prerequisites("STUB: returns empty until CombatFSM is built")
    assert "CombatFSM" in results


def test_extract_prerequisites_waiting_on():
    results = _extract_prerequisites("waiting on ActionQueue implementation")
    assert "ActionQueue" in results


def test_extract_prerequisites_no_match():
    results = _extract_prerequisites("pass")
    assert results == []


def test_extract_prerequisites_deduplicates():
    results = _extract_prerequisites(
        "blocked on CombatFSM; also blocked on CombatFSM"
    )
    assert results.count("CombatFSM") == 1


def test_extract_prerequisites_skips_noise():
    results = _extract_prerequisites("until The implementation is ready")
    assert "The" not in results


def test_dominant_single():
    assert _dominant(["blocked-on-prerequisite"] * 3) == "blocked-on-prerequisite"


def test_dominant_tie_returns_mixed():
    assert _dominant(["blocked-on-prerequisite", "concept-not-applicable"]) == "mixed"


def test_dominant_empty():
    assert _dominant([]) == "unknown"


def test_dir_key():
    assert _dir_key("world/ai/dungeon_master.py") == "world/ai"
    assert _dir_key("world/foo.py") == "world"


# ---------------------------------------------------------------------------
# stub_file_shape
# ---------------------------------------------------------------------------

def test_file_shape_no_stubs():
    conn = _make_db()
    result = stub_file_shape(_FakeAssessor(conn), {})
    assert "no stubs" in result


def test_file_shape_groups_by_file():
    conn = _make_db(stubs=[
        {"name": "stub_a", "file_path": "world/ai.py"},
        {"name": "stub_b", "file_path": "world/ai.py"},
        {"name": "stub_c", "file_path": "world/data.py"},
    ], non_stubs=[
        {"name": "real_a", "file_path": "world/ai.py"},
    ])
    result = stub_file_shape(_FakeAssessor(conn), {})
    assert "ai.py" in result
    assert "data.py" in result


def test_file_shape_density_calculation():
    """3 stubs / 4 total = 75% density."""
    conn = _make_db(
        stubs=[
            {"name": "s1", "file_path": "world/ai.py"},
            {"name": "s2", "file_path": "world/ai.py"},
            {"name": "s3", "file_path": "world/ai.py"},
        ],
        non_stubs=[{"name": "real", "file_path": "world/ai.py"}],
    )
    result = stub_file_shape(_FakeAssessor(conn), {})
    assert "75%" in result


def test_file_shape_scope_filters():
    conn = _make_db(stubs=[
        {"name": "stub_a", "file_path": "world/ai.py"},
        {"name": "stub_b", "file_path": "engine/runner.py"},
    ])
    result = stub_file_shape(_FakeAssessor(conn), {"scope": "world"})
    assert "ai.py" in result
    assert "runner.py" not in result


def test_file_shape_shows_verdict():
    conn = _make_db(stubs=[{
        "name": "stub_a",
        "file_path": "world/ai.py",
        "docstring": "This would generate narrative when the LLM layer is wired.",
    }])
    result = stub_file_shape(_FakeAssessor(conn), {})
    assert "verdict:" in result


def test_file_shape_sorted_by_density():
    """File with all stubs should rank above file with one stub."""
    conn = _make_db(
        stubs=[
            {"name": "s1", "file_path": "world/dense.py"},
            {"name": "s2", "file_path": "world/dense.py"},
            {"name": "s3", "file_path": "world/sparse.py"},
        ],
        non_stubs=[
            {"name": "r1", "file_path": "world/sparse.py"},
            {"name": "r2", "file_path": "world/sparse.py"},
            {"name": "r3", "file_path": "world/sparse.py"},
            {"name": "r4", "file_path": "world/sparse.py"},
        ],
    )
    result = stub_file_shape(_FakeAssessor(conn), {})
    assert result.index("dense.py") < result.index("sparse.py")


def test_file_shape_excludes_test_files():
    """Stubs under test_ paths must not appear in shape output."""
    conn = _make_db(stubs=[
        {"name": "real_stub", "file_path": "world/ai.py"},
        {"name": "test_helper", "file_path": "tests/test_encounter_fsm.py"},
        {"name": "test_econ", "file_path": "tests/test_economy.py"},
        {"name": "win_stub", "file_path": "tests\\test_windows.py"},
    ])
    result = stub_file_shape(_FakeAssessor(conn), {})
    assert "ai.py" in result
    assert "test_encounter_fsm" not in result
    assert "test_economy" not in result
    assert "test_windows" not in result


# ---------------------------------------------------------------------------
# stub_subsystem_shape
# ---------------------------------------------------------------------------

def test_subsystem_shape_no_stubs():
    conn = _make_db()
    result = stub_subsystem_shape(_FakeAssessor(conn), {})
    assert "no stubs" in result


def test_subsystem_shape_groups_by_directory():
    conn = _make_db(stubs=[
        {"name": "s1", "file_path": "world/ai.py"},
        {"name": "s2", "file_path": "world/data.py"},
        {"name": "s3", "file_path": "engine/runner.py"},
    ])
    result = stub_subsystem_shape(_FakeAssessor(conn), {})
    assert "world/" in result
    assert "engine/" in result


def test_subsystem_shape_shows_verdict():
    conn = _make_db(stubs=[{
        "name": "stub_a", "file_path": "world/ai.py",
    }])
    result = stub_subsystem_shape(_FakeAssessor(conn), {})
    assert "verdict:" in result


def test_subsystem_shape_scope_filter():
    conn = _make_db(stubs=[
        {"name": "s1", "file_path": "world/ai.py"},
        {"name": "s2", "file_path": "engine/runner.py"},
    ])
    result = stub_subsystem_shape(_FakeAssessor(conn), {"scope": "world"})
    assert "world/" in result
    assert "engine/" not in result


def test_subsystem_shape_design_skeleton_verdict():
    """Stubs with blocked-on-prerequisite as dominant -> design-skeleton."""
    from determined.agent.corpus_projections import _subsystem_verdict
    classifications = ["blocked-on-prerequisite"] * 4 + ["genuinely-unknown"]
    assert _subsystem_verdict("blocked-on-prerequisite", classifications) == "design-skeleton"


def test_subsystem_shape_dead_concept_verdict():
    """Stubs with concept-not-applicable as dominant -> dead-concept."""
    from determined.agent.corpus_projections import _subsystem_verdict
    classifications = ["concept-not-applicable"] * 4 + ["genuinely-unknown"]
    assert _subsystem_verdict("concept-not-applicable", classifications) == "dead-concept"


# ---------------------------------------------------------------------------
# stub_prerequisite_map
# ---------------------------------------------------------------------------

def test_prereq_map_no_stubs():
    conn = _make_db()
    result = stub_prerequisite_map(_FakeAssessor(conn), {})
    assert "no stubs" in result


def test_prereq_map_extracts_prerequisite():
    conn = _make_db(stubs=[{
        "name": "process",
        "file_path": "world/adj.py",
        "docstring": "STUB: blocked on AdjudicationEngine being built first.",
    }])
    result = stub_prerequisite_map(_FakeAssessor(conn), {})
    assert "AdjudicationEngine" in result


def test_prereq_map_groups_shared_prereq():
    """Two stubs blocked on the same prerequisite should appear under one entry."""
    conn = _make_db(stubs=[
        {
            "name": "start_encounter",
            "file_path": "world/adj.py",
            "docstring": "STUB: blocked on AdjudicationEngine.",
        },
        {
            "name": "handle_action",
            "file_path": "world/adj.py",
            "docstring": "Waiting on AdjudicationEngine to process combat.",
        },
    ])
    result = stub_prerequisite_map(_FakeAssessor(conn), {})
    # Both stubs under one AdjudicationEngine entry, count shown as 2
    assert "AdjudicationEngine" in result
    adj_section = result[result.index("AdjudicationEngine"):]
    assert "start_encounter" in adj_section
    assert "handle_action" in adj_section


def test_prereq_map_high_priority_for_many_blocked():
    """3+ stubs on same prereq -> HIGH priority."""
    conn = _make_db(stubs=[
        {"name": f"stub_{i}", "file_path": "world/ai.py",
         "docstring": "blocked on AIDungeonMaster"} for i in range(4)
    ])
    result = stub_prerequisite_map(_FakeAssessor(conn), {})
    assert "[HIGH]" in result


def test_prereq_map_no_prereqs_in_docstrings():
    conn = _make_db(stubs=[{"name": "empty", "file_path": "world/ai.py", "docstring": None}])
    result = stub_prerequisite_map(_FakeAssessor(conn), {})
    assert "no named prerequisites" in result


def test_prereq_map_scope_filter():
    conn = _make_db(stubs=[
        {"name": "s1", "file_path": "world/ai.py",
         "docstring": "blocked on AIDungeonMaster"},
        {"name": "s2", "file_path": "engine/runner.py",
         "docstring": "blocked on RunnerEngine"},
    ])
    result = stub_prerequisite_map(_FakeAssessor(conn), {"scope": "world"})
    assert "AIDungeonMaster" in result
    assert "RunnerEngine" not in result


# ---------------------------------------------------------------------------
# stub_concept_ghost_map
# ---------------------------------------------------------------------------

def test_concept_ghost_map_no_stubs():
    conn = _make_db()
    result = stub_concept_ghost_map(_FakeAssessor(conn), {})
    assert "no stubs" in result


def test_concept_ghost_map_detects_ghost():
    """CombatFSM referenced in stub but no class exists -> GHOST."""
    conn = _make_db(
        stubs=[{
            "name": "get_combat_context",
            "file_path": "world/adj.py",
            "docstring": "Query active CombatFSM for current encounter state.",
        }],
    )
    result = stub_concept_ghost_map(_FakeAssessor(conn), {})
    assert "GHOST" in result
    assert "CombatFSM" in result


def test_concept_ghost_map_live_concept():
    """Concept with a matching class -> live."""
    conn = _make_db(
        stubs=[{
            "name": "get_session",
            "file_path": "world/sess.py",
            "docstring": "Return the active SessionManager.",
        }],
        classes=[{"name": "SessionManager", "file_path": "world/session_manager.py"}],
    )
    result = stub_concept_ghost_map(_FakeAssessor(conn), {})
    assert "live" in result
    assert "SessionManager" in result


def test_concept_ghost_map_ghosts_ranked_first():
    """Ghost concepts should appear before live ones in output."""
    conn = _make_db(
        stubs=[
            {
                "name": "s1", "file_path": "world/a.py",
                "docstring": "Uses CombatFSM and SessionManager.",
            },
        ],
        classes=[{"name": "SessionManager", "file_path": "world/sm.py"}],
    )
    result = stub_concept_ghost_map(_FakeAssessor(conn), {})
    ghost_pos = result.find("[GHOST]")
    live_pos = result.find("[live]")
    assert ghost_pos < live_pos


def test_concept_ghost_map_shows_stub_count():
    """Output reports how many stubs reference each concept."""
    conn = _make_db(stubs=[
        {"name": "s1", "file_path": "world/a.py",
         "docstring": "Query CombatFSM for state."},
        {"name": "s2", "file_path": "world/b.py",
         "docstring": "Requires CombatFSM to be active."},
    ])
    result = stub_concept_ghost_map(_FakeAssessor(conn), {})
    # Should show 2 references for CombatFSM
    assert "2 stub reference" in result


def test_concept_ghost_map_no_concepts_in_docstrings():
    conn = _make_db(stubs=[{"name": "empty", "file_path": "world/a.py", "docstring": None}])
    result = stub_concept_ghost_map(_FakeAssessor(conn), {})
    assert "no concept names" in result


def test_concept_ghost_map_scope_filter():
    conn = _make_db(stubs=[
        {"name": "s1", "file_path": "world/a.py",
         "docstring": "blocked on CombatFSM"},
        {"name": "s2", "file_path": "engine/b.py",
         "docstring": "blocked on RunnerEngine"},
    ])
    result = stub_concept_ghost_map(_FakeAssessor(conn), {"scope": "world"})
    assert "CombatFSM" in result
    assert "RunnerEngine" not in result
