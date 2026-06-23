# tools/analysis/engine/parity_contract.py

from typing import Dict, Any


REQUIRED_BUCKETS = [
    "project",
    "runtime",
    "builtin",
    "stdlib",
    "external",
    "unresolved",
]


def normalize_snapshot(raw: Dict[str, Any]) -> Dict[str, Any]:
    buckets = raw.get("buckets", {}) or {}

    return {
        "file_count": int(raw.get("file_count", 0)),
        "symbol_reference_count": int(raw.get("symbol_reference_count", 0)),
        "edge_count": int(raw.get("edge_count", 0)),
        "buckets": {
            k: int(buckets.get(k, 0))
            for k in REQUIRED_BUCKETS
        },
    }


def compare(engine: Dict[str, Any], pipeline: Dict[str, Any]) -> Dict[str, Any]:
    e = normalize_snapshot(engine)
    p = normalize_snapshot(pipeline)

    diffs = {}

    if e["file_count"] != p["file_count"]:
        diffs["file_count"] = (e["file_count"], p["file_count"])

    if e["symbol_reference_count"] != p["symbol_reference_count"]:
        diffs["symbol_reference_count"] = (
            e["symbol_reference_count"],
            p["symbol_reference_count"],
        )

    if e["edge_count"] != p["edge_count"]:
        diffs["edge_count"] = (e["edge_count"], p["edge_count"])

    bucket_diffs = {}
    for k in REQUIRED_BUCKETS:
        if e["buckets"][k] != p["buckets"][k]:
            bucket_diffs[k] = (e["buckets"][k], p["buckets"][k])

    if bucket_diffs:
        diffs["buckets"] = bucket_diffs

    return {
        "passed": len(diffs) == 0,
        "diffs": diffs,
    }
    