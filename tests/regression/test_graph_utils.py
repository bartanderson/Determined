# tests/regression/test_graph_utils.py
#
# Minimal tests for graph_utils.py against an in-memory SQLite DB.

import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _make_oracle(edges, functions=None, classes=None):
    """Build a minimal oracle stub with the given call graph."""
    import sqlite3

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute(
                "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER, "
                "source_id TEXT, target_id TEXT, caller_file TEXT, resolved INTEGER DEFAULT 0, "
                "edge_type TEXT DEFAULT 'static')"
            )
            self.conn.execute(
                "CREATE TABLE symbol_names (id INTEGER PRIMARY KEY, canonical_id TEXT, name TEXT, name_type TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            from determined.identity.symbol_identity import normalize_symbol, all_name_forms
            seen: set[tuple] = set()
            for caller, callee in edges:
                src_id = normalize_symbol(caller)
                tgt_id = normalize_symbol(callee)
                self.conn.execute(
                    "INSERT INTO graph_edges (caller, callee, line_number, source_id, target_id) VALUES (?,?,0,?,?)",
                    (caller, callee, src_id, tgt_id)
                )
                for name, ntype in all_name_forms(caller):
                    if (src_id, name) not in seen:
                        seen.add((src_id, name))
                        self.conn.execute(
                            "INSERT INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)",
                            (src_id, name, ntype)
                        )
                for name, ntype in all_name_forms(callee):
                    if (tgt_id, name) not in seen:
                        seen.add((tgt_id, name))
                        self.conn.execute(
                            "INSERT INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)",
                            (tgt_id, name, ntype)
                        )
            for name, fp in (functions or []):
                self.conn.execute(
                    "INSERT INTO functions VALUES (?,?,0,NULL)", (name, fp)
                )
            for name, fp in (classes or []):
                self.conn.execute(
                    "INSERT INTO classes VALUES (?,?,0,NULL)", (name, fp)
                )

    return _Oracle()


# ------------------------------------------------------------------

def test_find_entry_points_basic():
    from determined.agent.graph_utils import find_entry_points
    oracle = _make_oracle(
        edges=[("run_game", "start_encounter"), ("start_encounter", "generate_encounter")],
        functions=[("run_game", "main.py"), ("start_encounter", "engine.py"), ("generate_encounter", "enc.py")],
    )
    eps = find_entry_points(oracle)
    names = [e["name"] for e in eps]
    assert "run_game" in names
    assert "start_encounter" not in names
    assert "generate_encounter" not in names


def test_find_entry_points_excludes_tests():
    from determined.agent.graph_utils import find_entry_points
    oracle = _make_oracle(
        edges=[],
        functions=[
            ("run_game", "main.py"),
            ("test_run_game", "tests/test_main.py"),
        ],
    )
    eps = find_entry_points(oracle)
    names = [e["name"] for e in eps]
    assert "run_game" in names
    assert "test_run_game" not in names


def test_bfs_callees_basic():
    from determined.agent.graph_utils import bfs_callees
    oracle = _make_oracle(edges=[
        ("A", "B"), ("B", "C"), ("C", "D"),
    ])
    result = bfs_callees(oracle, "A", max_depth=3)
    syms = [r["symbol"] for r in result]
    assert "B" in syms
    assert "C" in syms
    assert "D" in syms


def test_bfs_callees_depth_limit():
    from determined.agent.graph_utils import bfs_callees
    oracle = _make_oracle(edges=[
        ("A", "B"), ("B", "C"), ("C", "D"),
    ])
    result = bfs_callees(oracle, "A", max_depth=1)
    syms = [r["symbol"] for r in result]
    assert "B" in syms
    assert "C" not in syms
    assert "D" not in syms


def test_shortest_path_direct():
    from determined.agent.graph_utils import shortest_path
    oracle = _make_oracle(edges=[("A", "B"), ("B", "C")])
    path = shortest_path(oracle, "A", "C")
    assert path == ["A", "B", "C"]


def test_shortest_path_none_when_unreachable():
    from determined.agent.graph_utils import shortest_path
    oracle = _make_oracle(edges=[("A", "B"), ("C", "D")])
    assert shortest_path(oracle, "A", "D") is None


def test_shortest_path_same_symbol():
    from determined.agent.graph_utils import shortest_path
    oracle = _make_oracle(edges=[])
    assert shortest_path(oracle, "A", "A") == ["A"]


def test_shortest_path_module_qualified_callee():
    """BFS must traverse edges where callee is module-qualified (Gap 1 fix)."""
    from determined.agent.graph_utils import shortest_path
    # Simulates: _answer → pkg.mod.resolve_and_expand → pkg.mod2.dispatch
    oracle = _make_oracle(edges=[
        ("_answer", "pkg.mod.resolve_and_expand"),
        ("resolve_and_expand", "pkg.mod2.dispatch"),
    ])
    path = shortest_path(oracle, "_answer", "dispatch")
    assert path is not None, "BFS should traverse module-qualified callee edges"
    assert path[0] == "_answer"
    assert path[-1] == "dispatch"


def test_most_connected_ordering():
    from determined.agent.graph_utils import most_connected
    # Provide file_path entries so project-symbol filter doesn't drop them all
    fns = [("A", "mod.py"), ("B", "mod.py"), ("C", "mod.py"), ("D", "mod.py"), ("X", "mod.py")]
    oracle = _make_oracle(edges=[
        ("A", "B"), ("A", "C"), ("A", "D"),  # A has out=3
        ("X", "B"),                            # B has in=2
    ], functions=fns)
    results = most_connected(oracle, n=10)
    syms = [r["symbol"] for r in results]
    # A (out=3, total=3) and B (in=2+1=3 with X->B) should be near top
    assert syms[0] in ("A", "B")


def test_find_clusters_basic():
    from determined.agent.graph_utils import find_clusters
    oracle = _make_oracle(
        edges=[("A", "B"), ("A", "C"), ("B", "A")],
        functions=[("A", "file1.py"), ("B", "file2.py"), ("C", "file3.py")],
    )
    clusters = find_clusters(oracle, min_edges=2)
    # file1.py and file2.py share 2 edges (A->B and B->A)
    assert any("file1.py" in c["files"] and "file2.py" in c["files"] for c in clusters)


def test_subgraph_around_radius():
    from determined.agent.graph_utils import subgraph_around
    oracle = _make_oracle(edges=[
        ("A", "B"), ("B", "C"), ("C", "D"), ("X", "Y")
    ])
    sg = subgraph_around(oracle, "B", radius=1)
    assert "A" in sg["nodes"]  # caller of B
    assert "B" in sg["nodes"]
    assert "C" in sg["nodes"]  # callee of B
    assert "D" not in sg["nodes"]  # too far
    assert "X" not in sg["nodes"]  # disconnected


def _make_oracle_with_resolved(edges_resolved):
    """Build oracle where each edge entry is (caller, callee, resolved: 0|1)."""
    import sqlite3
    from determined.identity.symbol_identity import normalize_symbol, all_name_forms

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute(
                "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER, "
                "source_id TEXT, target_id TEXT, caller_file TEXT, resolved INTEGER DEFAULT 0, "
                "edge_type TEXT DEFAULT 'static')"
            )
            self.conn.execute(
                "CREATE TABLE symbol_names (id INTEGER PRIMARY KEY, canonical_id TEXT, name TEXT, name_type TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            seen: set[tuple] = set()
            for caller, callee, resolved in edges_resolved:
                src_id = normalize_symbol(caller)
                tgt_id = normalize_symbol(callee)
                self.conn.execute(
                    "INSERT INTO graph_edges (caller, callee, line_number, source_id, target_id, resolved) VALUES (?,?,0,?,?,?)",
                    (caller, callee, src_id, tgt_id, resolved)
                )
                for name, ntype in all_name_forms(caller):
                    if (src_id, name) not in seen:
                        seen.add((src_id, name))
                        self.conn.execute(
                            "INSERT INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)",
                            (src_id, name, ntype)
                        )
                for name, ntype in all_name_forms(callee):
                    if (tgt_id, name) not in seen:
                        seen.add((tgt_id, name))
                        self.conn.execute(
                            "INSERT INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)",
                            (tgt_id, name, ntype)
                        )
            self.conn.commit()

    return _Oracle()


def test_bfs_callees_resolved_only_excludes_unresolved():
    """resolved_only=True must not traverse edges with resolved=0."""
    from determined.agent.graph_utils import bfs_callees
    # handle_connect -> get (unresolved, stdlib collision) -> bestiary_get (project fn)
    # handle_connect -> process (resolved, real project call)
    oracle = _make_oracle_with_resolved([
        ("handle_connect", "get", 0),
        ("get", "bestiary_get", 0),
        ("handle_connect", "process", 1),
    ])
    result = bfs_callees(oracle, "handle_connect", max_depth=3, resolved_only=True)
    syms = [r["symbol"] for r in result]
    assert "process" in syms, "resolved edge should be traversed"
    assert "get" not in syms, "unresolved edge target should be excluded"
    assert "bestiary_get" not in syms, "downstream of unresolved should not appear"


def test_subgraph_around_resolved_only():
    """resolved_only=True must restrict subgraph to resolved edges only."""
    from determined.agent.graph_utils import subgraph_around
    oracle = _make_oracle_with_resolved([
        ("A", "B", 1),   # resolved
        ("A", "C", 0),   # unresolved -- C should not appear
    ])
    sg = subgraph_around(oracle, "A", radius=1, resolved_only=True)
    assert "B" in sg["nodes"]
    assert "C" not in sg["nodes"]


def _make_oracle_for_tools(edges_resolved):
    """Oracle with graph_edges + symbol_references + symbols tables for agent_tools tests."""
    import sqlite3
    from determined.identity.symbol_identity import normalize_symbol

    class _Oracle:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute(
                "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER, "
                "source_id TEXT, target_id TEXT, caller_file TEXT, resolved INTEGER DEFAULT 0, "
                "edge_type TEXT DEFAULT 'static')"
            )
            self.conn.execute(
                "CREATE TABLE symbol_references (caller TEXT, callee TEXT, file_path TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE symbols (name TEXT, file_path TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE symbol_names (id INTEGER PRIMARY KEY, canonical_id TEXT, name TEXT, name_type TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            for caller, callee, resolved in edges_resolved:
                src_id = normalize_symbol(caller)
                tgt_id = normalize_symbol(callee)
                self.conn.execute(
                    "INSERT INTO graph_edges (caller, callee, line_number, source_id, target_id, resolved) VALUES (?,?,1,?,?,?)",
                    (caller, callee, src_id, tgt_id, resolved)
                )
            self.conn.commit()

    return _Oracle()


def test_list_callers_raw_resolved_only_filters_collision():
    """_list_callers_raw(resolved_only=True) must exclude unresolved bare-name collision edges."""
    from determined.agent.agent_tools import _list_callers_raw
    # handle_connect calls auth.get() (unresolved, stdlib) and real_caller calls get (resolved)
    oracle = _make_oracle_for_tools([
        ("handle_connect", "get", 0),  # unresolved collision -- should be excluded
        ("real_caller", "get", 1),     # annotation-resolved -- should be included
    ])
    rows = _list_callers_raw(oracle, "get", resolved_only=True)
    callers = [r["caller"] for r in rows]
    assert "real_caller" in callers, "resolved caller should appear"
    assert "handle_connect" not in callers, "unresolved collision caller should be excluded"


def test_list_callers_raw_default_includes_unresolved():
    """_list_callers_raw without resolved_only returns all edges (backward compat)."""
    from determined.agent.agent_tools import _list_callers_raw
    oracle = _make_oracle_for_tools([
        ("handle_connect", "get", 0),
        ("real_caller", "get", 1),
    ])
    rows = _list_callers_raw(oracle, "get")
    callers = [r["caller"] for r in rows]
    assert "handle_connect" in callers
    assert "real_caller" in callers


def test_list_callees_raw_resolved_only_filters_collision():
    """_list_callees_raw(resolved_only=True) must exclude unresolved outgoing edges."""
    from determined.agent.agent_tools import _list_callees_raw
    oracle = _make_oracle_for_tools([
        ("handle_connect", "get", 0),      # unresolved stdlib collision
        ("handle_connect", "process", 1),  # real project call, resolved
    ])
    rows = _list_callees_raw(oracle, "handle_connect", resolved_only=True)
    callees = [r["callee"] for r in rows]
    assert "process" in callees, "resolved callee should appear"
    assert "get" not in callees, "unresolved callee should be excluded"


def test_list_callees_raw_default_includes_unresolved():
    """_list_callees_raw without resolved_only returns all project callees (backward compat)."""
    from determined.agent.agent_tools import _list_callees_raw
    oracle = _make_oracle_for_tools([
        ("handle_connect", "get", 0),
        ("handle_connect", "process", 1),
    ])
    rows = _list_callees_raw(oracle, "handle_connect")
    callees = [r["callee"] for r in rows]
    assert "process" in callees
    assert "get" in callees


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
