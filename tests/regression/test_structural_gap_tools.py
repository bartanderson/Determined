# tests/regression/test_structural_gap_tools.py
#
# Regression tests for:
#   find_isolated_modules   -- files that define symbols but are never imported
#   find_phantom_factories  -- ABC factory classes with no concrete subclass
#   detect_doc_drift Check 4 -- class role-claim drift (docstring vs inheritance)

import json
import sqlite3
import pytest
from unittest.mock import MagicMock

from determined.agent.agent_tools import (
    find_isolated_modules,
    find_phantom_factories,
    detect_doc_drift,
)


# ---------------------------------------------------------------------------
# Shared schema helpers
# ---------------------------------------------------------------------------

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, file_path TEXT
        );
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            name TEXT,
            line_number INTEGER DEFAULT 1,
            return_type TEXT,
            arguments_json TEXT,
            docstring TEXT,
            is_stub INTEGER DEFAULT 0,
            param_types_json TEXT,
            decorators_json TEXT,
            http_route TEXT,
            is_tool INTEGER DEFAULT 0,
            class_name TEXT
        );
        CREATE TABLE classes (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            name TEXT,
            line_number INTEGER DEFAULT 1,
            methods_json TEXT,
            base_classes_json TEXT,
            docstring TEXT
        );
        CREATE TABLE imports (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            module TEXT,
            import_type TEXT,
            line_number INTEGER DEFAULT 1
        );
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            caller TEXT,
            callee TEXT,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0
        );
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY,
            kind TEXT,
            subject TEXT,
            content TEXT,
            source TEXT
        );
    """)
    return conn


def _oracle(conn):
    o = MagicMock()
    o.conn = conn
    return o


def _assessor(conn):
    a = MagicMock()
    a.oracle = _oracle(conn)
    return a


def _add_abc(conn, file_path, cls_name, abstract_methods):
    conn.execute(
        "INSERT INTO classes (file_path, name, methods_json, base_classes_json) VALUES (?,?,?,?)",
        (file_path, cls_name, json.dumps(abstract_methods), json.dumps(["ABC"])),
    )
    for m in abstract_methods:
        conn.execute(
            "INSERT INTO functions (file_path, name, is_stub, decorators_json) VALUES (?,?,?,?)",
            (file_path, m, 0, json.dumps(["abstractmethod"])),
        )


def _add_subclass(conn, file_path, cls_name, base_name, methods):
    conn.execute(
        "INSERT INTO classes (file_path, name, methods_json, base_classes_json) VALUES (?,?,?,?)",
        (file_path, cls_name, json.dumps(methods), json.dumps([base_name])),
    )
    for m in methods:
        conn.execute(
            "INSERT INTO functions (file_path, name, is_stub, decorators_json) VALUES (?,?,?,?)",
            (file_path, m, 0, json.dumps([])),
        )


# ---------------------------------------------------------------------------
# find_isolated_modules
# ---------------------------------------------------------------------------

def test_isolated_module_not_imported_reported():
    """A file that defines functions but is never imported anywhere is flagged."""
    conn = _make_db()
    conn.execute("INSERT INTO functions (file_path, name) VALUES (?,?)", ("engine/phases.py", "do_thing"))
    # No import of 'phases' anywhere
    oracle = _oracle(conn)
    result = find_isolated_modules(oracle, {})
    assert "phases" in result
    assert "isolated" in result.lower() or "never imported" in result.lower()


def test_imported_module_not_reported():
    """A file that is imported somewhere is not flagged."""
    conn = _make_db()
    conn.execute("INSERT INTO functions (file_path, name) VALUES (?,?)", ("engine/phases.py", "do_thing"))
    conn.execute("INSERT INTO imports (file_path, module) VALUES (?,?)", ("app.py", "engine.phases"))
    oracle = _oracle(conn)
    result = find_isolated_modules(oracle, {})
    assert "No isolated modules" in result


def test_isolated_abc_file_is_critical():
    """An isolated file that defines ABCs is reported as critical severity."""
    conn = _make_db()
    _add_abc(conn, "interfaces/phases.py", "AuthorityPhase", ["validate_action"])
    # Not imported anywhere
    oracle = _oracle(conn)
    result = find_isolated_modules(oracle, {})
    assert "critical" in result
    assert "phases" in result


def test_isolated_module_stem_match():
    """Module isolation check matches on bare filename stem."""
    conn = _make_db()
    conn.execute("INSERT INTO functions (file_path, name) VALUES (?,?)", ("world/utils.py", "helper"))
    conn.execute("INSERT INTO imports (file_path, module) VALUES (?,?)", ("app.py", "utils"))
    oracle = _oracle(conn)
    result = find_isolated_modules(oracle, {})
    assert "No isolated modules" in result


def test_no_defining_files_returns_message():
    conn = _make_db()
    oracle = _oracle(conn)
    result = find_isolated_modules(oracle, {})
    assert "No files" in result or "No isolated" in result


# ---------------------------------------------------------------------------
# find_phantom_factories
# ---------------------------------------------------------------------------

def test_phantom_factory_no_subclass_reported():
    """Factory ABC with no subclass is a phantom factory."""
    conn = _make_db()
    _add_abc(conn, "wiring.py", "PhaseFactory", ["create_input", "create_authority", "create_output"])
    oracle = _oracle(conn)
    result = find_phantom_factories(oracle, {})
    assert "PhaseFactory" in result
    assert "phantom" in result.lower() or "no implementation" in result.lower()


def test_factory_with_subclass_not_reported():
    """Factory ABC that has a concrete subclass is not a phantom."""
    conn = _make_db()
    _add_abc(conn, "wiring.py", "PhaseFactory", ["create_input", "create_output"])
    _add_subclass(conn, "impl.py", "ConcreteFactory", "PhaseFactory", ["create_input", "create_output"])
    oracle = _oracle(conn)
    result = find_phantom_factories(oracle, {})
    assert "No phantom factories" in result


def test_non_factory_abc_not_reported():
    """An ABC with non-factory method names is not reported as a phantom factory."""
    conn = _make_db()
    _add_abc(conn, "auth.py", "AuthorityPhase", ["validate_action", "roll_dice", "check_permissions"])
    oracle = _oracle(conn)
    result = find_phantom_factories(oracle, {})
    assert "No phantom factories" in result


def test_mixed_factory_and_non_factory_methods_not_reported():
    """ABC with a mix of factory and non-factory abstract methods is not a phantom factory."""
    conn = _make_db()
    _add_abc(conn, "mixed.py", "MixedBase", ["create_thing", "validate_thing"])
    oracle = _oracle(conn)
    result = find_phantom_factories(oracle, {})
    assert "No phantom factories" in result


def test_no_abc_classes_returns_message():
    conn = _make_db()
    oracle = _oracle(conn)
    result = find_phantom_factories(oracle, {})
    assert "No ABC" in result


# ---------------------------------------------------------------------------
# detect_doc_drift Check 4: class role-claim drift
# ---------------------------------------------------------------------------

def test_role_claim_drift_detected():
    """Class that claims Authority phase in docstring but doesn't inherit AuthorityPhase is flagged."""
    conn = _make_db()
    # The ABC
    _add_abc(conn, "phases.py", "AuthorityPhase", ["validate_action"])
    # A class that self-identifies but doesn't inherit
    conn.execute(
        "INSERT INTO classes (file_path, name, methods_json, base_classes_json) VALUES (?,?,?,?)",
        ("world/authority_system.py", "AuthoritySystem", json.dumps(["validate_action"]), json.dumps([])),
    )
    conn.execute(
        "INSERT INTO functions (file_path, name, class_name, docstring, is_stub) VALUES (?,?,?,?,?)",
        ("world/authority_system.py", "validate_action", "AuthoritySystem",
         "Phase: Authority -- validates and executes game actions", 0),
    )
    assessor = _assessor(conn)
    result = detect_doc_drift(assessor, {"feature_path": "world/"})
    assert "role-claim drift" in result.lower() or "AuthoritySystem" in result


