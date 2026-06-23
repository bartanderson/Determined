# tools/analysis/engine/invariants.py

def run_integrity_check(graph, facts):
    errors = []

    edges = getattr(graph, "edges", [])

    # 1. edge count
    if len(edges) != facts["symbol_reference_count"]:
        errors.append("edge_count_mismatch")

    # 2. edge structure
    for e in edges:
        if not e.caller or not e.callee:
            errors.append("invalid_edge")

    return {
        "ok": len(errors) == 0,
        "errors": errors
    }