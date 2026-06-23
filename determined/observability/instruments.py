# tools/analysis/observability/instruments.py

from collections import Counter

from determined.observability.signals import Signal


def ingestion_instrument(file_analyses):
    return [
        Signal(
            name="file_count",
            value=len(file_analyses),
            unit="count",
            stage="ingestion",
            signal_class="structure",
        ),
        Signal(
            name="symbol_reference_count",
            value=sum(
                len(a.symbol_references)
                for a in file_analyses
            ),
            unit="count",
            stage="ingestion",
            signal_class="structure",
        ),
    ]


def graph_instrument(graph):
    return [
        Signal(
            name="edge_count",
            value=len(getattr(graph, "edges", [])),
            unit="count",
            stage="graph",
            signal_class="structure",
        ),
    ]


def classification_instrument(file_analyses):
    bucket_counts = Counter()

    for a in file_analyses:
        for r in a.symbol_references:
            bucket = getattr(r, "bucket", "unknown")
            bucket_counts[bucket] += 1

    return [
        Signal(
            name=f"bucket:{k}",
            value=v,
            unit="count",
            stage="classification",
            signal_class="structure",
        )
        for k, v in bucket_counts.items()
    ]

def propagation_instrument(file_analyses, graph):
    """
    Measures whether structure changes propagate across the system graph.
    """

    total_edges = len(getattr(graph, "edges", []))
    symbol_refs = sum(len(a.symbol_references) for a in file_analyses)

    if symbol_refs == 0:
        ratio = 0
    else:
        ratio = total_edges / symbol_refs

    return [
        Signal(
            name="edge_ref_ratio",
            value=ratio,
            unit="ratio",
            stage="propagation",
            signal_class="propagation",
        ),
        Signal(
            name="edge_density",
            value=total_edges,
            unit="count",
            stage="propagation",
            signal_class="propagation",
        ),
    ]