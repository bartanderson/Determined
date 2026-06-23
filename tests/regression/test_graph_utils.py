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
                "CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER)"
            )
            self.conn.execute(
                "CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            self.conn.execute(
                "CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)"
            )
            for caller, callee in edges:
                self.conn.execute(
                    "INSERT INTO graph_edges VALUES (?,?,0)", (caller, callee)
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


def test_most_connected_ordering():
    from determined.agent.graph_utils import most_connected
    oracle = _make_oracle(edges=[
        ("A", "B"), ("A", "C"), ("A", "D"),  # A has out=3
        ("X", "B"),                            # B has in=2
    ])
    results = most_connected(oracle, n=10)
    syms = [r["symbol"] for r in results]
    # A (out=3, total=3) and B (in=2, total=2+1=3 with X->B) should be near top
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


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
