# tools/analysis/inspection/system_shape.py

from __future__ import annotations

import sqlite3
from collections import defaultdict

def classify_symbol_domain(symbol: str, module: str | None = None) -> str:
    """
    Inspection-layer classification ONLY.
    Does not modify DB. Pure inference.
    """

    if not symbol:
        return "unknown"

    # builtin / python std heuristics
    BUILTIN_HINTS = {
        "print", "len", "str", "int", "dict", "list", "set",
        "open", "isinstance", "range", "max", "min"
    }

    if symbol in BUILTIN_HINTS:
        return "builtin"

    if module:
        if module.startswith("tools."):
            return "project"
        if module.startswith(("os", "sys", "re", "json", "datetime", "pathlib")):
            return "stdlib"
        return "external"

    return "unknown"
    
def generate_system_shape(connection: sqlite3.Connection) -> dict:
    cursor = connection.cursor()

    # --------------------------
    # FILE OVERVIEW
    # --------------------------
    cursor.execute("""
        SELECT file_path, role, is_hot, line_count
        FROM files
    """)
    files = cursor.fetchall()

    role_counts = defaultdict(int)
    hot_files = []
    total_lines = 0

    for file_path, role, is_hot, line_count in files:
        role_counts[role or "unknown"] += 1
        total_lines += line_count or 0

        if is_hot:
            hot_files.append(file_path)

    # --------------------------
    # IMPORT STRUCTURE
    # --------------------------
    cursor.execute("""
        SELECT file_path, module
        FROM imports
    """)
    imports = cursor.fetchall()

    external = 0
    internal = 0
    module_frequency = defaultdict(int)

    for _, module in imports:
        module_frequency[module] += 1
        if module.startswith("tools."):
            internal += 1
        else:
            external += 1

    # --------------------------
    # SYMBOL GRAPH DENSITY
    # --------------------------
    cursor.execute("""
        SELECT caller, callee, bucket, edge_role
        FROM symbol_references
    """)
    edges = cursor.fetchall()

    node_degree = defaultdict(int)
    node_bucket = defaultdict(lambda: defaultdict(int))
    cross_bucket_edges = defaultdict(int)

    for caller, callee, bucket, edge_role in edges:

        bucket = bucket or "unknown"

        caller_domain = classify_symbol_domain(caller)
        callee_domain = classify_symbol_domain(callee)

        # global coupling signal
        node_degree[caller] += 1
        node_degree[callee] += 1

        # bucketed projection (semantic view)
        node_bucket[caller_domain][caller] += 1
        node_bucket[callee_domain][callee] += 1

        # optional cross-boundary tracking
        if caller_domain != callee_domain:
            cross_bucket_edges[(caller_domain, callee_domain)] += 1

    top_connected = sorted(
        [
            (k, v)
            for k, v in node_degree.items()
        ],
        key=lambda x: x[1],
        reverse=True
    )[:10]

    top_connected_by_bucket = {
        bucket: sorted(
            nodes.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        for bucket, nodes in node_bucket.items()
    }

    # --------------------------
    # CONTRACT HEALTH
    # --------------------------
    cursor.execute("""
        SELECT severity, contract_name
        FROM contract_violations
    """)
    violations = cursor.fetchall()

    severity_counts = defaultdict(int)
    for severity, _ in violations:
        severity_counts[severity or "unknown"] += 1

    # --------------------------
    # SYSTEM SHAPE INFERENCE
    # --------------------------
    shape_tags = []

    if external > internal:
        shape_tags.append("external_dependency_heavy")

    if len(violations) > 20:
        shape_tags.append("contract_weak_system")

    if len(hot_files) > len(files) * 0.2:
        shape_tags.append("hotspot_concentrated")

    if max(node_degree.values(), default=0) > 50:
        shape_tags.append("high_coupling_core")

    if cross_bucket_edges:
        shape_tags.append("cross_layer_coupling_detected")

    # --------------------------
    # FINAL OUTPUT
    # --------------------------
    return {
        "file_count": len(files),
        "total_lines": total_lines,

        "role_distribution": dict(role_counts),

        "imports": {
            "internal": internal,
            "external": external,
            "top_modules": sorted(module_frequency.items(), key=lambda x: x[1], reverse=True)[:10],
        },

        "graph": {
            "edge_count": len(edges),
            "most_connected_nodes": [
                {"symbol": k, "degree": v} for k, v in top_connected
            ],
            "by_bucket": {
                bucket: dict(nodes)
                for bucket, nodes in node_bucket.items()
            },
            "cross_bucket_edges": dict(cross_bucket_edges),
        },

        "contracts": {
            "violations": len(violations),
            "severity": dict(severity_counts),
        },

        "hot_files": hot_files[:10],

        "system_shape_tags": shape_tags,
    }

def format_system_shape(shape: dict) -> str:
    lines = []

    lines.append("=" * 80)
    lines.append("SYSTEM SHAPE")
    lines.append("=" * 80)

    lines.append(f"Files: {shape['file_count']}")
    lines.append(f"Total Lines: {shape['total_lines']}")
    lines.append("")

    lines.append("Role Distribution:")
    for role, count in sorted(shape["role_distribution"].items()):
        lines.append(f"  {role}: {count}")

    lines.append("")
    lines.append("Imports:")
    lines.append(f"  Internal: {shape['imports']['internal']}")
    lines.append(f"  External: {shape['imports']['external']}")

    lines.append("")
    lines.append("Top Imported Modules:")
    for module, count in shape["imports"]["top_modules"]:
        lines.append(f"  {count:>4}  {module}")

    lines.append("")
    lines.append("Graph:")
    lines.append(f"  Edge Count: {shape['graph']['edge_count']}")

    lines.append("")
    lines.append("Most Connected Symbols:")
    for item in shape["graph"]["most_connected_nodes"]:
        lines.append(
            f"  {item['degree']:>4}  {item['symbol']}"
        )

    lines.append("")
    lines.append("Contracts:")
    lines.append(
        f"  Violations: {shape['contracts']['violations']}"
    )

    for severity, count in sorted(
        shape["contracts"]["severity"].items()
    ):
        lines.append(f"    {severity}: {count}")

    lines.append("")
    lines.append("Hot Files:")
    for file_path in shape["hot_files"]:
        lines.append(f"  {file_path}")

    lines.append("")
    lines.append("Shape Tags:")
    for tag in shape["system_shape_tags"]:
        lines.append(f"  {tag}")

    lines.append("=" * 80)

    return "\n".join(lines)