# determined/agent/risk_annotator.py
#
# Safe-zone / hot-zone risk scoring for symbols and files.
# Pure DB queries — no AI calls.
#
# HOT  : in_degree >= 5, OR (in_degree >= 3 AND mutations > 0)
# WARM : in_degree >= 2, OR mutations > 0
# SAFE : everything else (leaf nodes, low connectivity, no known mutations)
#
# Heuristic, not authoritative — misses dynamic dispatch and runtime writes.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle


def score_risk(oracle: "DBOracle", symbol: str) -> dict:
    """
    Score the change-risk of a symbol based on structural graph facts.
    Returns:
      level: "HOT" | "WARM" | "SAFE"
      in_degree: number of distinct callers
      out_degree: number of distinct callees
      mutation_count: times this symbol is a mutation target
      reasons: list of human-readable strings
    """
    # callers (in-degree): both bare name and module.name qualified form
    row = oracle.conn.execute(
        "SELECT COUNT(DISTINCT caller) FROM graph_edges WHERE callee = ? OR callee LIKE ?",
        (symbol, f"%.{symbol}"),
    ).fetchone()
    in_degree = row[0] if row else 0

    # callees (out-degree)
    row = oracle.conn.execute(
        "SELECT COUNT(DISTINCT callee) FROM graph_edges WHERE caller = ? OR caller LIKE ?",
        (symbol, f"%.{symbol}"),
    ).fetchone()
    out_degree = row[0] if row else 0

    # mutation events targeting this symbol
    row = oracle.conn.execute(
        "SELECT COUNT(*) FROM mutations WHERE target = ?",
        (symbol,),
    ).fetchone()
    mutation_count = row[0] if row else 0

    reasons: list[str] = []
    if in_degree >= 5:
        reasons.append(f"{in_degree} callers — wide blast radius")
    elif in_degree >= 2:
        reasons.append(f"{in_degree} callers")
    if mutation_count > 0:
        reasons.append(f"{mutation_count} mutation event(s) targeting this symbol")
    if not reasons:
        reasons.append("low connectivity, no known mutations")

    if in_degree >= 5 or (in_degree >= 3 and mutation_count > 0):
        level = "HOT"
    elif in_degree >= 2 or mutation_count > 0:
        level = "WARM"
    else:
        level = "SAFE"

    return {
        "level": level,
        "in_degree": in_degree,
        "out_degree": out_degree,
        "mutation_count": mutation_count,
        "reasons": reasons,
    }


def risk_badge(level: str) -> str:
    return {"HOT": "[HOT - review before changing]",
            "WARM": "[WARM - check callers]",
            "SAFE": "[SAFE]"}.get(level, f"[{level}]")
