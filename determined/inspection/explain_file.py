# tools/analysis/inspection/explain_file.py

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def explain_file(
    connection: sqlite3.Connection,
    file_path: str | Path,
) -> dict:
    file_path = str(Path(file_path))

    cursor = connection.cursor()

    # --------------------------
    # FILE IDENTITY
    # --------------------------
    cursor.execute("""
        SELECT role, is_hot, line_count
        FROM files
        WHERE file_path = ?
    """, (file_path,))
    file_row = cursor.fetchone() or ("unknown", 0, 0)

    role, is_hot, line_count = file_row

    # --------------------------
    # IMPORTS
    # --------------------------
    cursor.execute("""
        SELECT module, import_type
        FROM imports
        WHERE file_path = ?
    """, (file_path,))
    imports = cursor.fetchall()

    import_modules = [m for m, _ in imports]
    internal = sum(1 for m in import_modules if m.startswith("tools."))
    external = len(import_modules) - internal

    # --------------------------
    # SYMBOLS
    # --------------------------
    cursor.execute("""
        SELECT symbol_type
        FROM symbols
        WHERE file_path = ?
    """, (file_path,))
    symbol_rows = cursor.fetchall()

    symbol_types = [r[0] for r in symbol_rows]
    total_symbols = len(symbol_types)

    functions = symbol_types.count("function")
    classes = symbol_types.count("class")

    density_score = total_symbols / max(line_count or 1, 1)

    # --------------------------
    # SYMBOL REFERENCES
    # --------------------------
    cursor.execute("""
        SELECT caller, callee, bucket, edge_role
        FROM symbol_references
        WHERE file_path = ?
    """, (file_path,))
    refs = cursor.fetchall()

    top_callees = {}
    top_callers = {}
    bucket_counts = {}
    edge_role_counts = {}

    for caller, callee, bucket, edge_role in refs:
        top_callees[callee] = top_callees.get(callee, 0) + 1
        top_callers[caller] = top_callers.get(caller, 0) + 1

        bucket_counts[bucket or "unknown"] = bucket_counts.get(bucket or "unknown", 0) + 1
        edge_role_counts[edge_role or "unknown"] = edge_role_counts.get(edge_role or "unknown", 0) + 1

    def top_n(d: dict[str, int], n: int = 5):
        return sorted(
            [{"name": k, "count": v} for k, v in d.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:n]

    # --------------------------
    # CONTRACTS
    # --------------------------
    cursor.execute("""
        SELECT message, severity, contract_name
        FROM contract_violations
        WHERE file_path = ?
    """, (file_path,))
    violations_raw = cursor.fetchall()

    violations = [
        {
            "message": m,
            "severity": s,
            "contract": c,
        }
        for m, s, c in violations_raw
    ]

    risk_level = "low"
    if violations:
        risk_level = "high"
    elif density_score > 50:
        risk_level = "medium"

    # --------------------------
    # DEPENDENCIES
    # --------------------------
    cursor.execute("""
        SELECT module
        FROM imports
        WHERE file_path = ?
    """, (file_path,))
    outgoing = [r[0] for r in cursor.fetchall()]

    # --------------------------
    # SEMANTIC SUMMARY (heuristic compression)
    # --------------------------
    summary_parts = []

    summary_parts.append(f"This file is classified as '{role}'.")

    if is_hot:
        summary_parts.append("It is marked as hot (frequently used or critical).")

    summary_parts.append(
        f"It defines {functions} functions and {classes} classes with "
        f"{total_symbols} total symbols."
    )

    if external > internal:
        summary_parts.append("It depends more on external modules than internal ones.")

    if violations:
        summary_parts.append(f"There are {len(violations)} contract violations detected.")

    semantic_summary = " ".join(summary_parts)

    # --------------------------
    # FINAL OUTPUT
    # --------------------------
    return {
        "file_path": file_path,

        "identity": {
            "role": role,
            "is_hot": bool(is_hot),
            "line_count": line_count,
        },

        "imports": {
            "raw_count": len(imports),
            "top_modules": import_modules[:10],
            "internal_vs_external": {
                "internal": internal,
                "external": external,
            },
        },

        "symbols": {
            "total": total_symbols,
            "functions": functions,
            "classes": classes,
            "density_score": density_score,
        },

        "symbol_references": {
            "total": len(refs),
            "top_callees": top_n(top_callees),
            "top_callers": top_n(top_callers),
            "bucket_breakdown": bucket_counts,
            "edge_roles": edge_role_counts,
        },

        "contracts": {
            "violations": violations,
            "risk_level": risk_level,
            "summary": f"{len(violations)} violations detected" if violations else "No violations detected",
        },

        "dependencies": {
            "outgoing_modules": outgoing,
            "incoming_signals": [],  # placeholder for future graph enhancement
        },

        "semantic_summary": semantic_summary,
    }