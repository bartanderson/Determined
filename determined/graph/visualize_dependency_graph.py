# tools/analysis/graph/visualize_dependency_graph.py

from __future__ import annotations

from typing import List, Dict
import networkx as nx
import matplotlib.pyplot as plt


def visualize_dependency_graph(edges: List[Dict[str, str]]) -> None:
    """
    Scalable dependency graph visualization (improved layout + readability)
    """

    G = nx.DiGraph()

    for edge in edges:
        G.add_edge(edge["from_file"], edge["to_file"])

    plt.figure(figsize=(16, 12))

    # Better layout for medium/large graphs
    pos = nx.kamada_kawai_layout(G)

    # Nodes
    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=500,
        alpha=0.85,
    )

    # Edges (slightly transparent to reduce clutter)
    nx.draw_networkx_edges(
        G,
        pos,
        arrows=True,
        alpha=0.25,
        width=1.0,
    )

    # Short labels only (filename, not full path)
    labels = {
        node: node.split("/")[-1]
        for node in G.nodes()
    }

    nx.draw_networkx_labels(
        G,
        pos,
        labels,
        font_size=7,
    )

    plt.title("Dependency Graph (Readable Layout)")
    plt.axis("off")
    plt.tight_layout()
    plt.show()