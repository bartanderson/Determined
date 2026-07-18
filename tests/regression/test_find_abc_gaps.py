# tests/regression/test_find_abc_gaps.py
#
# Regression tests for find_abc_gaps — unimplemented ABC interface detection.
# Uses an in-memory SQLite DB with a minimal schema.
#
# New approach (post-fix): detects abstract methods via @abstractmethod decorator
# stored in decorators_json; checks per-subclass via methods_json, not global name search.

import json
import sqlite3
import pytest

from determined.agent.agent_tools import find_abc_gaps


def _make_db():
    """Return an in-memory DB with minimal schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE classes (id INTEGER PRIMARY KEY, file_path TEXT, name TEXT, "
        "line_number INTEGER, methods_json TEXT, base_classes_json TEXT, docstring TEXT)"
    )
    conn.execute(
        "CREATE TABLE functions (id INTEGER PRIMARY KEY, file_path TEXT, name TEXT, "
        "line_number INTEGER, return_type TEXT, arguments_json TEXT, docstring TEXT, "
        "is_stub INTEGER DEFAULT 0, param_types_json TEXT, decorators_json TEXT)"
    )
    return conn


class _FakeOracle:
    def __init__(self, conn):
        self.conn = conn


def _add_abc_base(conn, file_path, cls_name, methods):
    """Add an ABC base class with abstract methods."""
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (file_path, cls_name, 1, json.dumps(methods), json.dumps(["ABC"])),
    )
    for i, method in enumerate(methods):
        conn.execute(
            "INSERT INTO functions (file_path, name, line_number, is_stub, decorators_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, method, 10 + i, 0, json.dumps(["abstractmethod"])),
        )


def _add_subclass(conn, file_path, cls_name, base_name, overrides):
    """Add a concrete subclass with the given overriding methods."""
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (file_path, cls_name, 50, json.dumps(overrides), json.dumps([base_name])),
    )
    for i, method in enumerate(overrides):
        conn.execute(
            "INSERT INTO functions (file_path, name, line_number, is_stub, decorators_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, method, 60 + i, 0, json.dumps([])),
        )


def test_no_abc_classes_returns_message():
    conn = _make_db()
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "No ABC" in result


def test_subclass_missing_override_reported():
    """Concrete subclass that doesn't override an abstract method is reported."""
    conn = _make_db()
    _add_abc_base(conn, "iface.py", "IFoo", ["do_thing"])
    # ConcreteA overrides do_thing
    _add_subclass(conn, "impl_a.py", "ConcreteA", "IFoo", ["do_thing"])
    # ConcreteB does NOT override do_thing
    _add_subclass(conn, "impl_b.py", "ConcreteB", "IFoo", [])
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "ConcreteB" in result
    assert "do_thing" in result
    assert "ConcreteA" not in result


def test_all_subclasses_covered_returns_no_gaps():
    """When every subclass overrides all abstract methods, no gap reported."""
    conn = _make_db()
    _add_abc_base(conn, "iface.py", "IFoo", ["do_thing"])
    _add_subclass(conn, "impl.py", "ConcreteA", "IFoo", ["do_thing"])
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "All ABC stub methods" in result


def test_no_subclasses_returns_arch_void():
    """ABC with no subclasses is reported as an unimplemented interface (arch void)."""
    conn = _make_db()
    _add_abc_base(conn, "iface.py", "IFoo", ["do_thing"])
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "UNIMPLEMENTED INTERFACES" in result
    assert "IFoo" in result
    assert "do_thing" in result


def test_non_abstract_method_on_abc_not_reported():
    """Methods without @abstractmethod decorator are not treated as abstract."""
    conn = _make_db()
    conn.execute(
        "INSERT INTO classes (file_path, name, line_number, methods_json, base_classes_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("base.py", "Base", 1, json.dumps(["helper"]), json.dumps(["ABC"])),
    )
    # helper has no @abstractmethod
    conn.execute(
        "INSERT INTO functions (file_path, name, line_number, is_stub, decorators_json) "
        "VALUES (?, ?, ?, ?, ?)",
        ("base.py", "helper", 10, 0, json.dumps([])),
    )
    # subclass that doesn't override helper
    _add_subclass(conn, "sub.py", "Sub", "Base", [])
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "No abstract methods" in result or "All ABC stub methods" in result


def test_multiple_abc_classes_multiple_subclasses():
    """Multiple ABC bases, gaps reported per-subclass."""
    conn = _make_db()
    _add_abc_base(conn, "ifoo.py", "IFoo", ["foo_op"])
    _add_abc_base(conn, "ibar.py", "IBar", ["bar_op"])
    # FooImpl covers IFoo but ignores IBar (doesn't inherit IBar so no gap)
    _add_subclass(conn, "fooimpl.py", "FooImpl", "IFoo", ["foo_op"])
    # BarImpl covers IBar
    _add_subclass(conn, "barimpl.py", "BarImpl", "IBar", ["bar_op"])
    # GapImpl inherits IFoo but misses foo_op
    _add_subclass(conn, "gapimpl.py", "GapImpl", "IFoo", [])
    oracle = _FakeOracle(conn)
    result = find_abc_gaps(oracle, {})
    assert "GapImpl" in result
    assert "foo_op" in result
    assert "FooImpl" not in result
    assert "BarImpl" not in result
