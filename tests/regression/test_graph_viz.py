# tests/regression/test_graph_viz.py - minimal tests for graph_viz.py

import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _oracle(edges, functions=None):
    class _O:
        def __init__(self):
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("CREATE TABLE graph_edges (caller TEXT, callee TEXT, line_number INTEGER)")
            self.conn.execute("CREATE TABLE functions (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)")
            self.conn.execute("CREATE TABLE classes (name TEXT, file_path TEXT, line_number INTEGER, docstring TEXT)")
            for c, e in edges:
                self.conn.execute("INSERT INTO graph_edges VALUES (?,?,0)", (c, e))
            for n, fp in (functions or []):
                self.conn.execute("INSERT INTO functions VALUES (?,?,0,NULL)", (n, fp))
    return _O()


def test_text_tree_basic():
    from determined.agent.graph_viz import to_text_tree
    oracle = _oracle([("A", "B"), ("B", "C")])
    tree = to_text_tree(oracle, "A", max_depth=3)
    assert "A" in tree
    assert "B" in tree
    assert "C" in tree


def test_text_tree_depth_limit():
    from determined.agent.graph_viz import to_text_tree
    oracle = _oracle([("A", "B"), ("B", "C"), ("C", "D")])
    tree = to_text_tree(oracle, "A", max_depth=1)
    assert "B" in tree
    assert "C" not in tree


def test_to_dot_basic():
    from determined.agent.graph_viz import to_dot
    dot = to_dot(["A", "B"], [("A", "B")], title="test")
    assert "digraph" in dot
    assert '"A"' in dot
    assert '"B"' in dot
    assert '"A" -> "B"' in dot


def test_to_dot_highlight():
    from determined.agent.graph_viz import to_dot
    dot = to_dot(["A", "B"], [("A", "B")], highlight=["A"])
    assert "filled" in dot


def test_subgraph_dot_produces_valid_dot():
    from determined.agent.graph_viz import subgraph_dot
    oracle = _oracle([("A", "B"), ("B", "C")], functions=[("A", "f.py"), ("B", "f.py"), ("C", "f.py")])
    dot = subgraph_dot(oracle, "B", radius=1)
    assert "digraph" in dot
    assert "B" in dot


def test_clusters_dot_basic():
    from determined.agent.graph_viz import clusters_dot
    clusters = [{"files": ["world/a.py", "world/b.py"], "edge_count": 5}]
    dot = clusters_dot(clusters)
    assert "digraph" in dot
    assert "a.py" in dot
    assert "b.py" in dot


def test_save_dot_writes_file(tmp_path):
    from determined.agent.graph_viz import save_dot, to_dot
    dot = to_dot(["A", "B"], [("A", "B")])
    path = str(tmp_path / "test.dot")
    msg = save_dot(dot, path, render=False)
    assert os.path.exists(path)
    assert "written" in msg


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
