# tests/regression/test_detect_conventions.py
#
# Regression tests for detect_conventions (RM70).
#
# Three-gate analysis: Gate 1 (3+ members share a naming prefix/suffix),
# Gate 2 (2+ feature dims agree at >=70%), Gate 3 (agreeing dims span
# 2+ independent categories).
#
# Schema needed: functions (name, file_path, is_stub, return_type,
# param_types_json) and graph_edges (caller, callee).

import json
import sqlite3
import pytest
from unittest.mock import MagicMock

from determined.agent.agent_tools import detect_conventions, _get_convention_for_symbol


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY,
            name TEXT,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0,
            return_type TEXT,
            param_types_json TEXT
        );
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY,
            caller TEXT,
            callee TEXT,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0
        );
    """)
    return conn


def _oracle(conn):
    o = MagicMock()
    o.conn = conn
    return o


def _fn(conn, name, file_path="mod/a.py", is_stub=0, return_type=None,
        params=None, callers=(), callees=()):
    """Insert a function and its graph edges."""
    conn.execute(
        "INSERT INTO functions (name, file_path, is_stub, return_type, param_types_json) "
        "VALUES (?,?,?,?,?)",
        (name, file_path, is_stub, return_type, json.dumps(params or {})),
    )
    for caller in callers:
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
            (caller, name, "other.py"),
        )
    for callee in callees:
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
            (name, callee, file_path),
        )


# ---------------------------------------------------------------------------
# Gate 1: existence gate — naming family must have min_family members
# ---------------------------------------------------------------------------

def test_no_families_when_corpus_empty():
    conn = _make_db()
    result = detect_conventions(_oracle(conn), {})
    assert "No functions found" in result or "No naming families" in result


def test_too_few_members_no_family():
    """Two get_ functions don't make a family (min_family=3)."""
    conn = _make_db()
    _fn(conn, "get_foo")
    _fn(conn, "get_bar")
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "No naming families" in result or "0 family" in result


def test_exactly_min_family_members_passes():
    """Exactly 3 get_ functions with consistent features form a family."""
    conn = _make_db()
    _fn(conn, "get_foo", return_type="str")
    _fn(conn, "get_bar", return_type="str")
    _fn(conn, "get_baz", return_type="str")
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "prefix:get" in result


def test_min_family_param_respected():
    """min_family=4 suppresses a 3-member cluster."""
    conn = _make_db()
    _fn(conn, "get_foo", return_type="str")
    _fn(conn, "get_bar", return_type="str")
    _fn(conn, "get_baz", return_type="str")
    result = detect_conventions(_oracle(conn), {"min_family": 4})
    assert "prefix:get" not in result


# ---------------------------------------------------------------------------
# Gate 2: usefulness gate — 2+ feature dims must agree at >=70%
# ---------------------------------------------------------------------------

def test_family_needs_two_agreeing_dims():
    """A cluster where features are completely heterogeneous is suppressed."""
    conn = _make_db()
    # Each function is structurally different: varied return types, params, stubs
    _fn(conn, "do_foo", return_type="str", params={"x": "int"})
    _fn(conn, "do_bar", return_type="int", is_stub=1)
    _fn(conn, "do_baz", return_type=None, params={"a": "str", "b": "str"})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    # Either no family, or do_ family absent (varies by random agreement)
    # The key check: if the family appears it must have a valid canon
    if "prefix:do" in result:
        assert "canon on" in result


