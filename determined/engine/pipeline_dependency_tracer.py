# tools/analysis/engine/pipeline_dependency_tracer.py

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class PipelineDependencyReport:
    entry_points: list[str]
    edges: list[tuple[str, str]]
    engine_candidates: set[str]
    pipeline_only: set[str]
    truth_usage: set[str]
    ccss_usage: set[str]


ENGINE_HINTS = {
    "scan_project_files",
    "classify_references",
    "GraphBuilder",
    "persist_file_analysis",
    "build_evaluation_snapshot",
    "reduce",
}

TRUTH_HINTS = {
    "build_structure_view",
    "build_stability_view",
    "build_integrity_view",
    "QueryExecutor",
}

CCSS_HINTS = {
    "snapshot_store",
    "snapshot_compare",
    "run_check",
    "regression_check",
}


from collections import defaultdict

class PipelineReport:
    def __init__(self, data: dict):
        self.__dict__.update(data)


def trace_pipeline_dependencies(analysis_index):
    engine_hits = set()
    truth_hits = set()
    ccss_hits = set()

    entry_points = set()
    edges = []
    outgoing = defaultdict(set)

    def normalize(x):
        if x is None:
            return ""
        if isinstance(x, str):
            return x
        if hasattr(x, "module") and hasattr(x, "name"):
            return f"{x.module}.{x.name}"
        return str(x)

    def classify(name: str):
        if "determined.engine" in name or "engine" in name:
            return "engine"
        if "truth" in name:
            return "truth"
        if "ccss" in name:
            return "ccss"
        return "pipeline"

    for file, data in analysis_index.items():

        imports = data.get("imports", [])
        calls = data.get("calls", [])

        entry_points.add(file)

        for imp in imports:
            imp_str = normalize(imp)
            
            # -------------------------
            # PIPELINE DETECTION DEBUG
            # -------------------------
            if "pipeline" in imp_str:
                print("[PIPELINE MATCH]", file, "->", imp_str)

            bucket = classify(imp_str)

            if bucket == "engine":
                engine_hits.add(imp_str)
            elif bucket == "truth":
                truth_hits.add(imp_str)
            elif bucket == "ccss":
                ccss_hits.add(imp_str)

        for call in calls:
            call_str = normalize(call)
            edges.append((file, call_str))
            outgoing[file].add(call_str)

            bucket = classify(call_str)

            if bucket == "engine":
                engine_hits.add(call_str)
            elif bucket == "truth":
                truth_hits.add(call_str)
            elif bucket == "ccss":
                ccss_hits.add(call_str)

    all_calls = set(call for _, call in edges)

    engine_only = {c for c in all_calls if classify(c) == "engine"}
    truth_only = {c for c in all_calls if classify(c) == "truth"}
    ccss_only = {c for c in all_calls if classify(c) == "ccss"}
    pipeline_only = {c for c in all_calls if classify(c) == "pipeline"}

    data = {
        # core graph
        "entry_points": entry_points,
        "edges": edges,

        # raw buckets
        "engine_hits": engine_hits,
        "truth_hits": truth_hits,
        "ccss_hits": ccss_hits,

        # derived sets
        "engine_only": engine_only,
        "truth_only": truth_only,
        "ccss_only": ccss_only,
        "pipeline_only": pipeline_only,
    }

    # -----------------------------
    # PRINTER CONTRACT LAYER FIX
    # -----------------------------

    # what print_pipeline_report expects
    data["engine_candidates"] = data["engine_hits"]
    data["truth_usage"] = data["truth_hits"]
    data["ccss_usage"] = data["ccss_hits"]

    return PipelineReport(data)


def print_pipeline_report(report: PipelineDependencyReport) -> None:
    print("\n=== PIPELINE DEPENDENCY REPORT ===")

    print("\nENTRY POINTS:", len(report.entry_points))
    print("EDGES:", len(report.edges))

    print("\nENGINE CANDIDATES:", len(report.engine_candidates))
    for e in sorted(report.engine_candidates):
        print("  ", e)

    print("\nTRUTH USAGE:", len(report.truth_usage))
    for e in sorted(report.truth_usage):
        print("  ", e)

    print("\nCCSS USAGE:", len(report.ccss_usage))
    for e in sorted(report.ccss_usage):
        print("  ", e)

    print("\nPIPELINE-ONLY CALLS:", len(report.pipeline_only))
    for e in sorted(report.pipeline_only)[:50]:
        print("  ", e)

def _normalize_import(imp) -> str:
    """
    Convert ImportRepresentation (or raw strings) into comparable text.
    """
    if imp is None:
        return ""

    # already string
    if isinstance(imp, str):
        return imp

    # common AST-style objects
    for attr in ("name", "module", "value", "path"):
        if hasattr(imp, attr):
            val = getattr(imp, attr)
            if isinstance(val, str):
                return val

    # fallback
    return str(imp)