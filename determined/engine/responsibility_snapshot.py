# tools/analysis/engine/responsibility_snapshot.py

from typing import Dict, Any


def build_responsibility_snapshot(
    responsibility_map: Dict[str, Any],
    db_totals: Dict[str, int],
) -> Dict[str, Any]:
    """
    Pipeline-side projection of engine snapshot.

    IMPORTANT RULE:
    - This does NOT compute anything new.
    - It only reduces already-known data into SnapshotV1 shape.
    """

    buckets = responsibility_map.get("buckets", {}) or {}

    return {
        "engine": {
            "file_count": int(db_totals.get("file_count", 0)),
            "symbol_reference_count": int(db_totals.get("symbol_reference_count", 0)),
            "edge_count": int(db_totals.get("edge_count", 0)),
        },

        "responsibility": responsibility_map,
    }