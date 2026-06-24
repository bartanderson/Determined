# determined/viz/stub_density.py
#
# Stub density visualization: bar chart of stub count per module,
# colored by mean neighbor cyclomatic complexity.
#
# Usage:
#   python -m determined.viz.stub_density <corpus.db>
#   python -m determined.viz.stub_density <corpus.db> --out stubs.png

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _module_from_path(file_path: str) -> str:
    p = Path(file_path)
    parts = p.parts
    for i, part in enumerate(parts):
        if part in ("analysis", "tools"):
            if i + 1 < len(parts) - 1:
                return parts[i + 1]
    return p.stem if p.stem != "__init__" else (p.parent.name or p.stem)


def _neighbor_complexity(conn, stub_name: str) -> float:
    """Mean cyclomatic complexity of direct callers + callees of stub_name."""
    rows = conn.execute(
        """
        SELECT DISTINCT f.name
        FROM functions f
        JOIN (
            SELECT caller AS neighbor FROM graph_edges WHERE callee = ?
            UNION
            SELECT callee AS neighbor FROM graph_edges WHERE caller = ?
        ) n ON f.name = n.neighbor
        WHERE f.is_stub = 0
        """,
        (stub_name, stub_name),
    ).fetchall()

    if not rows:
        return 0.0

    complexities = []
    for (name,) in rows:
        (edge_count,) = conn.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE caller = ?", (name,)
        ).fetchone()
        complexities.append(edge_count)

    return sum(complexities) / len(complexities)


def plot_stub_density(db_path: str, out_path: str | None = None) -> None:
    import sqlite3
    import pandas as pd
    from plotnine import (
        ggplot, aes, geom_col, coord_flip, scale_fill_gradient,
        labs, theme_minimal, theme, element_text,
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    stubs = conn.execute(
        "SELECT file_path, name FROM functions WHERE is_stub = 1"
    ).fetchall()

    if not stubs:
        print("No stubs found in corpus.")
        conn.close()
        return

    print(f"{len(stubs)} stubs found.")

    rows = []
    for s in stubs:
        module = _module_from_path(s["file_path"])
        complexity = _neighbor_complexity(conn, s["name"])
        rows.append({"module": module, "stub": s["name"], "neighbor_complexity": complexity})

    conn.close()

    df = pd.DataFrame(rows)
    agg = (
        df.groupby("module")
        .agg(stub_count=("stub", "count"), mean_complexity=("neighbor_complexity", "mean"))
        .reset_index()
        .sort_values("stub_count", ascending=False)
    )

    p = (
        ggplot(agg, aes(x="reorder(module, stub_count)", y="stub_count", fill="mean_complexity"))
        + geom_col()
        + coord_flip()
        + scale_fill_gradient(low="#a8d8ea", high="#e84545", name="neighbor\ncomplexity")
        + labs(
            title="Stub density by module",
            subtitle="Color = mean cyclomatic complexity of neighboring functions",
            x="Module",
            y="Stub count",
        )
        + theme_minimal()
        + theme(figure_size=(10, max(4, len(agg) * 0.4)))
    )

    if out_path:
        p.save(out_path, dpi=150)
        print(f"Saved to {out_path}")
    else:
        p.draw()
        import matplotlib.pyplot as plt
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stub density chart for a corpus DB.")
    parser.add_argument("db_path", help="Path to corpus .db file")
    parser.add_argument("--out", help="Save to file instead of showing interactively")
    args = parser.parse_args()
    plot_stub_density(args.db_path, out_path=args.out)
