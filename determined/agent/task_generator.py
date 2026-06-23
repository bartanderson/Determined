# tools/analysis/agent/task_generator.py
#
# Generates task.md - a plain Markdown checklist of everything that may need
# review when a given symbol changes.
#
# Two-tier result model (see TRACKER.md item 6 audit, 2026-06-19):
#   Tier 1 - "Direct callers (confirmed)": graph_edges WHERE callee = symbol.
#             These are the exact files/lines that call the symbol directly.
#   Tier 2 - "Impact zone (may need review)": route_query() with seeds=[symbol]
#             override. This is the reverse-closure neighborhood from that
#             specific symbol, not a token-match superset.
#
# The generator writes task.md to a path chosen by the caller, or returns the
# content as a string if no path is given.

from __future__ import annotations

import textwrap
from datetime import date
from typing import Optional


def generate_task_md(
    symbol: str,
    oracle,
    out_path: Optional[str] = None,
    knowledge_conn=None,
) -> str:
    """
    Build a task.md checklist for `symbol`.

    oracle        - DBOracle (structural graph: graph_edges, functions, etc.).
    out_path      - if given, write the markdown to this file path as well.
    knowledge_conn - sqlite3 connection to knowledge.db; if None, known
                    findings section is omitted.

    Returns the markdown string.
    """
    direct = _direct_callers(oracle.conn, symbol)
    impact = _impact_zone(symbol, oracle)

    # Remove direct callers from the impact zone to avoid duplication
    direct_set = {(r["caller"], r["file_path"]) for r in direct}
    impact_only = [s for s in impact if s not in {r["caller"] for r in direct}]

    findings = _known_findings(knowledge_conn, symbol) if knowledge_conn is not None else []
    content = _render(symbol, direct, impact_only, findings)

    if out_path:
        _write_utf8(out_path, content)

    return content


# =========================================================
# TIER 1 - DIRECT CALLERS
# =========================================================

def _direct_callers(conn, symbol: str) -> list[dict]:
    """
    Exact rows from graph_edges where callee matches the symbol.
    Returns list of {caller, file_path, line_number}.
    """
    cur = conn.execute(
        """
        SELECT ge.caller, sr.file_path, ge.line_number
        FROM graph_edges ge
        LEFT JOIN symbol_references sr
            ON ge.caller = sr.caller AND ge.callee = sr.callee
        WHERE ge.callee = ? OR ge.callee LIKE ?
        ORDER BY sr.file_path, ge.line_number
        """,
        (symbol, f"%.{symbol}"),
    )
    rows = cur.fetchall()
    return [{"caller": r[0], "file_path": r[1] or "?", "line_number": r[2]} for r in rows]


# =========================================================
# TIER 2 - IMPACT ZONE
# =========================================================

def _impact_zone(symbol, oracle) -> list[str]:
    """
    Reverse-closure neighborhood from exactly this symbol via route_query()
    with seeds override (bypasses token-match discovery).
    """
    from determined.assessor.query_router import route_query

    result = route_query(
        text=f"what depends on {symbol}",
        oracle=oracle,
        seeds=[symbol],
    )
    # expanded_symbols includes the seed itself; exclude it
    return [s for s in result.expanded_symbols if s != symbol]


# =========================================================
# KNOWN FINDINGS (knowledge_artifacts)
# =========================================================

def _known_findings(conn, symbol: str) -> list[dict]:
    """
    Artifacts stored for this symbol in knowledge.db, provenance-ranked.
    Returns list of {kind, content, provenance, needs_review}.
    """
    _RANK = {"human-confirmed": 3, "ai-confirmed-by-human": 2, "ai-generated": 1}
    try:
        # Match exact symbol name OR file::symbol convention (e.g. "path.py::symbol")
        rows = conn.execute(
            "SELECT kind, content, provenance, needs_review FROM knowledge_artifacts "
            "WHERE subject = ? OR subject LIKE ? ORDER BY created_at DESC",
            (symbol, f"%::{symbol}"),
        ).fetchall()
    except Exception:
        return []
    results = [
        {"kind": r[0], "content": r[1], "provenance": r[2], "needs_review": bool(r[3])}
        for r in rows
    ]
    results.sort(key=lambda r: _RANK.get(r["provenance"], 0), reverse=True)
    return results


# =========================================================
# RENDER
# =========================================================

def _render(symbol: str, direct: list[dict], impact_only: list[str],
            findings: list[dict] | None = None) -> str:
    today = date.today().isoformat()
    lines = [
        f"# task: review impact of changes to `{symbol}`",
        f"Generated {today} by tools/analysis task_generator.",
        "",
        "---",
        "",
        "## Direct callers (confirmed)",
        "",
        "_These call `{symbol}` directly. Any signature or behavior change here"
        " requires updating each caller._".format(symbol=symbol),
        "",
    ]

    if direct:
        for r in direct:
            loc = f"{r['file_path']}:{r['line_number']}" if r["line_number"] else r["file_path"]
            lines.append(f"- [ ] `{r['caller']}` at `{loc}`")
    else:
        lines.append("- (no direct callers found in graph)")

    lines += [
        "",
        "## Impact zone (may need review)",
        "",
        "_These symbols are in the reverse-closure neighborhood of `{symbol}`. Not all".format(symbol=symbol),
        "will be affected by every change, but they depend on something in the call chain._",
        "",
    ]

    if impact_only:
        for sym in sorted(impact_only):
            lines.append(f"- [ ] `{sym}`")
    else:
        lines.append("- (no additional impact zone symbols found)")

    if findings:
        lines += [
            "",
            "## Known findings",
            "",
            "_Stored knowledge artifacts for this symbol (provenance-ranked)._",
            "",
        ]
        for f in findings:
            stale = " **[STALE - needs review]**" if f.get("needs_review") else ""
            lines.append(f"- **[{f['kind']} / {f['provenance']}]**{stale} {f['content']}")

    lines += [
        "",
        "---",
        "",
        "## Notes",
        "",
        "- Direct callers list is exact (from `graph_edges WHERE callee = ?`).",
        "- Impact zone is a neighborhood superset - cross-check before treating",
        "  every entry as a required change.",
        "- Re-run this generator after changes land to verify the zone shrinks.",
    ]

    return "\n".join(lines) + "\n"


def _write_utf8(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
