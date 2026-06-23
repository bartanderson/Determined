# tools/analysis/graph/visualize_local_graph.py

from __future__ import annotations

from typing import List, Dict
import networkx as nx
import matplotlib.pyplot as plt


def visualize_local_graph(
    edges: List[Dict[str, str]],
    center_file: str,
    depth: int = 1,
) -> None:
    """
    Visualize only the local neighborhood of a file.

    This prevents overlap and makes graphs readable at scale.
    """

    G = nx.DiGraph()

    for edge in edges:
        G.add_edge(edge["from_file"], edge["to_file"])

    # BFS neighborhood extraction
    nodes_to_keep = {center_file}
    frontier = {center_file}

    for _ in range(depth):
        next_frontier = set()

        for node in frontier:
            next_frontier.update(G.successors(node))
            next_frontier.update(G.predecessors(node))

        nodes_to_keep.update(next_frontier)
        frontier = next_frontier

    subgraph = G.subgraph(nodes_to_keep)

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(subgraph, k=0.9)

    nx.draw_networkx_nodes(subgraph, pos, node_size=700, alpha=0.9)
    nx.draw_networkx_edges(subgraph, pos, arrows=True, alpha=0.3)

    labels = {
        node: node.split("/")[-1]
        for node in subgraph.nodes()
    }

    nx.draw_networkx_labels(subgraph, pos, labels, font_size=8)

    plt.title(f"Local Dependency Graph: {center_file.split('/')[-1]}")
    plt.axis("off")
    plt.show()