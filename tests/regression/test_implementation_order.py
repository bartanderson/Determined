"""Regression tests for implementation_order tool (RM44)."""
import sqlite3
import pytest
from determined.agent.agent_tools import implementation_order


# ---------------------------------------------------------------------------
# Minimal oracle stub
# ---------------------------------------------------------------------------

class _Oracle:
    def __init__(self, conn):
        self.conn = conn


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE functions (
            name TEXT PRIMARY KEY,
            file_path TEXT,
            line_number INTEGER,
            is_stub INTEGER DEFAULT 0,
            decorators_json TEXT DEFAULT '[]',
            param_types_json TEXT DEFAULT '',
            docstring TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            caller TEXT,
            callee TEXT,
            resolved INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE classes (
            name TEXT,
            methods_json TEXT DEFAULT '[]',
            base_classes_json TEXT DEFAULT '[]',
            file_path TEXT
        )
    """)
    conn.commit()
    return conn


def _add_stub(conn, name, fp="module.py", ln=1):
    conn.execute(
        "INSERT OR IGNORE INTO functions VALUES (?,?,?,1,'[]','','')",
        (name, fp, ln),
    )


def _add_impl(conn, name, fp="module.py", ln=1):
    conn.execute(
        "INSERT OR IGNORE INTO functions VALUES (?,?,?,0,'[]','','')",
        (name, fp, ln),
    )


def _add_edge(conn, caller, callee, resolved=1):
    conn.execute(
        "INSERT INTO graph_edges VALUES (?,?,?)", (caller, callee, resolved)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_incomplete_symbols():
    conn = _make_db()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    assert "No incomplete symbols" in result


def test_single_stub_wave1():
    conn = _make_db()
    _add_stub(conn, "fn_a", "a.py", 10)
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    assert "fn_a" in result
    assert "Wave 1" in result


def test_chain_three_stubs_correct_order():
    """A calls B calls C (all stubs). C must be implemented first."""
    conn = _make_db()
    _add_stub(conn, "fn_a", "a.py", 1)
    _add_stub(conn, "fn_b", "a.py", 10)
    _add_stub(conn, "fn_c", "a.py", 20)
    # fn_a calls fn_b calls fn_c
    _add_edge(conn, "fn_a", "fn_b")
    _add_edge(conn, "fn_b", "fn_c")
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    # fn_c has no incomplete callees -> wave 1
    # fn_b depends on fn_c -> wave 2
    # fn_a depends on fn_b -> wave 3
    lines = result.splitlines()
    pos = {name: next(i for i, l in enumerate(lines) if name in l) for name in ("fn_a", "fn_b", "fn_c")}
    assert pos["fn_c"] < pos["fn_b"] < pos["fn_a"]


def test_parallel_stubs_same_wave():
    """fn_x and fn_y are independent stubs — both in wave 1."""
    conn = _make_db()
    _add_stub(conn, "fn_x", "b.py", 1)
    _add_stub(conn, "fn_y", "b.py", 5)
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    assert result.count("Wave 1") == 1
    assert "fn_x" in result
    assert "fn_y" in result
    # Both appear under Wave 1 (before any Wave 2 header)
    lines = result.splitlines()
    w1_idx = next(i for i, l in enumerate(lines) if "Wave 1" in l)
    w2_idx = next((i for i, l in enumerate(lines) if "Wave 2" in l), len(lines))
    wave1_block = "\n".join(lines[w1_idx:w2_idx])
    assert "fn_x" in wave1_block
    assert "fn_y" in wave1_block


def test_scope_filter():
    """scope='core.py' should exclude stubs in other files."""
    conn = _make_db()
    _add_stub(conn, "fn_core", "core.py", 1)
    _add_stub(conn, "fn_other", "other.py", 1)
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {"scope": "core.py"})
    assert "fn_core" in result
    assert "fn_other" not in result


def test_scope_filter_no_match():
    conn = _make_db()
    _add_stub(conn, "fn_a", "a.py", 1)
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {"scope": "nonexistent.py"})
    assert "No incomplete symbols" in result


def test_implemented_callee_not_in_graph():
    """An implemented function called by a stub should not appear in the output."""
    conn = _make_db()
    _add_stub(conn, "fn_stub", "a.py", 1)
    _add_impl(conn, "fn_impl", "a.py", 10)
    _add_edge(conn, "fn_stub", "fn_impl")
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    assert "fn_stub" in result
    assert "fn_impl" not in result


def test_cycle_detected():
    """Mutually recursive stubs (A calls B calls A) should be reported as a cycle group."""
    conn = _make_db()
    _add_stub(conn, "fn_p", "c.py", 1)
    _add_stub(conn, "fn_q", "c.py", 5)
    _add_edge(conn, "fn_p", "fn_q")
    _add_edge(conn, "fn_q", "fn_p")
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    # Both stubs appear in output
    assert "fn_p" in result
    assert "fn_q" in result


def test_mixed_stub_and_impl_callee_ordering():
    """fn_top calls fn_mid (stub) and fn_leaf (stub). fn_mid calls fn_leaf.
    Correct order: fn_leaf, fn_mid, fn_top."""
    conn = _make_db()
    _add_stub(conn, "fn_top", "d.py", 1)
    _add_stub(conn, "fn_mid", "d.py", 10)
    _add_stub(conn, "fn_leaf", "d.py", 20)
    _add_edge(conn, "fn_top", "fn_mid")
    _add_edge(conn, "fn_top", "fn_leaf")
    _add_edge(conn, "fn_mid", "fn_leaf")
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    lines = result.splitlines()
    pos = {name: next(i for i, l in enumerate(lines) if name in l) for name in ("fn_top", "fn_mid", "fn_leaf")}
    assert pos["fn_leaf"] < pos["fn_mid"] < pos["fn_top"]


def test_after_annotation_shown():
    """The 'After:' dependency annotation should appear for non-leaf stubs."""
    conn = _make_db()
    _add_stub(conn, "fn_root", "e.py", 1)
    _add_stub(conn, "fn_dep", "e.py", 5)
    _add_edge(conn, "fn_root", "fn_dep")
    conn.commit()
    oracle = _Oracle(conn)
    result = implementation_order(oracle, {})
    assert "After" in result
    assert "fn_dep" in result


def test_implementation_order_in_tools():
    """implementation_order must be registered in TOOLS."""
    from determined.agent.agent_tools import TOOLS
    assert "implementation_order" in TOOLS


def test_implementation_order_in_registry():
    """implementation_order must appear in tool_registry REGISTRY."""
    from determined.agent.tool_registry import REGISTRY
    assert "implementation_order" in REGISTRY
    entry = REGISTRY["implementation_order"]
    assert entry["category"] == "frontier"