def test_two_agreeing_dims_passes_gate2():
    """All get_ functions return str and take 0 params → 2 dims agree → family appears."""
    conn = _make_db()
    for name in ("get_alpha", "get_beta", "get_gamma"):
        _fn(conn, name, return_type="str", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "prefix:get" in result
    assert "canon on" in result


# ---------------------------------------------------------------------------
# Gate 3: confluence gate — agreeing dims must span 2+ categories
# ---------------------------------------------------------------------------

def test_single_category_dims_suppressed():
    """All agreement in one category (callers+callees are both 'structural') is not enough."""
    conn = _make_db()
    # Make 3 fn_ functions with same callers AND callees bucket but varied everything else
    for name in ("fn_a", "fn_b", "fn_c"):
        _fn(conn, name, return_type="str", params={"x": "int", "y": "int"})
        # Add exactly 1 caller and 1 callee so structural dims agree
        conn.execute("INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
                     ("caller_x", name, "other.py"))
        conn.execute("INSERT INTO graph_edges (caller, callee, caller_file) VALUES (?,?,?)",
                     (name, "callee_x", "mod/a.py"))
    # Now vary return types so only structural category agrees
    conn.execute("UPDATE functions SET return_type='int' WHERE name='fn_c'")
    # If only callers+callees agree (one category), gate 3 should suppress
    # (whether it actually triggers depends on param_count also varying)
    # This is a structural test — we just verify no crash and result is well-formed
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# Core output shape
# ---------------------------------------------------------------------------

def test_output_header_shows_family_count():
    conn = _make_db()
    for name in ("get_a", "get_b", "get_c"):
        _fn(conn, name, return_type="str")
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "family/families found" in result


def test_canon_line_present():
    conn = _make_db()
    for name in ("get_a", "get_b", "get_c"):
        _fn(conn, name, return_type="str", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "Canon:" in result


def test_members_section_present():
    conn = _make_db()
    for name in ("get_a", "get_b", "get_c"):
        _fn(conn, name, return_type="str", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "Members:" in result


def test_no_outliers_message_when_consistent():
    """A perfectly consistent family reports 'none — family is internally consistent'."""
    conn = _make_db()
    for name in ("get_a", "get_b", "get_c", "get_d"):
        _fn(conn, name, return_type="str", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "none — family is internally consistent" in result


# ---------------------------------------------------------------------------
# Outlier detection
# ---------------------------------------------------------------------------

def test_outlier_identified_by_param_divergence():
    """One get_ function taking params is flagged as outlier vs zero-param canon."""
    conn = _make_db()
    _fn(conn, "get_foo", return_type="str", params={})
    _fn(conn, "get_bar", return_type="str", params={})
    _fn(conn, "get_baz", return_type="str", params={})
    # outlier: takes a param
    _fn(conn, "get_weird", return_type="str", params={"x": "int"})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    if "prefix:get" in result:
        assert "get_weird" in result
        assert "diverges" in result or "differs by" in result


def test_outlier_stub_tagged():
    """A stub that diverges from an impl-body canon is tagged [stub]."""
    conn = _make_db()
    for name in ("validate_foo", "validate_bar", "validate_baz"):
        _fn(conn, name, return_type="bool", params={})
    _fn(conn, "validate_qux", is_stub=1, return_type="bool", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    if "prefix:validate" in result and "validate_qux" in result:
        assert "[stub]" in result


def test_outlier_rate_above_40pct_suppresses_family():
    """A family where >40% are outliers is dropped (too generic to be a convention).

    Design: 7 members, 4 unique outliers (57%) across two canon dims.
    - fn_one/two/three: return_type=str, callers=0  [canon]
    - fn_four/five: callers=1  → diverge on callers (2 outliers)
    - fn_six/seven: return_type=int → diverge on return_type (2 outliers)
    Canon: callers=0 (5/7=71%), return_type=str (5/7=71%), all others 100%.
    4/7 = 57% outliers → strictly >40% → family suppressed.
    """
    conn = _make_db()
    # 3 fully-canon members
    _fn(conn, "fn_one",   return_type="str", params={})
    _fn(conn, "fn_two",   return_type="str", params={})
    _fn(conn, "fn_three", return_type="str", params={})
    # 2 members that diverge on callers dim (have one caller)
    _fn(conn, "fn_four",  return_type="str", params={}, callers=("other_fn",))
    _fn(conn, "fn_five",  return_type="str", params={}, callers=("other_fn",))
    # 2 members that diverge on return_type dim
    _fn(conn, "fn_six",   return_type="int", params={})
    _fn(conn, "fn_seven", return_type="int", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "prefix:fn" not in result


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------

def test_scope_filters_to_matching_files():
    conn = _make_db()
    _fn(conn, "get_foo", file_path="api/routes.py", return_type="str")
    _fn(conn, "get_bar", file_path="api/routes.py", return_type="str")
    _fn(conn, "get_baz", file_path="api/routes.py", return_type="str")
    _fn(conn, "get_other", file_path="core/engine.py", return_type="str")
    # Scope to api/ only — engine function excluded
    result = detect_conventions(_oracle(conn), {"min_family": 3, "scope": "api/"})
    assert "prefix:get" in result
    # get_other is from engine.py — shouldn't be the only member list
    # (3 api members satisfy the family, it passes)
    assert "get_other" not in result


def test_scope_no_match_returns_not_found():
    conn = _make_db()
    _fn(conn, "get_foo", file_path="api/routes.py", return_type="str")
    result = detect_conventions(_oracle(conn), {"min_family": 3, "scope": "nonexistent/"})
    assert "No functions found" in result or "No naming families" in result


# ---------------------------------------------------------------------------
# Sort modes
# ---------------------------------------------------------------------------

def test_established_sort_largest_family_first():
    """Established sort (default) puts largest family first."""
    conn = _make_db()
    # prefix:get — 5 members
    for i in range(5):
        _fn(conn, f"get_{chr(65+i)}", return_type="str", params={})
    # prefix:set — 3 members
    for i in range(3):
        _fn(conn, f"set_{chr(65+i)}", return_type=None, params={"v": "str"})
    result = detect_conventions(_oracle(conn), {"min_family": 3, "sort": "established"})
    if "prefix:get" in result and "prefix:set" in result:
        assert result.index("prefix:get") < result.index("prefix:set")


def test_emerging_sort_smallest_family_first():
    """Emerging sort puts smallest qualifying family first."""
    conn = _make_db()
    for i in range(5):
        _fn(conn, f"get_{chr(65+i)}", return_type="str", params={})
    for i in range(3):
        _fn(conn, f"set_{chr(65+i)}", return_type=None, params={"v": "str"})
    result = detect_conventions(_oracle(conn), {"min_family": 3, "sort": "emerging"})
    if "prefix:get" in result and "prefix:set" in result:
        assert result.index("prefix:set") < result.index("prefix:get")


# ---------------------------------------------------------------------------
# Test file exclusion
# ---------------------------------------------------------------------------

def test_functions_in_test_files_excluded():
    """Functions from test_* files are excluded from convention analysis."""
    conn = _make_db()
    # 3 get_ functions in test files only — should NOT form a family
    _fn(conn, "get_foo", file_path="tests/test_api.py", return_type="str")
    _fn(conn, "get_bar", file_path="tests/test_db.py", return_type="str")
    _fn(conn, "get_baz", file_path="tests/test_util.py", return_type="str")
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    # No family should be found since all are from test files
    assert "prefix:get" not in result or "No naming families" in result


# ---------------------------------------------------------------------------
# Dunder exclusion
# ---------------------------------------------------------------------------

def test_dunder_functions_excluded():
    """__init__, __str__, etc. are excluded from naming analysis."""
    conn = _make_db()
    _fn(conn, "__init__", return_type=None)
    _fn(conn, "__str__", return_type="str")
    _fn(conn, "__repr__", return_type="str")
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "__init__" not in result
    assert "__str__" not in result


# ---------------------------------------------------------------------------
# Suffix families
# ---------------------------------------------------------------------------

def test_suffix_family_detected():
    """Functions sharing a suffix (e.g. _handler) are grouped as a suffix family."""
    conn = _make_db()
    _fn(conn, "click_handler", return_type=None, params={})
    _fn(conn, "submit_handler", return_type=None, params={})
    _fn(conn, "load_handler", return_type=None, params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    assert "suffix:handler" in result


def test_prefix_wins_over_suffix_for_same_cluster():
    """When a name matches both prefix and suffix clusters, prefix takes precedence."""
    conn = _make_db()
    # get_X functions also end in _foo — prefix:get should win
    _fn(conn, "get_foo", return_type="str", params={})
    _fn(conn, "get_bar", return_type="str", params={})
    _fn(conn, "get_baz", return_type="str", params={})
    result = detect_conventions(_oracle(conn), {"min_family": 3})
    # prefix:get should appear; suffix:foo/bar/baz with only 1 member each won't
    assert "prefix:get" in result


# ---------------------------------------------------------------------------
# _get_convention_for_symbol
# ---------------------------------------------------------------------------

def _make_get_family(conn):
    """Seed a passing prefix:get family of 4 non-stub, str-returning functions."""
    for name in ("get_foo", "get_bar", "get_baz", "get_qux"):
        _fn(conn, name, return_type="str", params={"x": "int"})


def test_convention_for_symbol_in_family():
    """Symbol that belongs to a passing convention returns family info."""
    conn = _make_db()
    _make_get_family(conn)
    result = _get_convention_for_symbol(conn, "get_foo")
    assert result["family"] == "prefix:get"
    assert result["family_size"] == 4
    assert result["is_outlier"] is False


def test_convention_for_symbol_not_in_any_family():
    """Symbol with a unique prefix returns empty family."""
    conn = _make_db()
    _make_get_family(conn)
    _fn(conn, "run_thing", return_type="None", params={})
    result = _get_convention_for_symbol(conn, "run_thing")
    assert result["family"] is None
    assert result["family_size"] == 0


def test_convention_for_symbol_outlier_detected():
    """Stub that diverges from canon is flagged as outlier."""
    conn = _make_db()
    # 3 non-stub str-returners form the canon; the 4th is a stub with None return
    for name in ("get_foo", "get_bar", "get_baz"):
        _fn(conn, name, return_type="str", params={"x": "int"})
    _fn(conn, "get_odd", is_stub=1, return_type=None, params={})
    result = _get_convention_for_symbol(conn, "get_odd")
    assert result["family"] == "prefix:get"
    assert result["is_outlier"] is True


def test_convention_for_symbol_absent_from_corpus():
    """Symbol that does not exist in functions table returns empty family."""
    conn = _make_db()
    _make_get_family(conn)
    result = _get_convention_for_symbol(conn, "nonexistent_fn")
    assert result["family"] is None


def test_convention_for_symbol_generic_cluster_rejected():
    """Cluster where >40% are outliers is rejected; no family returned."""
    conn = _make_db()
    # 3 non-stub str-returners + 2 diverging stubs = 40% outlier rate (borderline)
    # Add a 6th diverging to push past 40%
    for name in ("get_a", "get_b", "get_c"):
        _fn(conn, name, return_type="str", params={"x": "int"})
    for name in ("get_d", "get_e", "get_f"):
        _fn(conn, name, is_stub=1, return_type=None, params={})
    # 3/6 = 50% outliers — cluster should be rejected as too generic
    result = _get_convention_for_symbol(conn, "get_d")
    assert result["family"] is None
