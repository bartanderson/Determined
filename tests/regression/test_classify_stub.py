# tests/regression/test_classify_stub.py
#
# Regression tests for the RM69 judgment layer: extract_signals + score_hypotheses.
# Uses in-memory SQLite fixtures — no live corpus required.
# Tests verify signal extraction and hypothesis scoring independently,
# then test the classify_stub tool entry point.

import json
import sqlite3
import tempfile
import os
import pytest

from determined.agent.classify_stub import (
    extract_signals,
    score_hypotheses,
    classify_stub,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_db(stubs=None, non_stubs=None, classes=None):
    """Create an in-memory DB with the minimal schema classify_stub needs."""
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
    conn.execute("""
        CREATE TABLE files (file_path TEXT, line_count INTEGER)
    """)

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
# extract_signals — signal extraction
# ---------------------------------------------------------------------------

def test_extract_signals_not_found():
    conn = _make_db()
    sig = extract_signals(_FakeOracle(conn), "nonexistent")
    assert "error" in sig


def test_extract_signals_not_stub():
    conn = _make_db(non_stubs=[{"name": "real_fn"}])
    sig = extract_signals(_FakeOracle(conn), "real_fn")
    assert "error" in sig


def test_extract_signals_caller_count_zero():
    conn = _make_db(stubs=[{"name": "my_stub", "docstring": "does something"}])
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    assert sig["caller_count"] == 0
    assert sig["callee_count"] == 0


def test_extract_signals_caller_count_nonzero():
    conn = _make_db(
        stubs=[{"name": "my_stub"}],
        non_stubs=[{"name": "caller_fn"}],
    )
    conn.execute(
        "INSERT INTO graph_edges VALUES ('caller_fn','my_stub',NULL,'static',0,NULL,NULL)"
    )
    conn.commit()
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    assert sig["caller_count"] >= 1


def test_extract_signals_sibling_stubs():
    conn = _make_db(stubs=[
        {"name": "stub_a", "file_path": "world/ai.py"},
        {"name": "stub_b", "file_path": "world/ai.py"},
        {"name": "stub_c", "file_path": "world/ai.py"},
    ])
    sig = extract_signals(_FakeOracle(conn), "stub_a")
    assert sig["sibling_stub_count"] == 2
    assert "stub_b" in sig["sibling_stubs"]
    assert "stub_c" in sig["sibling_stubs"]


def test_extract_signals_no_siblings():
    conn = _make_db(stubs=[
        {"name": "stub_a", "file_path": "world/ai.py"},
        {"name": "stub_b", "file_path": "world/other.py"},
    ])
    sig = extract_signals(_FakeOracle(conn), "stub_a")
    assert sig["sibling_stub_count"] == 0


def test_extract_signals_concept_presence_absent():
    conn = _make_db(stubs=[{
        "name": "my_stub",
        "docstring": "Query active CombatFSM for context.",
    }])
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    # CombatFSM concept should have count 0 (nothing in DB matches)
    assert any(v == 0 for v in sig["concept_presence"].values())


def test_extract_signals_concept_presence_present():
    conn = _make_db(
        stubs=[{"name": "my_stub", "docstring": "Use WorldController to get state."}],
        classes=[{"name": "WorldController", "file_path": "world/world_controller.py"}],
    )
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    assert any(v > 0 for v in sig["concept_presence"].values())


def test_extract_signals_file_character_utility_bag():
    conn = _make_db(stubs=[{"name": "my_stub", "file_path": "utils/helpers.py"}])
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    assert sig["file_character"] == "utility_bag"


def test_extract_signals_file_character_multi_concept():
    conn = _make_db(
        stubs=[{"name": "my_stub", "file_path": "world/data.py"}],
        classes=[
            {"name": "ClassA", "file_path": "world/data.py"},
            {"name": "ClassB", "file_path": "world/data.py"},
        ],
    )
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    assert sig["file_character"] == "multi_concept"


def test_extract_signals_has_intent_from_docstring():
    conn = _make_db(stubs=[{
        "name": "my_stub",
        "docstring": "This would pull from unpaid_choices and create story complications.",
    }])
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    assert sig["has_intent"] is True


def test_extract_signals_no_intent_placeholder_doc():
    conn = _make_db(stubs=[{
        "name": "my_stub",
        "docstring": "OG System has no subraces, return empty list",
    }])
    sig = extract_signals(_FakeOracle(conn), "my_stub")
    # "return" in docstring doesn't match _INTENT_PATTERNS
    # docstring_quality should be placeholder (short, no intent language)
    assert sig["docstring_quality"] in ("placeholder", "none")


# ---------------------------------------------------------------------------
# score_hypotheses — hypothesis scoring
# ---------------------------------------------------------------------------

def _base_signals(**overrides):
    base = {
        "body_shape": "empty_pass",
        "has_intent": False,
        "intent_text": None,
        "caller_count": 0,
        "callee_count": 0,
        "concept_presence": {},
        "sibling_stub_count": 0,
        "sibling_stubs": [],
        "file_character": "utility_bag",
        "docstring_quality": "none",
        "return_type": None,
    }
    base.update(overrides)
    return base


def test_score_genuinely_unknown_no_signals():
    # No intent, no callers, no concepts, empty body → genuinely-unknown tops
    h = score_hypotheses(_base_signals())
    assert h[0]["classification"] == "genuinely-unknown"


def test_score_design_intent_strong_intent_language():
    # Strong intent comment → design-intent-stated tops
    h = score_hypotheses(_base_signals(
        has_intent=True,
        intent_text="This would trigger completion events when arc finishes.",
        caller_count=1,
        docstring_quality="behavioral",
    ))
    top = h[0]["classification"]
    assert top == "design-intent-stated"


def test_score_blocked_on_prerequisite_absent_concept():
    # Absent concept + has callers → blocked-on-prerequisite
    h = score_hypotheses(_base_signals(
        concept_presence={"CombatFSM": 0},
        caller_count=1,
        body_shape="trivial_return",
    ))
    classifications = [r["classification"] for r in h]
    assert "blocked-on-prerequisite" in classifications
    assert h[0]["classification"] in ("blocked-on-prerequisite", "design-intent-stated")


def test_score_concept_not_applicable_no_callers_absent():
    # All concepts absent + no callers → concept-not-applicable competitive
    h = score_hypotheses(_base_signals(
        concept_presence={"SubraceManager": 0, "SubraceRegistry": 0},
        caller_count=0,
        docstring_quality="placeholder",
    ))
    classifications = [r["classification"] for r in h]
    assert "concept-not-applicable" in classifications


def test_score_dense_sibling_cluster():
    # Dense sibling cluster → blocked-on-prerequisite gets a boost
    h = score_hypotheses(_base_signals(
        sibling_stub_count=4,
        caller_count=1,
        body_shape="empty_pass",
    ))
    classifications = [r["classification"] for r in h]
    assert "blocked-on-prerequisite" in classifications


def test_score_raises_not_impl_boosts_design_intent():
    h = score_hypotheses(_base_signals(
        body_shape="raise_not_impl",
        has_intent=True,
        intent_text="Needs implementation when X is built",
        caller_count=2,
    ))
    assert h[0]["classification"] == "design-intent-stated"


def test_score_all_concepts_present_boosts_design_intent():
    h = score_hypotheses(_base_signals(
        concept_presence={"WorldController": 3, "SessionManager": 2},
        has_intent=True,
        caller_count=1,
    ))
    assert h[0]["classification"] == "design-intent-stated"


def test_score_returns_evidence():
    h = score_hypotheses(_base_signals(
        has_intent=True,
        intent_text="This would handle the event",
        caller_count=1,
    ))
    top = h[0]
    assert len(top["evidence"]) > 0


def test_score_floor_filters_noise():
    # All signals neutral → should still return something above 0.2 floor
    h = score_hypotheses(_base_signals(caller_count=0))
    assert len(h) >= 1
    for entry in h:
        assert entry["score"] >= 0.2


# ---------------------------------------------------------------------------
# classify_stub — tool entry point
# ---------------------------------------------------------------------------

def test_classify_stub_missing_symbol():
    conn = _make_db()
    result = classify_stub(_FakeAssessor(conn), {"symbol": "nonexistent"})
    assert "not found" in result


def test_classify_stub_missing_arg():
    conn = _make_db()
    result = classify_stub(_FakeAssessor(conn), {})
    assert "ERROR" in result


def test_classify_stub_not_stub():
    conn = _make_db(non_stubs=[{"name": "real_fn"}])
    result = classify_stub(_FakeAssessor(conn), {"symbol": "real_fn"})
    assert "not found" in result


def test_classify_stub_output_contains_symbol():
    conn = _make_db(stubs=[{
        "name": "my_stub",
        "docstring": "This would process pending consequences.",
        "file_path": "world/ai_dungeon_master.py",
    }])
    result = classify_stub(_FakeAssessor(conn), {"symbol": "my_stub"})
    assert "my_stub" in result
    assert "ai_dungeon_master.py" in result


def test_classify_stub_output_contains_hypothesis():
    conn = _make_db(stubs=[{
        "name": "process_stub",
        "docstring": "This would create story complications using the three-layer approach.",
    }])
    result = classify_stub(_FakeAssessor(conn), {"symbol": "process_stub"})
    # At least one hypothesis classification should appear in output
    assert any(cls in result for cls in [
        "design-intent-stated", "blocked-on-prerequisite",
        "concept-not-applicable", "genuinely-unknown", "UNCERTAIN",
    ])


def test_classify_stub_uncertain_when_no_signals():
    conn = _make_db(stubs=[{"name": "empty_stub", "docstring": None}])
    result = classify_stub(_FakeAssessor(conn), {"symbol": "empty_stub"})
    # May be UNCERTAIN or genuinely-unknown — either is correct
    assert "genuinely-unknown" in result or "UNCERTAIN" in result


# ---------------------------------------------------------------------------
# Magic method / lifecycle handling
# ---------------------------------------------------------------------------

def test_is_lifecycle_python_dunder():
    from determined.agent.classify_stub import _is_lifecycle_method
    assert _is_lifecycle_method("__init__", "world/foo.py") is True
    assert _is_lifecycle_method("__str__", "world/foo.py") is True
    assert _is_lifecycle_method("process", "world/foo.py") is False


def test_is_lifecycle_js_constructor():
    from determined.agent.classify_stub import _is_lifecycle_method
    assert _is_lifecycle_method("constructor", "src/Foo.ts") is True
    assert _is_lifecycle_method("constructor", "src/Foo.js") is True
    assert _is_lifecycle_method("__init__", "src/Foo.js") is False


def test_is_lifecycle_other_language():
    from determined.agent.classify_stub import _is_lifecycle_method
    # Go / Rust: no lifecycle convention detectable by name alone
    assert _is_lifecycle_method("new", "src/foo.go") is False
    assert _is_lifecycle_method("new", "src/foo.rs") is False


def test_extract_signals_lifecycle_flag():
    """__init__ stub is flagged as a lifecycle method."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/ai.py"}],
        classes=[{"name": "AIDungeonMaster", "file_path": "world/ai.py"}],
    )
    sig = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/ai.py")
    assert sig.get("is_lifecycle") is True


def test_extract_signals_protocol_abc_detected():
    """__init__ on a Protocol class sets is_protocol_or_abc=True."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/iface.py"}],
        classes=[{
            "name": "IActionHandler",
            "file_path": "world/iface.py",
            "base_classes": ["Protocol"],
        }],
    )
    sig = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/iface.py")
    assert sig.get("is_protocol_or_abc") is True


