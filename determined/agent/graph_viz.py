# tools/analysis/agent/graph_viz.py
#
# Visual output for call graphs. Two formats:
#   - ASCII text tree (terminal, always works)
#   - Graphviz DOT (export to .dot, render with graphviz)
#
# All functions take pre-computed nodes/edges or an oracle + symbol.
# Keeps rendering separate from graph traversal (graph_utils.py).

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle

from determined.agent.graph_utils import bfs_callees, subgraph_around


# ------------------------------------------------------------------
# ASCII call tree
# ------------------------------------------------------------------

def to_text_tree(
    oracle: "DBOracle",
    root: str,
    max_depth: int = 3,
    max_nodes: int = 40,
) -> str:
    """
    Render a call tree rooted at `root` as indented ASCII text.
    Shows what root calls, what those call, etc.
    """
    lines = [root]
    visited: set[str] = {root}

    def _walk(symbol: str, depth: int, prefix: str) -> None:
        if depth > max_depth or len(lines) >= max_nodes:
            return
        rows = oracle.conn.execute(
            "SELECT DISTINCT callee FROM graph_edges WHERE caller = ? ORDER BY callee",
            (symbol,)
        ).fetchall()
        for i, row in enumerate(rows):
            if len(lines) >= max_nodes:
                lines.append(f"{prefix}... (truncated)")
                return
            callee = row[0]
            connector = "└── " if i == len(rows) - 1 else "├── "
            if callee in visited:
                lines.append(f"{prefix}{connector}{callee} (seen)")
                continue
            visited.add(callee)
            lines.append(f"{prefix}{connector}{callee}")
            extension = "    " if i == len(rows) - 1 else "│   "
            _walk(callee, depth + 1, prefix + extension)

    _walk(root, 1, "")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Graphviz DOT export
# ------------------------------------------------------------------

def to_dot(
    nodes: list[str],
    edges: list[tuple[str, str]],
    title: str = "call_graph",
    highlight: list[str] | None = None,
) -> str:
    """
    Render nodes + edges as a Graphviz DOT string.
    highlight: list of node names to render in a different color (e.g. entry points).
    """
    highlight_set = set(highlight or [])
    lines = [
        f'digraph "{title}" {{',
        '  rankdir=LR;',
        '  node [shape=box fontname="Helvetica" fontsize=10];',
        '  edge [fontsize=8];',
        '',
    ]

    for node in sorted(nodes):
        label = node.replace('"', '\\"')
        if node in highlight_set:
            lines.append(f'  "{label}" [style=filled fillcolor="#aed6f1"];')
        else:
            lines.append(f'  "{label}";')

    lines.append('')
    for src, dst in sorted(edges):
        lines.append(f'  "{src}" -> "{dst}";')

    lines.append('}')
    return "\n".join(lines)


# ------------------------------------------------------------------
# Subgraph DOT (convenience: subgraph_around + to_dot)
# ------------------------------------------------------------------

def subgraph_dot(
    oracle: "DBOracle",
    symbol: str,
    radius: int = 2,
    highlight_entry_points: bool = True,
) -> str:
    """
    Build a DOT diagram of the call graph around `symbol` within `radius` hops.
    Entry point nodes (no callers) are highlighted blue.
    """
    sg = subgraph_around(oracle, symbol, radius=radius)

    highlight = []
    if highlight_entry_points:
        called = {r[0] for r in oracle.conn.execute(
            "SELECT DISTINCT callee FROM graph_edges"
        ).fetchall()}
        highlight = [n for n in sg["nodes"] if n not in called]

    return to_dot(
        sg["nodes"],
        sg["edges"],
        title=f"subgraph_{symbol}",
        highlight=highlight,
    )


# ------------------------------------------------------------------
# Save DOT to file and optionally render to PNG
# ------------------------------------------------------------------

def save_dot(dot_str: str, path: str, render: bool = False) -> str:
    """
    Write DOT string to `path`. If render=True and graphviz is installed,
    also renders to a PNG at the same path with .png extension.
    Returns a status message.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(dot_str)

    if not render:
        return f"DOT written to {path}"

    try:
        import graphviz
        src = graphviz.Source(dot_str)
        out = path.replace(".dot", "")
        src.render(out, format="png", cleanup=True)
        return f"DOT written to {path}, PNG rendered to {out}.png"
    except Exception as e:
        return f"DOT written to {path} (PNG render failed: {e})"


# ------------------------------------------------------------------
# Cluster diagram DOT
# ------------------------------------------------------------------

def clusters_dot(clusters: list[dict], title: str = "clusters", top_n: int = 20) -> str:
    """
    Render file-level clusters as a DOT diagram.
    Each file is a node; edge weight reflects call density between files.
    `clusters` is the output of graph_utils.find_clusters().
    """
    top = clusters[:top_n]
    nodes: set[str] = set()
    edges = []
    for c in top:
        f1, f2 = c["files"][0], c["files"][1]
        # Shorten to filename only for readability
        n1 = f1.replace("\\", "/").split("/")[-1]
        n2 = f2.replace("\\", "/").split("/")[-1]
        nodes.add(n1)
        nodes.add(n2)
        edges.append((n1, n2, c["edge_count"]))

    lines = [
        f'digraph "{title}" {{',
        '  rankdir=LR;',
        '  node [shape=ellipse fontname="Helvetica" fontsize=9];',
        '',
    ]
    for n in sorted(nodes):
        lines.append(f'  "{n}";')
    lines.append('')
    for src, dst, weight in edges:
        lines.append(f'  "{src}" -> "{dst}" [label="{weight}" penwidth={min(weight, 5)}];')
    lines.append('}')
    return "\n".join(lines)
