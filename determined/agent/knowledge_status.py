# tools/analysis/agent/knowledge_status.py
#
# Self-awareness layer: what the agent knows vs what exists in the corpus.
# Used for Phase 4 SUGGEST (post-answer follow-up directions) and the
# "what do you know?" / "what haven't you explored?" special queries.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor


# ------------------------------------------------------------------
# Coverage report
# ------------------------------------------------------------------

def coverage_report(oracle: "DBOracle", assessor: "Assessor", unknown_limit: int = 10) -> dict:
    """
    Compare corpus contents against knowledge.db findings.
    Returns:
      total_files, known_files, unknown_files,
      total_symbols, known_symbols, unknown_symbols,
      known_entry_points, known_chains
    """
    conn = getattr(assessor, "_knowledge_conn", None)

    # All files in corpus
    all_files = {
        r["file_path"].replace("\\", "/").split("/")[-1]
        for r in oracle.find_files()
    }

    # All symbols in corpus
    all_syms = {
        r[0] for r in oracle.conn.execute(
            "SELECT name FROM functions UNION SELECT name FROM classes"
        ).fetchall()
    }

    known_files: set[str] = set()
    known_syms: set[str] = set()
    known_chains: set[str] = set()

    if conn:
        for row in conn.execute(
            "SELECT subject, kind FROM knowledge_artifacts"
        ).fetchall():
            subj, kind = row[0], row[1]
            if kind == "file_purpose":
                known_files.add(subj)
            elif kind in ("design_note", "strategy_decision", "query_finding",
                          "known_issue", "query_finding"):
                known_syms.add(subj)
            if kind == "strategy_decision" and subj.startswith("chain::"):
                known_chains.add(subj[7:])  # strip "chain::" prefix

    unknown = sorted(all_files - known_files)
    return {
        "total_files": len(all_files),
        "known_files": len(known_files & all_files),
        "unknown_files": unknown[:unknown_limit],
        "unknown_total": len(unknown),
        "total_symbols": len(all_syms),
        "known_symbols": len(known_syms & all_syms),
        "unknown_symbols": len(all_syms - known_syms),
        "known_chains": sorted(known_chains),
    }


def coverage_summary(oracle: "DBOracle", assessor: "Assessor") -> str:
    """One-paragraph text summary of current knowledge coverage."""
    r = coverage_report(oracle, assessor)
    pct_files = int(100 * r["known_files"] / r["total_files"]) if r["total_files"] else 0
    pct_syms = int(100 * r["known_symbols"] / r["total_symbols"]) if r["total_symbols"] else 0
    lines = [
        f"Knowledge coverage: {r['known_files']}/{r['total_files']} files ({pct_files}%), "
        f"{r['known_symbols']}/{r['total_symbols']} symbols ({pct_syms}%)."
    ]
    if r["known_chains"]:
        lines.append(f"Call chains traced: {', '.join(r['known_chains'])}.")
    if r["unknown_files"]:
        sample = ", ".join(r["unknown_files"][:5])
        more = f" (+{len(r['unknown_files'])-5} more)" if len(r["unknown_files"]) > 5 else ""
        lines.append(f"Not yet explored: {sample}{more}.")
    return " ".join(lines)


# ------------------------------------------------------------------
# Phase 4: SUGGEST
# Derive 2-3 follow-up directions from facts just retrieved.
# Pure Python - no AI call.
# ------------------------------------------------------------------

def suggest_followups(
    facts: list[dict],
    oracle: "DBOracle",
    assessor: "Assessor",
) -> str:
    """
    Given the fact set from a Q&A turn, produce 2-3 concrete follow-up
    suggestions. Looks for: symbols with no findings, files not yet
    described, orphaned entry points, connected symbols not yet explored.
    Returns a short text block or empty string if nothing interesting found.
    """
    from determined.agent.agent_resolver import _symbols_from_result, _files_from_result
    conn = getattr(assessor, "_knowledge_conn", None)

    mentioned_syms: set[str] = set()
    mentioned_files: set[str] = set()

    for f in facts:
        if f["tool"] == "unmatched" or not f["result"]:
            continue
        for s in _symbols_from_result(f["result"]):
            mentioned_syms.add(s)
        for fp in _files_from_result(f["result"]):
            mentioned_files.add(fp)

    suggestions = []

    # Symbols mentioned but with no knowledge.db findings
    unfound_syms = []
    for sym in list(mentioned_syms)[:10]:
        if conn:
            row = conn.execute(
                "SELECT 1 FROM knowledge_artifacts WHERE subject = ? OR subject LIKE ? LIMIT 1",
                (sym, f"%::{sym}"),
            ).fetchone()
            if not row:
                unfound_syms.add(sym) if hasattr(unfound_syms, 'add') else unfound_syms.append(sym)
        else:
            unfound_syms.append(sym)

    if unfound_syms:
        suggestions.append(
            f"Unexplored symbols from this answer: {', '.join(unfound_syms[:3])}. "
            f"Try: 'brief for {unfound_syms[0]}' or 'what calls {unfound_syms[0]}'"
        )

    # Files mentioned but not yet described
    undescribed = []
    for fp in list(mentioned_files)[:5]:
        fname = fp.replace("\\", "/").split("/")[-1]
        if conn:
            row = conn.execute(
                "SELECT 1 FROM knowledge_artifacts WHERE subject = ? AND kind = 'file_purpose' LIMIT 1",
                (fname,),
            ).fetchone()
            if not row:
                undescribed.append(fname)
        else:
            undescribed.append(fname)

    if undescribed:
        suggestions.append(
            f"Files not yet described: {', '.join(undescribed[:2])}. "
            f"Try: 'what does {undescribed[0]} do'"
        )

    # Coverage gap nudge
    if conn:
        total = oracle.conn.execute("SELECT COUNT(*) FROM files").fetchone()
        known = conn.execute(
            "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='file_purpose'"
        ).fetchone()
        total_n = total[0] if total else 0
        known_n = known[0] if known else 0
        if total_n > 0 and known_n < total_n:
            suggestions.append(
                f"Discovery coverage: {known_n}/{total_n} files surveyed. "
                f"Run discovery agent to build broader context."
            )

    if not suggestions:
        return ""

    lines = ["I can also explore:"]
    for i, s in enumerate(suggestions[:3], 1):
        lines.append(f"  {i}. {s}")
    return "\n".join(lines)
