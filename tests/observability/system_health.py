# tools/analysis/tests/observability/system_health.py

from collections import Counter
from dataclasses import dataclass
from typing import Any
from determined.engine.run_engine import EngineResult
from determined.observability.signal_contract import prune_signals
from determined.observability.instruments import (
    ingestion_instrument,
    graph_instrument,
    classification_instrument,
    propagation_instrument,
)

@dataclass
class HealthReport:
    file_count: int
    symbol_refs: int
    edge_count: int
    bucket_counts: dict
    warnings: list





def compute_health(snapshot: Any, signals=None):

    # ----------------------------------
    # normalize EngineResult vs dict
    # ----------------------------------
    if hasattr(snapshot, "facts"):
        facts = snapshot.facts
        file_analyses = getattr(snapshot.ingestion, "file_analyses", [])
        graph = snapshot.graph.get("graph") if isinstance(snapshot.graph, dict) else snapshot.graph
    else:
        facts = snapshot
        file_analyses = snapshot.get("file_analyses", [])
        graph = snapshot.get("graph")

    # ----------------------------------
    # unify facts access layer
    # ----------------------------------
    if hasattr(snapshot, "facts"):
        facts = snapshot.facts
    else:
        facts = snapshot

    # If engine didn't pass signals, reconstruct them defensively
    if signals is None:
        signals = []
        signals += ingestion_instrument(file_analyses)
        signals += graph_instrument(graph)
        signals += propagation_instrument(file_analyses, graph)
        signals += classification_instrument(file_analyses)

    signals = prune_signals(signals)

    bucket_counts = Counter()

    for s in signals:
        if s.name.startswith("bucket:"):
            bucket = s.name.split(":", 1)[1]
            bucket_counts[bucket] += s.value

    symbol_refs = facts.get("symbol_reference_count", 0)
    edge_count = facts.get("edge_count", 0)
    file_count = facts.get("file_count", 0)

    warnings = []

    if edge_count != symbol_refs:
        warnings.append(
            f"EDGE MISMATCH: edges={edge_count}, refs={symbol_refs}"
        )

    if file_count == 0:
        warnings.append("NO FILES PROCESSED")

    # NEW: signal-based structural sanity
    structure_signals = [s for s in signals if s.signal_class == "structure"]

    if len(structure_signals) == 0:
        warnings.append("NO STRUCTURE SIGNALS ACTIVE")

    return HealthReport(
        file_count=file_count,
        symbol_refs=symbol_refs,
        edge_count=edge_count,
        bucket_counts=dict(bucket_counts),
        warnings=warnings,
    )


def print_health(report: HealthReport) -> None:
    print("\n=== SYSTEM HEALTH REPORT ===\n")

    print("files:", report.file_count)
    print("symbol_refs:", report.symbol_refs)
    print("edges:", report.edge_count)

    print("\n--- BUCKETS ---")
    for k, v in report.bucket_counts.items():
        print(f"{k}: {v}")

    print("\n--- WARNINGS ---")
    if not report.warnings:
        print("OK")
    else:
        for w in report.warnings:
            print(w)