def test_extract_signals_abc_base_detected():
    """ABC base class also sets is_protocol_or_abc=True."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/base.py"}],
        classes=[{
            "name": "BaseHandler",
            "file_path": "world/base.py",
            "base_classes": ["ABC"],
        }],
    )
    sig = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/base.py")
    assert sig.get("is_protocol_or_abc") is True


def test_extract_signals_normal_class_not_protocol():
    """Regular class does not set is_protocol_or_abc."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/normal.py"}],
        classes=[{
            "name": "NormalClass",
            "file_path": "world/normal.py",
            "base_classes": [],
        }],
    )
    sig = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/normal.py")
    assert sig.get("is_protocol_or_abc") is False


def test_extract_signals_class_docstring_used_as_intent():
    """When stub has no docstring, class docstring provides intent signal."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/dm.py", "docstring": None}],
        classes=[{
            "name": "AIDungeonMaster",
            "file_path": "world/dm.py",
            "base_classes": [],
            "docstring": "Would orchestrate narrative generation when LLM layer is wired.",
        }],
    )
    sig = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/dm.py")
    assert sig.get("class_docstring") is not None
    # Intent should be picked up from class docstring
    assert sig.get("has_intent") is True


def test_extract_signals_class_sibling_stubs_counted():
    """class_sibling_stubs counts other stubs in the same file."""
    conn = _make_db(
        stubs=[
            {"name": "__init__", "file_path": "world/ai.py"},
            {"name": "generate",  "file_path": "world/ai.py"},
            {"name": "narrate",   "file_path": "world/ai.py"},
        ],
        classes=[{"name": "AIDungeonMaster", "file_path": "world/ai.py"}],
    )
    sig = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/ai.py")
    assert sig.get("class_sibling_stubs") == 2


def test_extract_signals_file_path_hint_disambiguates():
    """file_path_hint selects the correct __init__ when two exist in different files."""
    conn = _make_db(
        stubs=[
            {"name": "__init__", "file_path": "world/a.py", "docstring": "Intent A"},
            {"name": "__init__", "file_path": "world/b.py", "docstring": "Intent B"},
        ],
    )
    sig_a = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/a.py")
    sig_b = extract_signals(_FakeOracle(conn), "__init__", file_path_hint="world/b.py")
    assert sig_a["file_path"] == "world/a.py"
    assert sig_b["file_path"] == "world/b.py"


def test_extract_signals_file_path_hint_ts_separator():
    """file_path_hint with backslash or mixed case still matches forward-slash stored path."""
    conn = _make_db(
        stubs=[
            {"name": "addLogMessage", "file_path": "src/ui/UIManager.ts"},
        ],
    )
    # caller passes backslash-separated path (Windows)
    sig = extract_signals(_FakeOracle(conn), "addLogMessage", file_path_hint="src\\ui\\UIManager.ts")
    assert sig.get("file_path") == "src/ui/UIManager.ts"
    # caller passes wrong case
    sig2 = extract_signals(_FakeOracle(conn), "addLogMessage", file_path_hint="src/ui/uimanager.ts")
    assert sig2.get("file_path") == "src/ui/UIManager.ts"


def test_classify_stub_protocol_note_in_output():
    """classify_stub output notes Protocol/ABC membership prominently."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/iface.py"}],
        classes=[{
            "name": "IActionHandler",
            "file_path": "world/iface.py",
            "base_classes": ["Protocol"],
        }],
    )
    result = classify_stub(
        _FakeAssessor(conn),
        {"symbol": "__init__", "file_path": "world/iface.py"},
    )
    assert "Protocol" in result or "ABC" in result
    assert "[lifecycle]" in result


