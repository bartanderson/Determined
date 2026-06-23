from determined.metrics.extract_metrics import extract_metrics
from determined.graph.evaluation_snapshot import build_evaluation_snapshot

def run_full_analysis_pipeline(file_analyses):
    """
    Single source of truth for:
    - snapshots
    - metrics
    - intermediate structures
    """

    # --------------------------
    # SNAPSHOT LAYER
    # --------------------------
    snapshots = file_analyses  # already snapshots from persistence layer

    # SIMPLE VALIDATION (PIPELINE GUARD)
    required_keys = ["edge_count", "bucket_summary", "failure_breakdown"]

    for i, s in enumerate(snapshots):
        for k in required_keys:
            if k not in s:
                raise ValueError(f"Snapshot[{i}] missing key: {k}")

    # --------------------------
    # METRICS LAYER
    # --------------------------
    metrics = extract_metrics(snapshots)

    # --------------------------
    # DERIVE L2 STRUCTURE (if needed later)
    # --------------------------
    # You can rehydrate graph if required in future
    # graph = rebuild_graph(...)

    return {
        "snapshots": snapshots,
        "metrics": metrics,
    }