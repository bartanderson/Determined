# tools/analysis/observability/fault_injector.py

import random


def inject_edge_drop(graph, rate=0.1):
    edges = list(getattr(graph, "edges", []))
    keep = []

    for e in edges:
        if random.random() > rate:
            keep.append(e)

    graph.edges = keep
    return graph


def inject_classification_drift(file_analyses, rate=0.1):
    buckets = ["project", "external", "builtin", "stdlib"]

    for a in file_analyses:
        for r in a.symbol_references:
            if random.random() < rate:
                r.bucket = random.choice(buckets)

    return file_analyses