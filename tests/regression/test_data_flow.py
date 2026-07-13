"""Regression tests for RM39: data_flow edge emission and data_flow_edges tool."""
import ast
import sqlite3
import textwrap
import pytest

from determined.ingestion.parse_ast import _extract_symbol_references
from determined.agent.agent_tools import data_flow_edges


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _refs_from_source(source: str):
    tree = ast.parse(source)
    return _extract_symbol_references(
        tree,
        known_symbols=set(),
        alias_map={},
        module_name="test_mod",
    )


def _make_db(edges=None, functions=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            target_id TEXT,
            caller TEXT,
            callee TEXT,
            line_number INTEGER,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            edge_type TEXT DEFAULT 'static'
        )
    """)
    conn.execute("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            file_path TEXT,
            is_stub INTEGER DEFAULT 0
        )
    """)
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, edge_type) VALUES (?,?,?,?,?)",
            e,
        )
    for f in (functions or []):
        conn.execute("INSERT INTO functions (name, file_path) VALUES (?,?)", f)
    conn.commit()
    return conn


class _Oracle:
    def __init__(self, conn):
        self.conn = conn


class _Assessor:
    def __init__(self, conn):
        self.oracle = _Oracle(conn)


# ---------------------------------------------------------------------------
# parse_ast: data_flow edge emission
# ---------------------------------------------------------------------------

