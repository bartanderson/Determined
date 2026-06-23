# tools/analysis/engine/engine_snapshot_diff.py

from dataclasses import asdict, is_dataclass
from typing import Any, Dict


def _normalize(obj: Any) -> Any:
    """
    Convert snapshot into comparable primitives only.
    No semantic interpretation.
    """

    if is_dataclass(obj):
        return _normalize(asdict(obj))

    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_normalize(x) for x in obj]

    if isinstance(obj, set):
        return sorted(list(obj))

    return obj


def diff_snapshots(engine_snapshot: Any, pipeline_snapshot: Any) -> Dict[str, Any]:

    eng = _normalize(engine_snapshot)
    pipe = _normalize(pipeline_snapshot)

    missing_keys_engine = []
    missing_keys_pipeline = []
    mismatched_values = []

    def walk(a, b, path=""):
        if isinstance(a, dict) and isinstance(b, dict):
            a_keys = set(a.keys())
            b_keys = set(b.keys())

            for k in a_keys - b_keys:
                missing_keys_pipeline.append(f"{path}.{k}" if path else k)

            for k in b_keys - a_keys:
                missing_keys_engine.append(f"{path}.{k}" if path else k)

            for k in a_keys & b_keys:
                walk(a[k], b[k], f"{path}.{k}" if path else k)

        else:
            if a != b:
                mismatched_values.append({
                    "path": path,
                    "engine": a,
                    "pipeline": b,
                })

    walk(eng, pipe)

    return {
        "missing_keys_engine": missing_keys_engine,
        "missing_keys_pipeline": missing_keys_pipeline,
        "mismatched_values": mismatched_values,
        "match": (
            not missing_keys_engine
            and not missing_keys_pipeline
            and not mismatched_values
        ),
    }


def print_snapshot_diff(diff: Dict[str, Any]) -> None:

    print("\n=== SNAPSHOT PARITY DIFF ===")

    print("\nmissing_keys_engine:", len(diff["missing_keys_engine"]))
    for k in diff["missing_keys_engine"]:
        print(" -", k)

    print("\nmissing_keys_pipeline:", len(diff["missing_keys_pipeline"]))
    for k in diff["missing_keys_pipeline"]:
        print(" -", k)

    print("\nmismatched_values:", len(diff["mismatched_values"]))
    for m in diff["mismatched_values"]:
        print(" -", m["path"], "=> engine:", m["engine"], "| pipeline:", m["pipeline"])

    print("\nMATCH:", diff["match"])