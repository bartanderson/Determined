# tools/analysis/observability/instruments.py
#
# OBSERVABILITY SCOPE (Option B -- RM73)
# =======================================
# MONITORED (signals emitted during EngineRunner.run):
#   ingestion_instrument  -- file_count, symbol_reference_count
#   graph_instrument      -- edge_count
#   classification_instrument -- bucket distribution (project/stdlib/unknown)
#   propagation_instrument -- edge_ref_ratio, edge_density
#
# NOT MONITORED (known gaps -- Option A follow-on work):
#   - Ingest failure / partial ingest (files silently skipped due to parse errors)
#   - Corpus returning empty on a non-empty source directory
#   - Query returning no results when results are expected (false-negative)
#   - Schema staleness (corpus predates a migration; call_arg_count=0 everywhere)
#   - Per-file re-ingest failure (reingest_file exceptions are logged but not signaled)
#   - Transitive dependent re-ingest coverage (find_transitive_dependents gaps)
#   - LLM call failure / timeout (llm_client errors are caught, not signaled)
#   - Corpus-level staleness (mtime drift -- covered by detect_changed_files,
#     not by a signal)
#
# All signals are structure-class only. No integrity, stability, or
# query-level signals are emitted at ingest time.

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