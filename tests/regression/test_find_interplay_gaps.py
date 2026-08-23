"""
Regression tests for find_interplay_gaps.
Uses in-memory SQLite seeded with controlled fixtures.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock
from determined.agent.agent_tools import find_interplay_gaps


def _make_oracle(conn):
    oracle = MagicMock()
    oracle.conn = conn
    return oracle


def _seed_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY,
            name TEXT, file_path TEXT, is_stub INTEGER DEFAULT 0,
            return_type TEXT, arguments_json TEXT, param_types_json TEXT,
            docstring TEXT, decorators_json TEXT, http_route TEXT,
            is_tool INTEGER DEFAULT 0, class_name TEXT, line_number INTEGER
        );
        CREATE TABLE IF NOT EXISTS graph_edges (
            id INTEGER PRIMARY KEY,
            source_id TEXT, target_id TEXT,
            caller TEXT, callee TEXT, line_number INTEGER,
            caller_file TEXT, resolved INTEGER DEFAULT 1, edge_type TEXT
        );
    """)


# ---------------------------------------------------------------------------
# 1. Unresolved edges between implemented functions
# ---------------------------------------------------------------------------

def test_unresolved_impl_edge_detected():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('caller_fn', 'app/a.py', 0)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file, resolved) VALUES ('caller_fn', 'missing_fn', 'app/a.py', 0)")
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "caller_fn -> missing_fn" in result
    assert "UNRESOLVED EDGES" in result


def test_stub_caller_excluded_from_unresolved():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('stub_fn', 'app/a.py', 1)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file, resolved) VALUES ('stub_fn', 'missing_fn', 'app/a.py', 0)")
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "stub_fn -> missing_fn" not in result


# ---------------------------------------------------------------------------
# 2. Production edges not covered by tests
# ---------------------------------------------------------------------------

def test_uncovered_prod_edge_detected():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('prod_fn', 'app/b.py', 0)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file, resolved) VALUES ('prod_fn', 'other_fn', 'app/b.py', 1)")
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "prod_fn -> other_fn" in result
    assert "PRODUCTION EDGES NOT EXERCISED" in result


def test_covered_prod_edge_not_flagged():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('prod_fn', 'app/b.py', 0)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file, resolved) VALUES ('prod_fn', 'other_fn', 'app/b.py', 1)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file, resolved) VALUES ('test_prod_fn', 'other_fn', 'app/tests/test_b.py', 1)")
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "all production edges have test coverage" in result


# ---------------------------------------------------------------------------
# 3. Interaction hubs
# ---------------------------------------------------------------------------

def test_interaction_hub_detected():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('hub_fn', 'app/c.py', 0)")
    hub_fan = 3
    for i in range(hub_fan):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?, 'hub_fn', 'app/x.py')",
            (f"caller_{i}",),
        )
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file) VALUES ('hub_fn', ?, 'app/c.py')",
            (f"callee_{i}",),
        )
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {"hub_fan": str(hub_fan)})
    assert "hub_fn" in result
    assert "INTERACTION HUBS" in result


# ---------------------------------------------------------------------------
# 4. Circular file dependencies
# ---------------------------------------------------------------------------

def test_circular_file_dep_detected():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('fn_b', 'app/b.py', 0)")
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('fn_a', 'app/a.py', 0)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file) VALUES ('fn_a', 'fn_b', 'app/a.py')")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file) VALUES ('fn_b', 'fn_a', 'app/b.py')")
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "CIRCULAR FILE DEPENDENCIES" in result
    assert "a.py" in result and "b.py" in result


# ---------------------------------------------------------------------------
# 5. Tightly-coupled file pairs
# ---------------------------------------------------------------------------

def test_tight_coupling_detected():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('fn_b', 'app/b.py', 0)")
    for i in range(3):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?, 'fn_b', 'app/a.py')",
            (f"fn_a_{i}",),
        )
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {"threshold": "3"})
    assert "TIGHTLY-COUPLED" in result
    assert "a.py" in result and "b.py" in result


def test_below_threshold_not_flagged():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.execute("INSERT INTO functions (name, file_path, is_stub) VALUES ('fn_b', 'app/b.py', 0)")
    conn.execute("INSERT INTO graph_edges (caller, callee, caller_file) VALUES ('fn_a', 'fn_b', 'app/a.py')")
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {"threshold": "5"})
    assert "none with >=" in result


# ---------------------------------------------------------------------------
# Clean corpus -- all sections report clean
# ---------------------------------------------------------------------------

def test_clean_corpus_no_findings():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "INTERPLAY GAP ANALYSIS" in result
    assert "none found" in result.lower() or "no " in result.lower() or "all production" in result.lower()


def _seed_db_with_call_arg_count(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY,
            name TEXT, file_path TEXT, is_stub INTEGER DEFAULT 0,
            return_type TEXT, arguments_json TEXT, param_types_json TEXT,
            docstring TEXT, decorators_json TEXT, http_route TEXT,
            is_tool INTEGER DEFAULT 0, class_name TEXT, line_number INTEGER
        );
        CREATE TABLE IF NOT EXISTS graph_edges (
            id INTEGER PRIMARY KEY,
            source_id TEXT, target_id TEXT,
            caller TEXT, callee TEXT, line_number INTEGER,
            caller_file TEXT, resolved INTEGER DEFAULT 1,
            edge_type TEXT DEFAULT 'static',
            call_arg_count INTEGER
        );
    """)


# ---------------------------------------------------------------------------
# 6. Argument count mismatches
# ---------------------------------------------------------------------------

def test_arg_count_mismatch_detected():
    conn = sqlite3.connect(":memory:")
    _seed_db_with_call_arg_count(conn)
    # callee declares 2 params (self excluded), caller passes 3
    conn.execute(
        "INSERT INTO functions (name, file_path, is_stub, arguments_json) VALUES (?, ?, 0, ?)",
        ("callee_fn", "app/b.py", '["self", "x", "y"]'),
    )
    conn.execute(
        "INSERT INTO graph_edges (caller, callee, caller_file, resolved, edge_type, call_arg_count) "
        "VALUES (?, ?, ?, 1, 'static', 3)",
        ("caller_fn", "callee_fn", "app/a.py"),
    )
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "ARGUMENT COUNT MISMATCHES" in result
    assert "caller_fn -> callee_fn" in result
    assert "passed=3" in result
    assert "declared=2" in result


def test_arg_count_match_not_flagged():
    conn = sqlite3.connect(":memory:")
    _seed_db_with_call_arg_count(conn)
    # callee declares 2 params (self excluded), caller passes 2 -- no mismatch
    conn.execute(
        "INSERT INTO functions (name, file_path, is_stub, arguments_json) VALUES (?, ?, 0, ?)",
        ("callee_fn", "app/b.py", '["self", "x", "y"]'),
    )
    conn.execute(
        "INSERT INTO graph_edges (caller, callee, caller_file, resolved, edge_type, call_arg_count) "
        "VALUES (?, ?, ?, 1, 'static', 2)",
        ("caller_fn", "callee_fn", "app/a.py"),
    )
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "none found" in result.lower() or "caller_fn -> callee_fn" not in result


def test_old_db_without_call_arg_count_column():
    # Section 6 must degrade gracefully on old corpus DBs lacking the column
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)  # old schema, no call_arg_count column
    conn.commit()

    result = find_interplay_gaps(_make_oracle(conn), {})
    assert "INTERPLAY GAP ANALYSIS" in result  # tool must not crash