def test_nested_call_emits_data_flow_edge():
    """fn_b(fn_a()) should produce a data_flow edge: fn_b -> fn_a."""
    source = textwrap.dedent("""\
        def outer():
            result = fn_b(fn_a())
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 1
    ref = data_flow[0]
    # fqdn is module-qualified; check suffix
    assert ref.caller.endswith("fn_b")
    assert ref.callee.endswith("fn_a")


def test_nested_call_also_has_static_edges():
    """fn_b(fn_a()) should still produce static edges for both calls."""
    source = textwrap.dedent("""\
        def outer():
            fn_b(fn_a())
    """)
    refs = _refs_from_source(source)
    static = [r for r in refs if r.edge_type == "static"]
    callees = {r.callee for r in static}
    assert any(c.endswith("fn_b") for c in callees)
    assert any(c.endswith("fn_a") for c in callees)


def test_plain_call_no_data_flow_edge():
    """fn_b(x) where x is not a call should not produce data_flow edges."""
    source = textwrap.dedent("""\
        def outer():
            fn_b(x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0


def test_multiple_nested_calls():
    """fn_c(fn_a(), fn_b()) produces two data_flow edges: fn_c->fn_a and fn_c->fn_b."""
    source = textwrap.dedent("""\
        def outer():
            fn_c(fn_a(), fn_b())
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 2
    assert all(r.caller.endswith("fn_c") for r in data_flow)
    callees = {r.callee for r in data_flow}
    assert any(c.endswith("fn_a") for c in callees)
    assert any(c.endswith("fn_b") for c in callees)


def test_variable_binding_emits_data_flow_edge():
    """result = fn_a(); fn_b(result) -- Level 2 variable binding -> data_flow edge."""
    source = textwrap.dedent("""\
        def outer():
            result = fn_a()
            fn_b(result)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 1
    ref = data_flow[0]
    assert ref.caller.endswith("fn_b")
    assert ref.callee.endswith("fn_a")


# ---------------------------------------------------------------------------
# data_flow_edges tool
# ---------------------------------------------------------------------------

def test_data_flow_edges_out():
    """direction='out' shows which functions consume fn_a's return value."""
    conn = _make_db(edges=[
        ("fn_b", "fn_a", "fn_b", "fn_a", "data_flow"),
        ("fn_c", "fn_a", "fn_c", "fn_a", "data_flow"),
    ])
    result = data_flow_edges(_Assessor(conn), {"symbol": "fn_a", "direction": "out"})
    assert "fn_b" in result
    assert "fn_c" in result
    assert "RETURN VALUE" in result


def test_data_flow_edges_in():
    """direction='in' shows what fn_b consumes return values from."""
    conn = _make_db(edges=[
        ("fn_b", "fn_a", "fn_b", "fn_a", "data_flow"),
    ])
    result = data_flow_edges(_Assessor(conn), {"symbol": "fn_b", "direction": "in"})
    assert "fn_a" in result
    assert "CONSUMES" in result


def test_data_flow_edges_both():
    """direction='both' shows both CONSUMES and RETURN VALUE sections."""
    conn = _make_db(edges=[
        ("fn_b", "fn_a", "fn_b", "fn_a", "data_flow"),
        ("fn_c", "fn_b", "fn_c", "fn_b", "data_flow"),
    ])
    result = data_flow_edges(_Assessor(conn), {"symbol": "fn_b", "direction": "both"})
    assert "CONSUMES" in result
    assert "RETURN VALUE" in result
    assert "fn_a" in result
    assert "fn_c" in result


def test_data_flow_edges_no_symbol():
    result = data_flow_edges(_Assessor(_make_db()), {"symbol": ""})
    assert "symbol" in result.lower()


def test_data_flow_edges_default_direction_is_out():
    """Default direction is 'out' -- shows RETURN VALUE section."""
    conn = _make_db(edges=[
        ("fn_b", "fn_a", "fn_b", "fn_a", "data_flow"),
    ])
    result = data_flow_edges(_Assessor(conn), {"symbol": "fn_a"})
    assert "RETURN VALUE" in result
    assert "fn_b" in result


def test_data_flow_edges_total_count():
    """Output includes total data_flow edge count."""
    conn = _make_db(edges=[
        ("fn_b", "fn_a", "fn_b", "fn_a", "data_flow"),
        ("fn_c", "fn_a", "fn_c", "fn_a", "data_flow"),
    ])
    result = data_flow_edges(_Assessor(conn), {"symbol": "fn_a"})
    assert "Total data_flow edges in corpus: 2" in result


# ---------------------------------------------------------------------------
# Level 2: variable binding tracking
# ---------------------------------------------------------------------------

def test_variable_rebound_uses_latest_binding():
    """When a variable is reassigned, only the latest binding is tracked."""
    source = textwrap.dedent("""\
        def outer():
            x = fn_a()
            x = fn_b()
            fn_c(x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    callees = {r.callee for r in data_flow}
    assert any(c.endswith("fn_b") for c in callees), "latest binding should be fn_b"
    assert not any(c.endswith("fn_a") for c in callees), "stale binding fn_a should not appear"


def test_binding_does_not_cross_function_boundary():
    """A variable binding from one function must not leak into a nested function."""
    source = textwrap.dedent("""\
        def outer():
            x = fn_a()
            def inner():
                fn_b(x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0, "binding from outer must not be visible inside inner"


def test_unbound_name_arg_produces_no_data_flow():
    """fn_b(x) where x was not assigned from a call produces no data_flow edge."""
    source = textwrap.dedent("""\
        def outer(x):
            fn_b(x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0


def test_module_level_assignment_not_tracked():
    """result = fn_a() at module level (outside any function) is not tracked."""
    source = textwrap.dedent("""\
        result = fn_a()
        fn_b(result)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0


def test_level1_and_level2_coexist():
    """fn_c(fn_a(), result) where result=fn_b() produces two data_flow edges."""
    source = textwrap.dedent("""\
        def outer():
            result = fn_b()
            fn_c(fn_a(), result)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 2
    assert all(r.caller.endswith("fn_c") for r in data_flow)
    callees = {r.callee for r in data_flow}
    assert any(c.endswith("fn_a") for c in callees)
    assert any(c.endswith("fn_b") for c in callees)


def test_chained_variable_bindings():
    """a = fn_a(); b = fn_b(a); fn_c(b) -- chain of variable bindings."""
    source = textwrap.dedent("""\
        def outer():
            a = fn_a()
            b = fn_b(a)
            fn_c(b)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    # fn_b(a) -> data_flow fn_b->fn_a; fn_c(b) -> data_flow fn_c->fn_b
    assert len(data_flow) == 2
    callers = {r.caller for r in data_flow}
    assert any(c.endswith("fn_b") for c in callers)
    assert any(c.endswith("fn_c") for c in callers)


def test_multiple_functions_bindings_are_independent():
    """Two functions with same variable name have independent bindings."""
    source = textwrap.dedent("""\
        def first():
            x = fn_a()
            fn_b(x)

        def second():
            x = fn_c()
            fn_d(x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 2
    pairs = {(r.caller.split(".")[-1], r.callee.split(".")[-1]) for r in data_flow}
    assert ("fn_b", "fn_a") in pairs
    assert ("fn_d", "fn_c") in pairs


# ---------------------------------------------------------------------------
# Level 3: for-loop over call result + keyword-arg variable pass
# ---------------------------------------------------------------------------

def test_for_loop_over_call_emits_data_flow_edge():
    """for x in fn_a() -> data_flow edge (outer) -> fn_a."""
    source = textwrap.dedent("""\
        def outer():
            for x in fn_a():
                pass
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 1
    assert data_flow[0].caller.endswith("outer")
    assert data_flow[0].callee.endswith("fn_a")
    assert data_flow[0].identity.provenance == ["data_flow_for_iter"]


def test_for_loop_binds_loop_var_for_downstream():
    """for x in fn_a(): fn_b(x) -> two data_flow edges: outer->fn_a, fn_b->fn_a."""
    source = textwrap.dedent("""\
        def outer():
            for x in fn_a():
                fn_b(x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 2
    provs = {r.identity.provenance[0] for r in data_flow}
    assert "data_flow_for_iter" in provs
    assert "data_flow_var" in provs


def test_for_loop_attribute_iter_emits_edge():
    """for x in obj.get_items() -> data_flow edge outer -> obj.get_items."""
    source = textwrap.dedent("""\
        def outer():
            for x in obj.get_items():
                pass
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 1
    assert "get_items" in data_flow[0].callee


def test_for_loop_over_name_not_call_no_data_flow():
    """for x in items -> items is not a call, no data_flow edge emitted."""
    source = textwrap.dedent("""\
        def outer():
            items = [1, 2, 3]
            for x in items:
                pass
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0


def test_keyword_arg_variable_pass_emits_data_flow():
    """fn_b(key=result) where result=fn_a() -> data_flow edge fn_b -> fn_a."""
    source = textwrap.dedent("""\
        def outer():
            result = fn_a()
            fn_b(key=result)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 1
    assert data_flow[0].caller.endswith("fn_b")
    assert data_flow[0].callee.endswith("fn_a")
    assert data_flow[0].identity.provenance == ["data_flow_var_kwarg"]


def test_kwargs_unpack_not_tracked():
    """fn_b(**result) should not emit a data_flow edge."""
    source = textwrap.dedent("""\
        def outer():
            result = fn_a()
            fn_b(**result)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0


def test_keyword_arg_unbound_var_no_data_flow():
    """fn_b(key=x) where x is not from a call -> no data_flow edge."""
    source = textwrap.dedent("""\
        def outer(x):
            fn_b(key=x)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 0


def test_level3_coexists_with_level1_and_level2():
    """fn_d(fn_a(), result, key=other) where result=fn_b(), other=fn_c() -> 3 edges."""
    source = textwrap.dedent("""\
        def outer():
            result = fn_b()
            other = fn_c()
            fn_d(fn_a(), result, key=other)
    """)
    refs = _refs_from_source(source)
    data_flow = [r for r in refs if r.edge_type == "data_flow"]
    assert len(data_flow) == 3
    callees = {r.callee for r in data_flow}
    assert any(c.endswith("fn_a") for c in callees)
    assert any(c.endswith("fn_b") for c in callees)
    assert any(c.endswith("fn_c") for c in callees)