def test_classify_stub_lifecycle_tag_in_output():
    """classify_stub header shows [lifecycle] for dunder methods."""
    conn = _make_db(
        stubs=[{"name": "__init__", "file_path": "world/ai.py"}],
        classes=[{"name": "AIDungeonMaster", "file_path": "world/ai.py"}],
    )
    result = classify_stub(
        _FakeAssessor(conn),
        {"symbol": "__init__", "file_path": "world/ai.py"},
    )
    assert "[lifecycle]" in result


def test_score_hypotheses_protocol_favors_design_intent():
    """Protocol/ABC signal pushes design-intent-stated above genuinely-unknown."""
    signals = {
        "body_shape": "empty_pass",
        "has_intent": False,
        "has_removal": False,
        "intent_text": "",
        "caller_count": 0,
        "callee_count": 0,
        "concept_presence": {},
        "sibling_stub_count": 0,
        "sibling_removal_trend": 0.0,
        "file_character": "single_class",
        "docstring_quality": "none",
        "is_lifecycle": True,
        "is_protocol_or_abc": True,
        "class_sibling_stubs": 0,
        "instance_vars_assigned": True,
    }
    hyps = score_hypotheses(signals)
    top = hyps[0] if hyps else {}
    assert top.get("classification") == "design-intent-stated"


def test_score_hypotheses_no_instance_vars_signals_blocked():
    """__init__ that assigns no self.x pushes blocked-on-prerequisite."""
    signals = {
        "body_shape": "empty_pass",
        "has_intent": False,
        "has_removal": False,
        "intent_text": "",
        "caller_count": 1,
        "callee_count": 0,
        "concept_presence": {},
        "sibling_stub_count": 0,
        "sibling_removal_trend": 0.0,
        "file_character": "single_class",
        "docstring_quality": "none",
        "is_lifecycle": True,
        "is_protocol_or_abc": False,
        "class_sibling_stubs": 0,
        "instance_vars_assigned": False,
    }
    hyps = score_hypotheses(signals)
    labels = [h["classification"] for h in hyps]
    assert "blocked-on-prerequisite" in labels
