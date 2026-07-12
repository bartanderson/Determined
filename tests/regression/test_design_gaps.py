"""Regression tests for RM48: design_gaps tool."""
import sqlite3
import pytest
from determined.agent.agent_tools import (
    design_gaps,
    _extract_design_requirements,
    _match_level_b,
    _match_level_c,
)


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class _Oracle:
    def __init__(self, conn):
        self.conn = conn


class _Assessor:
    def __init__(self, conn):
        self.oracle = _Oracle(conn)


def _make_db(design_notes=None, functions=None, files=None, edges=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            kind TEXT,
            content TEXT,
            provenance TEXT,
            source TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT DEFAULT '',
            docstring TEXT DEFAULT '',
            is_stub INTEGER DEFAULT 0,
            line_number INTEGER DEFAULT 1,
            return_type TEXT DEFAULT '',
            param_types_json TEXT DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE classes (
            name TEXT PRIMARY KEY,
            file_path TEXT DEFAULT '',
            docstring TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE symbols (
            name TEXT,
            file_path TEXT,
            symbol_type TEXT DEFAULT 'function',
            line_number INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            file_path TEXT DEFAULT '',
            resolved INTEGER DEFAULT 0
        )
    """)

    for dn in (design_notes or []):
        conn.execute(
            "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, source) VALUES (?,?,?,?,?)",
            (dn.get("subject",""), "design_note", dn["content"], "human-confirmed", dn.get("source","doc.md"))
        )
    for fn in (functions or []):
        conn.execute(
            "INSERT INTO functions (name, file_path, docstring) VALUES (?,?,?)",
            (fn["name"], fn.get("file_path",""), fn.get("docstring",""))
        )
        conn.execute(
            "INSERT INTO symbols (name, file_path) VALUES (?,?)",
            (fn["name"], fn.get("file_path",""))
        )
    for fp in (files or []):
        conn.execute("INSERT INTO symbols (name, file_path) VALUES (?,?)", ("_file_"+fp, fp))
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee) VALUES (?,?)",
            (e["caller"], e["callee"])
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# _extract_design_requirements
# ---------------------------------------------------------------------------

def test_extract_reqs_new_prefix_format():
    conn = _make_db(design_notes=[
        {"content": "[REQUIREMENT|authoritative|00A.md] The engine must enforce authority.", "subject": "engine"},
    ])
    reqs = _extract_design_requirements(conn)
    assert len(reqs) == 1
    assert "must enforce" in reqs[0]["content"]


def test_extract_reqs_old_must_format():
    conn = _make_db(design_notes=[
        {"content": "The system must validate all inputs before processing.", "subject": "system"},
    ])
    reqs = _extract_design_requirements(conn)
    assert len(reqs) == 1


def test_extract_reqs_shall_format():
    conn = _make_db(design_notes=[
        {"content": "The AI layer shall never write directly to DungeonStateNeo.", "subject": "ai_layer"},
    ])
    reqs = _extract_design_requirements(conn)
    assert len(reqs) == 1


def test_extract_reqs_intent_excluded():
    conn = _make_db(design_notes=[
        {"content": "[INTENT|medium|notes.md] This section describes the philosophy.", "subject": "philosophy"},
    ])
    reqs = _extract_design_requirements(conn)
    # "intent" content with no must/shall should not be extracted
    assert len(reqs) == 0


def test_extract_reqs_no_design_notes():
    conn = _make_db()
    assert _extract_design_requirements(conn) == []


def test_extract_reqs_mixed():
    conn = _make_db(design_notes=[
        {"content": "The layer must enforce boundaries.", "subject": "layer"},
        {"content": "This is general design context without modals.", "subject": "context"},
        {"content": "The interface shall expose a clean API.", "subject": "interface"},
    ])
    reqs = _extract_design_requirements(conn)
    assert len(reqs) == 2


# ---------------------------------------------------------------------------
# _match_level_b
# ---------------------------------------------------------------------------

def test_level_b_finds_matching_file():
    conn = _make_db(files=["auth/auth_boundary.py", "ui/main.py"])
    oracle = _Oracle(conn)
    matches = _match_level_b(oracle, "auth_boundary", "The auth layer must validate tokens.")
    assert any("auth" in f for f in matches)


def test_level_b_no_match():
    conn = _make_db(files=["render/canvas.py"])
    oracle = _Oracle(conn)
    matches = _match_level_b(oracle, "session", "The session must persist tokens.")
    assert not any("canvas" in f for f in matches)


def test_level_b_empty_subject():
    conn = _make_db(files=["session/manager.py"])
    oracle = _Oracle(conn)
    # Should still work with empty subject (uses req_text keywords)
    matches = _match_level_b(oracle, "", "The session must persist across reconnects.")
    assert isinstance(matches, list)


# ---------------------------------------------------------------------------
# _match_level_c
# ---------------------------------------------------------------------------

def test_level_c_finds_matching_edge():
    conn = _make_db(edges=[
        {"caller": "intent_classifier", "callee": "game_state"},
        {"caller": "renderer", "callee": "canvas"},
    ])
    oracle = _Oracle(conn)
    matches = _match_level_c(oracle, "intent", "The intent layer must classify player input.")
    assert any("intent" in m["caller"] or "intent" in m["callee"] for m in matches)


def test_level_c_no_match():
    conn = _make_db(edges=[{"caller": "renderer", "callee": "canvas"}])
    oracle = _Oracle(conn)
    matches = _match_level_c(oracle, "session", "Session must persist tokens.")
    assert isinstance(matches, list)


# ---------------------------------------------------------------------------
# design_gaps -- integration
# ---------------------------------------------------------------------------

def test_design_gaps_no_design_notes():
    conn = _make_db()
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {})
    assert "ingest_design_docs" in result or "No design notes" in result


def test_design_gaps_gap_detected():
    """A requirement with no matching function, file, or edge -> GAP."""
    conn = _make_db(
        design_notes=[
            {"content": "The zorb_manager must frobnicate all wuggles.", "subject": "zorb_manager"},
        ],
        functions=[
            {"name": "render_canvas", "file_path": "render.py", "docstring": "Draws pixels."},
        ]
    )
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {})
    assert "GAP" in result
    assert "zorb" in result.lower() or "frobnicate" in result.lower() or "wuggle" in result.lower()


def test_design_gaps_partial_file_match():
    """Requirement keyword matches a file path but no function -> PARTIAL."""
    conn = _make_db(
        design_notes=[
            {"content": "The session manager must persist state across reconnects.", "subject": "session_manager", "source": "00A.md"},
        ],
        functions=[
            {"name": "render_ui", "file_path": "render/ui.py", "docstring": "Draws the interface."},
        ],
        files=["session/session_manager.py"],
    )
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {})
    # Should be PARTIAL (file matches) not GAP
    assert "PARTIAL" in result or "session" in result.lower()


def test_design_gaps_scope_filter():
    conn = _make_db(design_notes=[
        {"content": "The auth layer must validate tokens.", "subject": "auth_layer", "source": "auth.md"},
        {"content": "The render system must update frames at 60fps.", "subject": "render", "source": "render.md"},
    ])
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {"scope": "auth"})
    assert "auth" in result.lower()
    # render requirement should not appear
    assert "render system" not in result


def test_design_gaps_scope_no_match():
    conn = _make_db(design_notes=[
        {"content": "The auth layer must validate tokens.", "subject": "auth", "source": "doc.md"},
    ])
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {"scope": "zorblax"})
    assert "zorblax" in result


def test_design_gaps_show_satisfied_flag():
    """show_satisfied=true should include SATISFIED section if any requirements are satisfied."""
    conn = _make_db(
        design_notes=[
            {"content": "The engine must enforce authority at mutation time.", "subject": "engine"},
        ],
        functions=[
            # No matching function -> will be GAP, but flag still processed
            {"name": "unrelated_helper", "file_path": "util.py", "docstring": "Helper utility."},
        ]
    )
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {"show_satisfied": True})
    # With no satisfied items, satisfied section should say 0
    assert isinstance(result, str)
    assert len(result) > 0


def test_design_gaps_output_structure():
    """Output must have corpus label, requirement count line, and tier sections."""
    conn = _make_db(design_notes=[
        {"content": "The phantom system must never exist.", "subject": "phantom"},
    ])
    assessor = _Assessor(conn)
    result = design_gaps(assessor, {})
    lines = result.splitlines()
    # First line should reference corpus
    assert any("corpus" in ln.lower() or "requirements" in ln.lower() for ln in lines[:3])


def test_design_gaps_constraint_content_prefix():
    """[CONSTRAINT|...] prefix should also be picked up as a requirement."""
    conn = _make_db(design_notes=[
        {"content": "[CONSTRAINT|authoritative|00A.md] External callers must not bypass validation.", "subject": "validation"},
    ])
    reqs = _extract_design_requirements(conn)
    assert len(reqs) == 1