def test_correctly_wired_class_not_flagged():
    """Class that claims a role AND inherits the correct ABC is not flagged."""
    conn = _make_db()
    _add_abc(conn, "phases.py", "AuthorityPhase", ["validate_action"])
    _add_subclass(conn, "world/authority_system.py", "AuthoritySystem", "AuthorityPhase", ["validate_action"])
    conn.execute(
        "INSERT INTO functions (file_path, name, class_name, docstring, is_stub) VALUES (?,?,?,?,?)",
        ("world/authority_system.py", "validate_action", "AuthoritySystem",
         "Phase: Authority -- validates game actions", 0),
    )
    assessor = _assessor(conn)
    result = detect_doc_drift(assessor, {"feature_path": "world/"})
    assert "AuthoritySystem" not in result or "role-claim" not in result.lower()


def test_role_claim_no_matching_abc_not_flagged():
    """A role claim that has no matching ABC in the corpus is silently ignored (can't verify)."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO classes (file_path, name, methods_json, base_classes_json) VALUES (?,?,?,?)",
        ("world/manager.py", "SessionManager", json.dumps(["start"]), json.dumps([])),
    )
    conn.execute(
        "INSERT INTO functions (file_path, name, class_name, docstring, is_stub) VALUES (?,?,?,?,?)",
        ("world/manager.py", "start", "SessionManager", "Component: Sessions -- manages user sessions", 0),
    )
    assessor = _assessor(conn)
    result = detect_doc_drift(assessor, {"feature_path": "world/"})
    # No ABC named "Sessions" exists, so nothing to verify — should not flag
    assert "SessionManager" not in result or "role-claim" not in result.lower()
