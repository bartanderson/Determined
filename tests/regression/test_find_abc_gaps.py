# tests/regression/test_find_abc_gaps.py
#
# Regression tests for find_abc_gaps — unimplemented ABC interface detection.
# Uses an in-memory SQLite DB with a minimal schema.

import json
import sqlite3
import pytest

from determined.agent.agent_tools import find_abc_gaps


def _make_db():
    """Return an in-memory DB with minimal schema + sample ABC data."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE classes (id INTEGER PRIMARY KEY, file_path TEXT, name TEXT, "
        "line_number INTEGER, methods_json TEXT, base_classes_json TEXT, docstring TEXT)"
    )
    conn.execute(
        "CREATE TABLE functions (id INTEGER PRIMARY KEY, file_path TEXT, name TEXT, "
        "line_number INTEGER, return_type TEXT, arguments_json TEXT, docstring TEXT, "
        "is_stub INTEGER DEFAULT 0, param_types_json TEXT)"
    )
    return conn


class _FakeOracle:
    def __init__(self, conn):
        self.conn = conn


def test_no_abc_classes_returns_message():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "No ABC" in result


def test_abc_stub_with_no_override_reported():
    conn = _make_db()
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("iface.py", "IFoo", 1, json.dumps(["do_thing"]), json.dumps(["ABC"])),
    )
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, is_stub) VALUES (?, ?, ?, ?)",
        ("iface.py", "do_thing", 5, 1),
    )
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "IFoo" in result
    assert "do_thing" in result


def test_abc_stub_with_concrete_override_not_reported():
    conn = _make_db()
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("iface.py", "IFoo", 1, json.dumps(["do_thing"]), json.dumps(["ABC"])),
    )
    # Abstract stub in iface.py
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, is_stub) VALUES (?, ?, ?, ?)",
        ("iface.py", "do_thing", 5, 1),
    )
    # Concrete override in impl.py
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, is_stub) VALUES (?, ?, ?, ?)",
        ("impl.py", "do_thing", 20, 0),
    )
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "All ABC stub methods have at least one non-stub override" in result


def test_non_stub_abc_method_not_reported():
    conn = _make_db()
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("base.py", "Base", 1, json.dumps(["helper"]), json.dumps(["ABC"])),
    )
    # method exists but is NOT a stub (is_stub=0)
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, is_stub) VALUES (?, ?, ?, ?)",
        ("base.py", "helper", 10, 0),
    )
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    # No gaps: non-stub method on ABC class is a concrete implementation, not abstract
    assert "No stub methods" in result or "All ABC stub methods" in result


def test_multiple_abc_classes_grouped():
    conn = _make_db()
    for cls, method in [("IFoo", "foo_op"), ("IBar", "bar_op")]:
        conn.execute(
            "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"{cls.lower()}.py", cls, 1, json.dumps([method]), json.dumps(["ABC"])),
        )
        conn.execute(
            "INSERT INTO functions (file_path, name, line_number, is_stub) VALUES (?, ?, ?, ?)",
            (f"{cls.lower()}.py", method, 5, 1),
        )
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "IFoo" in result
    assert "IBar" in result
    assert "foo_op" in result
    assert "bar_op" in result
