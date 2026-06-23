# tools/analysis/metrics/extract_metrics.py

from __future__ import annotations

# MODULE: metrics
# OWNED: TRUE
#
# CONTRACT (LOCKED v1)
# - Aggregates snapshot outputs into system metrics
# - Must aggregate snapshot totals deterministically
# - Does NOT own classification or snapshot construction

def extract_metrics(snapshots):
    total_edges = 0

    bucket_totals = {
        "project": 0,
        "builtin": 0,
        "classification_gap": 0,
        "external_lib": 0,
        "runtime": 0,
        "unresolved_qualified_reference": 0,
    }

    failure_breakdown = {}
    unknown_samples = []

    for s in snapshots:
        total_edges += s["edge_count"]

        bs = s["bucket_summary"]
        bucket_totals["project"] += bs.get("project", 0)
        bucket_totals["builtin"] += bs.get("builtin", 0)
        bucket_totals["classification_gap"] += bs.get("classification_gap", 0)
        bucket_totals["external_lib"] += bs.get("external_lib", 0)
        bucket_totals["runtime"] += bs.get("runtime", 0)
        bucket_totals["unresolved_qualified_reference"] += bs.get("unresolved_qualified_reference", 0)

        for k, v in s.get("failure_breakdown", {}).items():
            failure_breakdown[k] = failure_breakdown.get(k, 0) + v

        unknown_samples.extend(s.get("unknown_samples", [])[:5])

    return {
        "total_edges": total_edges,
        "bucket_totals": bucket_totals,
        "failure_breakdown": failure_breakdown,
        "unknown_samples": unknown_samples[:50],
    }