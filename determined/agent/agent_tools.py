# tools/analysis/agent/agent_tools.py
#
# Tool functions for the local conversational agent (DESIGN.md section 8).
# Each tool is a plain function: takes (oracle, assessor, args_dict) and
# returns a plain string or list. All are independently testable against
# a real corpus DB before being wired into the agent loop.
#
# Tools are intentionally thin wrappers over existing layers - no logic
# lives here that belongs in the layers themselves.

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

_embed_model = None

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model

from determined.agent.edge_tools import (
    edges_of,
    edge_detail,
    list_import_deps,
    add_edge,
)
from determined.agent.bag_tools import (
    bag_status,
    bag_list,
    bag_add,
    bag_label,
    bag_clear,
    bag_report,
)

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.assessor import Assessor


# ------------------------------------------------------------------
# DISCOVERY TOOLS
# ------------------------------------------------------------------

def search_symbols(oracle: "DBOracle", args: dict) -> str:
    """
    search_symbols(query) - find symbols by name substring.
    Returns up to 20 matches: name, file, line, type.
    """
    query = args.get("query", "").strip()
    if not query:
        return "ERROR: query argument required"
    results = _search_symbols_raw(oracle, query, limit=20)
    if not results:
        return f"No symbols found matching '{query}'"
    lines = [f"Symbols matching '{query}':"]
    for r in results:
        file_short = r["file_path"].replace("\\", "/").split("/")[-1]
        lines.append(f"  {r['name']} ({r['symbol_type']}) in {file_short} line {r['line_number']}")
    return "\n".join(lines)


def search_files(oracle: "DBOracle", args: dict) -> str:
    """
    search_files(query) - find files by path substring.
    Returns matching file paths with line counts.
    """
    query = args.get("query", "").strip()
    if not query:
        return "ERROR: query argument required"
    results = oracle.find_files(pattern=query)
    if not results:
        return f"No files found matching '{query}'"
    lines = [f"Files matching '{query}':"]
    for r in results:
        path = r["file_path"].replace("\\", "/")
        # trim to project-relative
        for prefix in [oracle.get_project_root().replace("\\", "/") + "/"]:
            if path.startswith(prefix):
                path = path[len(prefix):]
        lines.append(f"  {path} ({r['line_count']} lines)")
    return "\n".join(lines)


def list_callers(oracle: "DBOracle", args: dict) -> str:
    """
    list_callers(symbol) - direct callers from graph_edges.
    Matches bare name and module.name qualified forms.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    rows = _list_callers_raw(oracle, symbol)
    if not rows:
        return f"No direct callers found for '{symbol}'"
    lines = [f"Direct callers of '{symbol}':"]
    for r in rows:
        file_short = (r["file_path"] or "?").replace("\\", "/").split("/")[-1]
        tag = " (annotation-resolved)" if r.get("resolved") else ""
        lines.append(f"  {r['caller']} in {file_short} line {r['line_number']}{tag}")
    return "\n".join(lines)


def list_callees(oracle: "DBOracle", args: dict) -> str:
    """
    list_callees(symbol) - what this symbol calls, from graph_edges.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    rows = _list_callees_raw(oracle, symbol)
    if not rows:
        return f"No project callees for '{symbol}' (only builtins, or makes no calls)"
    lines = [f"'{symbol}' calls:"]
    for r in rows:
        file_short = (r["file_path"] or "?").replace("\\", "/").split("/")[-1]
        suffix = f" (x{r['count']})" if r["count"] > 1 else ""
        tag = " (annotation-resolved)" if r.get("resolved") else ""
        lines.append(f"  {r['callee']} in {file_short} line {r['line_number']}{suffix}{tag}")
    return "\n".join(lines)


def symbols_in_file(oracle: "DBOracle", args: dict) -> str:
    """
    symbols_in_file(file_path) - all functions and classes in a file.
    file_path may be relative (e.g. 'world/encounter_generator.py').
    """
    file_path = args.get("file_path", "").strip()
    if not file_path:
        return "ERROR: file_path argument required"
    # match on suffix so relative paths work
    normalized = file_path.replace("\\", "/")
    rows = oracle.conn.execute(
        """
        SELECT name, symbol_type, line_number, docstring
        FROM (
            SELECT name, 'function' as symbol_type, line_number, docstring
            FROM functions WHERE file_path LIKE ?
            UNION ALL
            SELECT name, 'class' as symbol_type, line_number, docstring
            FROM classes WHERE file_path LIKE ?
        )
        ORDER BY line_number
        """,
        (f"%{normalized}", f"%{normalized}"),
    ).fetchall()
    if not rows:
        return f"No symbols found in '{file_path}' (file may not be in corpus)"
    lines = [f"Symbols in '{file_path}':"]
    for r in rows:
        has_doc = " [has docstring]" if r[3] else ""
        lines.append(f"  line {r[2]}: {r[1]} {r[0]}{has_doc}")
    return "\n".join(lines)


def files_in_directory(oracle: "DBOracle", args: dict) -> str:
    """
    files_in_directory(path) - list files in a directory from the corpus.
    path is a relative directory name e.g. 'src' or 'lib'.
    """
    path = args.get("path", "").strip().rstrip("/").rstrip("\\")
    if not path:
        return "ERROR: path argument required"
    results = oracle.find_files(pattern=f"/{path}/")
    if not results:
        # try without leading slash for edge cases
        results = oracle.find_files(pattern=path)
    if not results:
        return f"No files found in directory '{path}'"
    root = oracle.get_project_root().replace("\\", "/")
    lines = [f"Files in '{path}/':"]
    for r in results:
        fp = r["file_path"].replace("\\", "/")
        if root and fp.startswith(root + "/"):
            fp = fp[len(root) + 1:]
        lines.append(f"  {fp} ({r['line_count']} lines)")
    return "\n".join(lines)


# ------------------------------------------------------------------
# UNDERSTANDING TOOLS
# ------------------------------------------------------------------

def describe_file(assessor: "Assessor", args: dict) -> str:
    """
    describe_file(file_path) - AI semantic summary of a file.
    file_path may be bare filename or relative path. Resolves against
    corpus DB to get the canonical project-relative path before reading.
    """
    file_path = args.get("file_path", "").strip()
    if not file_path:
        return "ERROR: file_path argument required"

    # Resolve bare filename to project-relative path via corpus DB
    resolved = _resolve_file_path(assessor.oracle, file_path)
    if resolved:
        file_path = resolved

    result = assessor.semantic_summary(file_path, kind="file")
    content = result.get("content", "")
    cache_note = " [cached]" if result.get("cache_hit") else ""

    # Annotation-resolved edge stat
    oracle = assessor.oracle
    try:
        fp_pattern = "%" + file_path.replace("/", "%").replace("\\", "%")
        total = oracle.conn.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE caller_file LIKE ?",
            (fp_pattern,),
        ).fetchone()[0]
        resolved = oracle.conn.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE caller_file LIKE ? AND resolved = 1",
            (fp_pattern,),
        ).fetchone()[0]
        if total > 0:
            pct = int(100 * resolved / total)
            edge_stat = f"\nCall edges: {total} total, {resolved} annotation-resolved ({pct}%)"
        else:
            edge_stat = ""
    except Exception:
        edge_stat = ""

    return f"Summary of '{file_path}'{cache_note}:{edge_stat}\n{content}"


def _resolve_file_path(oracle: "DBOracle", file_path: str) -> str | None:
    """
    Given a bare filename or partial path, return the project-relative path
    (e.g. 'world/adjudication_engine.py') by looking it up in the corpus.
    Returns None if not found or if input already looks like a path.
    """
    import os
    # Already a path with directory component - use as-is
    if "/" in file_path or "\\" in file_path:
        return None
    matches = oracle.find_files(pattern=file_path)
    if not matches:
        return None
    root = (oracle.get_project_root() or "").replace("\\", "/").rstrip("/")

    # Prefer exact basename match over substring match
    # e.g. "utils.py" should not resolve to "ai_utils.py"
    basename = file_path.split("/")[-1].split("\\")[-1]
    exact = [m for m in matches
             if m["file_path"].replace("\\", "/").split("/")[-1] == basename]
    best = exact[0] if exact else matches[0]

    fp = best["file_path"].replace("\\", "/")
    if root and fp.startswith(root + "/"):
        fp = fp[len(root) + 1:]
    return fp


# ------------------------------------------------------------------
# RAW HELPERS - return structured data; string tools derive from these (XIV)
# ------------------------------------------------------------------

def _search_symbols_raw(oracle: "DBOracle", query: str, limit: int = 20) -> list[dict]:
    """
    Symbol lookup by name substring (query='') returns all symbols.
    Enriches oracle.find_symbols results with docstrings from functions/classes.
    Returns list[dict]: name, file_path, symbol_type, line_number, docstring.
    """
    results = oracle.find_symbols(query, limit=limit)
    if not results:
        return []
    names = [r["name"] for r in results]
    placeholders = ",".join("?" * len(names))
    doc_map: dict[str, str | None] = {}
    for table in ("functions", "classes"):
        rows = oracle.conn.execute(
            f"SELECT name, docstring FROM {table} WHERE name IN ({placeholders})",
            names,
        ).fetchall()
        for name, doc in rows:
            if name not in doc_map:
                doc_map[name] = doc
    for r in results:
        r["docstring"] = doc_map.get(r["name"])
    return results


def _list_callers_raw(oracle: "DBOracle", symbol: str) -> list[dict]:
    """
    Direct callers of symbol from graph_edges.
    Returns list[dict]: caller, file_path, line_number, resolved.
    """
    rows = oracle.conn.execute(
        """
        SELECT ge.caller, sr.file_path, ge.line_number, COALESCE(ge.resolved, 0)
        FROM graph_edges ge
        LEFT JOIN symbol_references sr
            ON ge.caller = sr.caller AND ge.callee = sr.callee
        WHERE ge.callee = ? OR ge.callee LIKE ?
        ORDER BY sr.file_path, ge.line_number
        """,
        (symbol, f"%.{symbol}"),
    ).fetchall()
    return [{"caller": r[0], "file_path": r[1], "line_number": r[2], "resolved": bool(r[3])} for r in rows]


def _list_callees_raw(oracle: "DBOracle", symbol: str) -> list[dict]:
    """
    Project callees of symbol from graph_edges (builtins filtered out).
    Returns list[dict]: callee, file_path, line_number, count, resolved.
    """
    import builtins as _bi
    rows = oracle.conn.execute(
        """
        SELECT ge.callee, sr.file_path, ge.line_number, COALESCE(ge.resolved, 0)
        FROM graph_edges ge
        LEFT JOIN symbol_references sr
            ON ge.caller = sr.caller AND ge.callee = sr.callee
        WHERE ge.caller = ?
        ORDER BY ge.line_number
        """,
        (symbol,),
    ).fetchall()
    seen: dict[str, tuple] = {}
    counts: dict[str, int] = {}
    resolved_map: dict[str, bool] = {}
    for callee, fp, ln, res in rows:
        bare = (callee or "").rsplit(".", 1)[-1]
        if not bare or bare in dir(_bi):
            continue
        counts[callee] = counts.get(callee, 0) + 1
        if callee not in seen:
            seen[callee] = (fp, ln)
            resolved_map[callee] = bool(res)
    return [
        {"callee": callee, "file_path": fp, "line_number": ln, "count": counts[callee], "resolved": resolved_map[callee]}
        for callee, (fp, ln) in list(seen.items())[:30]
    ]


def _graph_most_connected_raw(
    oracle: "DBOracle", filter_str: str = "", n: int = 15
) -> list[dict]:
    """
    Top n symbols by call degree, optionally filtered by name substring.
    Returns list[dict]: symbol, file_path, in_degree, out_degree.
    """
    from determined.agent.graph_utils import most_connected
    return most_connected(oracle, n=n, filter_substr=filter_str)


def _graph_subgraph_raw(oracle: "DBOracle", symbol: str, radius: int = 2) -> dict:
    """
    Nodes and edges within radius hops of symbol.
    Returns dict: nodes (set[str]), edges (list[tuple[str, str]]).
    """
    from determined.agent.graph_utils import subgraph_around
    return subgraph_around(oracle, symbol, radius=radius)


def _distill_to_one_sentence(content: str, subject: str, conn=None) -> str | None:
    """
    Compress `content` into one sentence via llama-server.
    Returns None if llama-server is unreachable - callers must handle this explicitly
    so the failure is visible rather than silently swallowed (SOTS XIII).
    Checks semantic cache first if conn is provided.
    """
    from determined.agent.llm_client import generate as _llm_generate, LLM_TIMEOUT
    prompt = (
        f"Summarise the following in exactly one sentence (max 25 words). "
        f"Be concrete and name the main thing it does.\n\n"
        f"Subject: {subject}\n\n{content[:1500]}"
    )
    if conn is not None:
        from determined.agent.semantic_cache import lookup, store
        cached = lookup(prompt, conn)
        if cached is not None:
            return cached
    result = _llm_generate(prompt, timeout=LLM_TIMEOUT)
    if result is not None and conn is not None:
        from determined.agent.semantic_cache import store
        store(prompt, result, conn)
    return result


def _get_design_frame(assessor: "Assessor", symbol: str, file_path: str) -> str:
    """
    Semantic lookup: embed the symbol context, cosine-search against bundled
    SOTS tenets. Falls back gracefully if embedding model unavailable.
    No knowledge.db required.
    """
    from determined.data.sots_loader import search_tenets

    stem = ""
    if file_path:
        stem = file_path.replace("\\", "/").split("/")[-1].replace(".py", "")

    docstring = ""
    if assessor.oracle:
        row = assessor.oracle.conn.execute(
            "SELECT docstring FROM functions WHERE name = ? LIMIT 1", (symbol,)
        ).fetchone()
        if not row:
            row = assessor.oracle.conn.execute(
                "SELECT docstring FROM classes WHERE name = ? LIMIT 1", (symbol,)
            ).fetchone()
        if row and row[0]:
            docstring = row[0][:300]

    parts = [f"symbol: {symbol}"]
    if stem:
        parts.append(f"file: {stem}")
    if docstring:
        parts.append(docstring)
    query = "  ".join(parts)

    hits = search_tenets(query, threshold=0.32, top_n=3)
    if not hits:
        return ""
    lines = [f"  [{t['id']}] {t['title']}: {t['description']}" for t in hits]
    return "\nDesign frame (SOTS):\n" + "\n".join(lines)


def symbol_intent(oracle: "DBOracle", args: dict) -> str:
    """
    symbol_intent(symbol[, file_path]) - docstring for a function or class (Layer 2).
    If file_path is given, prefer the symbol from that file (disambiguation).
    Returns None-equivalent message if no docstring exists.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    file_hint = args.get("file_path", "").strip()

    def _query(table: str, extra_where: str = "", params: tuple = ()) -> object:
        sql = (f"SELECT name, file_path, line_number, docstring FROM {table} "
               f"WHERE name = ? {extra_where} LIMIT 1")
        return oracle.conn.execute(sql, (symbol,) + params).fetchone()

    row = None
    if file_hint:
        # Try exact file first, then fall back to any file
        row = (_query("functions", "AND file_path LIKE ?", (f"%{file_hint}",)) or
               _query("classes",   "AND file_path LIKE ?", (f"%{file_hint}",)))
    if not row:
        row = _query("functions") or _query("classes")
    if not row:
        return f"'{symbol}' not found in corpus"
    file_short = row[1].replace("\\", "/").split("/")[-1]
    if not row[3]:
        return f"'{symbol}' in {file_short} line {row[2]}: no docstring"
    return f"'{symbol}' in {file_short} line {row[2]}:\n{row[3]}"


def symbol_brief(assessor: "Assessor", args: dict) -> str:
    """
    symbol_brief(symbol) - full two-tier brief: direct callers + impact zone.
    Calls generate_task_md. Richest single-symbol output available.
    Prepends a risk annotation line (HOT/WARM/SAFE) and distilled one-liner.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    from determined.agent.risk_annotator import score_risk, risk_badge
    r = score_risk(assessor.oracle, symbol)
    badge = risk_badge(r["level"])
    brief = assessor.generate_task_md(symbol)
    risk_line = f"Risk: {badge}  ({'; '.join(r['reasons'])})"
    row = assessor.oracle.conn.execute(
        "SELECT file_path FROM symbols WHERE name = ?", (symbol,)
    ).fetchone()
    file_path = row[0] if row else ""
    design_frame = _get_design_frame(assessor, symbol, file_path)

    # Prepend distilled preamble if available (stored in corpus DB by distill_corpus)
    distilled_line = ""
    if file_path:
        stem = file_path.replace(chr(92), "/").split("/")[-1].replace(".py", "")
        dist_row = assessor.oracle.conn.execute(
            "SELECT distilled FROM semantic_summaries "
            "WHERE subject LIKE ? AND distilled IS NOT NULL LIMIT 1",
            (f"%{stem}.py",),
        ).fetchone()
        if dist_row:
            distilled_line = f"Summary: {dist_row[0]}\n"

    return distilled_line + risk_line + "\n" + brief + design_frame


_CONSTRAINT_PATTERNS = (
    "must not", "never", "only", "forbidden", "must be", "shall not",
    "do not", "cannot", "prohibited", "required", "always",
)


def _check_design_violations_core(
    assessor: "Assessor", symbol: str, file_path: str
) -> list[dict]:
    """
    Pure analysis: embed symbol context, cosine-search bundled SOTS tenets
    filtered for constraint language. Returns list[dict]: subject, content, score.
    Returns empty list on embedding failure (XIII). SOTS XI: pure, no mutations.
    No knowledge.db required.
    """
    from determined.data.sots_loader import load_tenets, search_tenets

    # Build a rich query: symbol name + docstring + callee names
    docstring = ""
    row = assessor.oracle.conn.execute(
        "SELECT docstring FROM functions WHERE name = ? LIMIT 1", (symbol,)
    ).fetchone()
    if not row:
        row = assessor.oracle.conn.execute(
            "SELECT docstring FROM classes WHERE name = ? LIMIT 1", (symbol,)
        ).fetchone()
    if row and row[0]:
        docstring = row[0][:300]

    callee_names = " ".join(r["callee"].rsplit(".", 1)[-1] for r in _list_callees_raw(assessor.oracle, symbol)[:10])
    stem = file_path.replace("\\", "/").split("/")[-1].replace(".py", "") if file_path else ""
    query = f"symbol: {symbol}  file: {stem}  {docstring}  calls: {callee_names}"

    # SOTS tenets already contain constraint language - search directly
    hits = search_tenets(query, threshold=0.30, top_n=5)
    return [
        {"subject": f"SOTS {t['id']}", "content": f"{t['title']}: {t['description']}", "score": t["score"]}
        for t in hits
    ]


def check_design_violations(assessor: "Assessor", args: dict) -> str:
    """
    check_design_violations(symbol) - cross-reference symbol against design constraints.
    Embeds symbol + docstring + callee names, cosine-searches all design_notes,
    filters for constraint language. Returns potential violations for human review.
    Pure analysis only (SOTS XI): never mutates state, never acts on findings.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"

    row = assessor.oracle.conn.execute(
        "SELECT file_path FROM symbols WHERE name = ?", (symbol,)
    ).fetchone()
    file_path = row[0] if row else ""

    hits = _check_design_violations_core(assessor, symbol, file_path)

    if not hits:
        from determined.data.sots_loader import load_tenets
        return (
            f"No design violations detected for '{symbol}' "
            f"(checked {len(load_tenets())} SOTS tenets, none matched above threshold)."
        )

    lines = [f"Potential design violations for '{symbol}':"]
    for h in hits:
        label = h["subject"] or "general"
        lines.append(f"  [{label}] (score={h['score']:.2f})")
        lines.append(f"    {h['content'][:200]}")
    lines.append("")
    lines.append("Review these constraints manually - this is a similarity match, not a confirmed violation.")
    return "\n".join(lines)


def risk_profile(assessor: "Assessor", args: dict):
    """
    risk_profile(symbol) - structural change-risk rating for a symbol.
    Returns HOT/WARM/SAFE with the reasons: in-degree, mutations, blast radius.
    Appends design_note artifacts and design violation matches.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    oracle = assessor.oracle
    from determined.agent.risk_annotator import score_risk, risk_badge
    r = score_risk(oracle, symbol)
    badge = risk_badge(r["level"])
    lines = [f"Risk profile for '{symbol}': {badge}"]
    for reason in r["reasons"]:
        lines.append(f"  - {reason}")
    lines.append(f"  in_degree={r['in_degree']}  out_degree={r['out_degree']}  mutations={r['mutation_count']}")
    row = oracle.conn.execute("SELECT file_path FROM symbols WHERE name = ?", (symbol,)).fetchone()
    file_path = row[0] if row else ""
    design_frame = _get_design_frame(assessor, symbol, file_path)
    if design_frame:
        lines.append(design_frame)
    # Append design violations (item 19)
    violations = _check_design_violations_core(assessor, symbol, file_path)
    if violations:
        lines.append("\nDesign constraint matches:")
        for v in violations:
            label = v["subject"] or "general"
            lines.append(f"  [{label}] {v['content'][:150]}")
    bag_item = {"__type__": "symbol", "__key__": f"symbol::{symbol}",
                "name": symbol, "file_path": file_path, "risk": r["level"]}
    return "\n".join(lines), [bag_item]


# ------------------------------------------------------------------
# KNOWLEDGE TOOLS
# ------------------------------------------------------------------

def get_findings(assessor: "Assessor", args: dict) -> str:
    """
    get_findings(symbol) - stored knowledge artifacts for a symbol.
    Matches bare symbol name, file::symbol form, and LIKE %::symbol.
    Provenance-ranked: human-confirmed first. Flags stale findings.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    # Try exact match first, then suffix match for file::symbol subjects
    artifacts = assessor.get_artifacts(symbol)
    if not artifacts and assessor._knowledge_conn:
        rows = assessor._knowledge_conn.execute(
            "SELECT id, subject, kind, content, provenance, created_at, file_hash, needs_review "
            "FROM knowledge_artifacts WHERE subject LIKE ? ORDER BY created_at DESC",
            (f"%::{symbol}",),
        ).fetchall()
        from determined.intent.knowledge_artifact import _row_to_dict, _PROVENANCE_RANK
        artifacts = [_row_to_dict(r) for r in rows]
        artifacts.sort(key=lambda r: _PROVENANCE_RANK.get(r["provenance"], 0), reverse=True)
    # Also search semantic_summaries (file-level LLM summaries stored separately)
    semantic_hits = []
    if assessor._knowledge_conn:
        sem_rows = assessor._knowledge_conn.execute(
            "SELECT subject, content FROM semantic_summaries "
            "WHERE subject LIKE ? ORDER BY generated_at DESC LIMIT 3",
            (f"%{symbol}%",),
        ).fetchall()
        for row in sem_rows:
            semantic_hits.append({"subject": row[0], "content": row[1]})

    if not artifacts and not semantic_hits:
        return f"No stored findings for '{symbol}'"
    lines = [f"Findings for '{symbol}':"]
    for a in artifacts:
        stale = " [STALE - needs review]" if a.get("needs_review") else ""
        lines.append(f"  [{a['kind']} / {a['provenance']}]{stale}")
        lines.append(f"    {a['content'][:300]}")
    for s in semantic_hits:
        lines.append(f"  [semantic_summary / ai-generated]")
        lines.append(f"    {s['content'][:300]}")
    return "\n".join(lines)


def list_findings_by_kind(assessor: "Assessor", args: dict) -> str:
    """
    list_findings_by_kind(kind) - all stored artifacts of a given kind.
    Structural kinds (written by extract_design_facts):
      hot / dead / entry / stub
    Knowledge kinds (written by store_finding or ask_truth_layer):
      file_purpose / design_note / known_issue / strategy_decision /
      query_finding / session_decision
    """
    kind = args.get("kind", "").strip()
    if not kind:
        return "ERROR: kind argument required"
    artifacts = assessor.list_artifacts(kind=kind)
    if not artifacts:
        return f"No stored findings of kind '{kind}'"
    lines = [f"All '{kind}' findings:"]
    for a in artifacts:
        stale = " [STALE]" if a.get("needs_review") else ""
        lines.append(f"  [{a['subject']} / {a['provenance']}]{stale}")
        lines.append(f"    {a['content']}")
    return "\n".join(lines)


def store_finding(assessor: "Assessor", args: dict) -> str:
    """
    store_finding(symbol, kind, content) - write a derived finding to knowledge.db.
    Provenance is always ai-generated. Valid kinds:
    file_purpose / strategy_decision / query_finding / design_note / known_issue
    Use when a non-obvious finding took multiple tool calls to derive.
    """
    symbol = args.get("symbol", "").strip()
    kind = args.get("kind", "").strip()
    content = args.get("content", "").strip()
    if not symbol or not kind or not content:
        return "ERROR: symbol, kind, and content are all required"
    try:
        assessor.add_artifact(symbol, kind, content, "ai-generated")
        return f"Stored {kind} finding for '{symbol}'"
    except ValueError as e:
        return f"ERROR: {e}"


# ------------------------------------------------------------------
# GRAPH TOOLS
# ------------------------------------------------------------------

def graph_path(oracle: "DBOracle", args: dict) -> str:
    """
    graph_path(src, dst) - shortest call path from src to dst.
    """
    src = args.get("src", "").strip()
    dst = args.get("dst", "").strip()
    if not src or not dst:
        return "ERROR: src and dst arguments required"
    from determined.agent.graph_utils import shortest_path
    path = shortest_path(oracle, src, dst)
    if path is None:
        return f"No call path found from '{src}' to '{dst}'"
    return f"Call path from '{src}' to '{dst}':\n  " + " -> ".join(path)


def graph_entry_points(oracle: "DBOracle", args: dict) -> str:
    """
    graph_entry_points() - symbols with no callers (system roots).
    Ranked by out_degree descending: high fan-out = real execution root.
    """
    from determined.agent.graph_utils import find_entry_points
    eps = find_entry_points(oracle)
    if not eps:
        return "No entry points found"
    lines = [f"Entry points ({len(eps)} total, ranked by fan-out):"]
    for ep in eps[:20]:
        fp = ep["file_path"].replace("\\", "/").split("/")[-1]
        calls = ep.get("out_degree", 0)
        calls_note = f" — calls {calls} functions" if calls else " — leaf (calls nothing)"
        lines.append(f"  {ep['name']} ({ep['symbol_type']}) in {fp}{calls_note}")
    if len(eps) > 20:
        lines.append(f"  ... and {len(eps) - 20} more (lower fan-out, likely isolated helpers)")
    return "\n".join(lines)


def graph_most_connected(oracle: "DBOracle", args: dict):
    """
    graph_most_connected(filter) - top symbols by call degree with risk badges.
    filter is an optional substring to limit results.
    """
    filter_str = args.get("filter", "").strip()
    from determined.agent.risk_annotator import score_risk, risk_badge
    results = _graph_most_connected_raw(oracle, filter_str=filter_str, n=15)
    if not results:
        return f"No connected symbols found" + (f" matching '{filter_str}'" if filter_str else "")
    label = f" matching '{filter_str}'" if filter_str else ""
    lines = [f"Most connected symbols{label}:"]
    bag_items = []
    for r in results:
        fp = r["file_path"].replace("\\", "/").split("/")[-1] if r["file_path"] else "?"
        risk = score_risk(oracle, r["symbol"])
        badge = risk_badge(risk["level"])
        lines.append(f"  {badge} {r['symbol']} in {fp}  (in={r['in_degree']} out={r['out_degree']})")
        bag_items.append({"__type__": "symbol", "__key__": f"symbol::{r['symbol']}",
                          "name": r["symbol"], "file_path": r["file_path"] or "",
                          "risk": risk["level"], "in_degree": r["in_degree"]})
    return "\n".join(lines), bag_items


def graph_subgraph(oracle: "DBOracle", args: dict) -> str:
    """
    graph_subgraph(symbol, radius) - nodes and edges within radius hops.
    Returns a text summary; use graph_viz for visual output.
    """
    symbol = args.get("symbol", "").strip()
    radius = int(args.get("radius", 2))
    if not symbol:
        return "ERROR: symbol argument required"
    sg = _graph_subgraph_raw(oracle, symbol, radius=radius)
    lines = [f"Subgraph around '{symbol}' (radius={radius}):"]
    lines.append(f"  Nodes ({len(sg['nodes'])}): {', '.join(sorted(sg['nodes'])[:20])}")
    if len(sg['nodes']) > 20:
        lines[-1] += f" ... +{len(sg['nodes'])-20} more"
    lines.append(f"  Edges ({len(sg['edges'])}):")
    for src, dst in sg['edges'][:15]:
        lines.append(f"    {src} -> {dst}")
    if len(sg['edges']) > 15:
        lines.append(f"    ... +{len(sg['edges'])-15} more")
    return "\n".join(lines)


def graph_clusters(oracle: "DBOracle", args: dict) -> str:
    """
    graph_clusters() - file pairs with heavy mutual call density.
    """
    from determined.agent.graph_utils import find_clusters
    clusters = find_clusters(oracle, min_edges=2)
    if not clusters:
        return "No file clusters found (no file pairs share 2+ call edges)"
    # Separate test pairs from prod pairs so real subsystems aren't buried
    prod_clusters = [
        c for c in clusters
        if not any("test" in f.lower() for f in c["files"])
    ]
    test_clusters = [c for c in clusters if c not in prod_clusters]

    lines = [f"File clusters ({len(clusters)} pairs, {len(prod_clusters)} prod / {len(test_clusters)} test):"]
    lines.append("  [production subsystems]")
    for c in prod_clusters[:12]:
        f1 = c['files'][0].replace("\\", "/").split("/")[-1]
        f2 = c['files'][1].replace("\\", "/").split("/")[-1]
        lines.append(f"    {f1} <-> {f2}  ({c['edge_count']} edges)")
    if test_clusters:
        lines.append(f"  [test↔prod pairs: {len(test_clusters)} — omitted]")
    return "\n".join(lines)


# ------------------------------------------------------------------
# STUB TOOLS
# ------------------------------------------------------------------

def list_stubs(oracle: "DBOracle", args: dict) -> str:
    """
    list_stubs(limit?) - stub functions ranked by caller count (highest priority first).
    """
    limit = int(args.get("limit", 20))
    rows = oracle.conn.execute(
        """
        SELECT f.name, f.file_path, COUNT(ge.caller) AS callers
        FROM functions f
        LEFT JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        WHERE f.is_stub = 1
        GROUP BY f.name, f.file_path
        ORDER BY callers DESC, f.file_path, f.name
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    if not rows:
        return "No stub functions found in corpus."
    lines = [f"Stub functions ({len(rows)} shown, ranked by caller count):"]
    for r in rows:
        fp = (r[1] or "").replace("\\", "/").split("/")[-1]
        callers = r[2] or 0
        lines.append(f"  {r[0]} in {fp}  ({callers} callers)")
    return "\n".join(lines)


def project_stub(oracle: "DBOracle", args: dict) -> str:
    """
    project_stub(symbol) - generate a concrete implementation for a stub function
    using its call-graph context, behavioral contracts, and sibling code.
    Requires Ollama running. May take 20-40 seconds.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    from determined.agent.stub_projector import project_stub as _proj
    result = _proj(oracle.db_path, symbol)
    if "error" in result:
        return f"Cannot project '{symbol}': {result['error']}"
    ctx = result.get("context_summary", {})
    lines = [
        f"Stub projection for '{symbol}' ({result.get('file_path', '?')} line {result.get('line_number', '?')})",
        f"Context: {ctx.get('callers', 0)} callers · {ctx.get('contracts', 0)} contracts · {ctx.get('sibling_callees', 0)} sibling callees",
        "",
        "Suggested implementation:",
        result.get("suggested_body", "(no suggestion)"),
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------
# QUALITY SWEEP TOOLS
# ------------------------------------------------------------------

def missing_docstrings(oracle: "DBOracle", args: dict) -> str:
    """
    missing_docstrings(limit?) - functions and classes with no docstring.
    Returns up to limit items (default 20), sorted by file then line.
    """
    limit = int(args.get("limit", 20))
    rows = oracle.conn.execute(
        "SELECT 'function' as kind, name, file_path, line_number FROM functions "
        "WHERE docstring IS NULL OR docstring = '' "
        "UNION ALL "
        "SELECT 'class', name, file_path, line_number FROM classes "
        "WHERE docstring IS NULL OR docstring = '' "
        "ORDER BY file_path, line_number LIMIT ?",
        (limit,),
    ).fetchall()
    if not rows:
        return "All functions and classes have docstrings."
    root = oracle.get_project_root() or ""
    lines = [f"Functions/classes missing docstrings ({len(rows)} shown, limit {limit}):"]
    for kind, name, fpath, lineno in rows:
        rel = fpath.replace("\\", "/").replace(root.replace("\\", "/") + "/", "")
        lines.append(f"  {kind} {name} in {rel} line {lineno}")
    return "\n".join(lines)


def find_todos(oracle: "DBOracle", args: dict) -> str:
    """
    find_todos(limit?) - scan project files for TODO/FIXME/HACK/XXX comments.
    Returns file, line number, and the comment text. Files containing hot
    symbols (high in-degree) are shown first.
    """
    limit = int(args.get("limit", 30))
    root = oracle.get_project_root() or ""
    tags = ("TODO", "FIXME", "HACK", "XXX")

    # Get all known project files from corpus
    file_paths = [
        r[0] for r in oracle.conn.execute("SELECT file_path FROM files").fetchall()
    ]

    # Build a "hot file" set: files containing any symbol with in_degree >= 3
    hot_files: set[str] = set()
    for row in oracle.conn.execute(
        "SELECT callee FROM graph_edges GROUP BY callee HAVING COUNT(DISTINCT caller) >= 3"
    ).fetchall():
        sym = row[0].rsplit(".", 1)[-1]  # bare name
        fp_row = oracle.conn.execute(
            "SELECT file_path FROM functions WHERE name = ? LIMIT 1", (sym,)
        ).fetchone()
        if fp_row:
            hot_files.add(fp_row[0].replace("\\", "/").split("/")[-1])

    hits: list[tuple] = []  # (is_hot, rel_path, lineno, text)
    for fpath in file_paths:
        fname = fpath.replace("\\", "/").split("/")[-1]
        is_hot = fname in hot_files
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if any(tag in stripped for tag in tags):
                        rel = fpath.replace("\\", "/").replace(
                            root.replace("\\", "/") + "/", ""
                        )
                        hits.append((is_hot, rel, lineno, stripped[:120]))
        except OSError:
            continue

    if not hits:
        return "No TODO/FIXME/HACK/XXX found in project files."

    # Hot-file TODOs first, then the rest; cap total
    hits.sort(key=lambda h: (0 if h[0] else 1, h[1], h[2]))
    hits = hits[:limit]

    lines = [f"TODO/FIXME/HACK/XXX in project files ({len(hits)} shown):"]
    prev_hot_section = None
    for is_hot, rel, lineno, text in hits:
        section = "hot files" if is_hot else "other files"
        if section != prev_hot_section:
            lines.append(f"  [{section}]")
            prev_hot_section = section
        lines.append(f"    {rel}:{lineno}  {text}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# GIT HISTORY TOOLS
# ------------------------------------------------------------------

def git_log_for(oracle: "DBOracle", args: dict) -> str:
    """
    git_log_for(path) - recent git commits touching a file or directory.
    Returns last 10 commits: hash, date, author, message.
    path is relative to the repo root inferred from the corpus DB location.
    If only a bare filename is given, resolves it to a full path via the corpus.
    """
    import subprocess, os
    path = args.get("path", "").strip()
    if not path:
        return "ERROR: path argument required"
    # If bare filename (no directory separator), try to resolve via corpus
    if "/" not in path and "\\" not in path:
        try:
            rows = oracle.conn.execute(
                "SELECT file_path FROM files WHERE file_path LIKE ? LIMIT 1",
                (f"%{path}",),
            ).fetchall()
            if rows:
                path = rows[0][0].replace("\\", "/")
        except Exception:
            pass
    # Get repo root from oracle (prefers value persisted at ingestion time)
    try:
        repo_root = oracle.get_project_root()
    except Exception:
        repo_root = None
    if not repo_root:
        return "ERROR: could not locate git repo root"
    repo_root = repo_root.replace("\\", "/")
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--follow", "-10",
             "--format=%h %ad %an: %s", "--date=short", "--", path],
            cwd=repo_root,
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip()
        if not output:
            return f"No git history found for '{path}'"
        return f"Recent commits touching '{path}':\n" + output
    except Exception as e:
        return f"ERROR running git log: {e}"


# ------------------------------------------------------------------
# KNOWLEDGE COVERAGE TOOLS
# ------------------------------------------------------------------

def knowledge_status(assessor: "Assessor", args: dict) -> str:
    """
    knowledge_status() - what the tool knows vs what's in the corpus.
    Reports coverage of semantic summaries and knowledge artifacts against
    total file/symbol counts. Useful before starting a session to know
    what's already been analyzed.
    """
    import os
    corpus = os.path.basename(getattr(assessor.oracle, "db_path", "") or "")
    corpus_filter = "(corpus = ? OR corpus IS NULL)" if corpus else "1=1"
    corpus_params = [corpus] if corpus else []

    total_files = assessor.oracle.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_fns = assessor.oracle.conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]

    sem_count = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM semantic_summaries WHERE {corpus_filter}", corpus_params
    ).fetchone()[0]
    artifact_count = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM knowledge_artifacts WHERE {corpus_filter}", corpus_params
    ).fetchone()[0]

    by_kind = assessor._knowledge_conn.execute(
        f"SELECT kind, COUNT(*) FROM knowledge_artifacts WHERE {corpus_filter} "
        f"GROUP BY kind ORDER BY COUNT(*) DESC", corpus_params
    ).fetchall()

    stale_count = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM knowledge_artifacts WHERE needs_review=1 AND {corpus_filter}",
        corpus_params
    ).fetchone()[0]

    entry_pts = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'entry::%' AND {corpus_filter}",
        corpus_params
    ).fetchone()[0]
    dead_code = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'dead::%' AND {corpus_filter}",
        corpus_params
    ).fetchone()[0]
    hot_syms = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'hot::%' AND {corpus_filter}",
        corpus_params
    ).fetchone()[0]
    stub_files = assessor._knowledge_conn.execute(
        f"SELECT COUNT(*) FROM knowledge_artifacts WHERE subject LIKE 'stubs::%' AND {corpus_filter}",
        corpus_params
    ).fetchone()[0]

    lines = [
        f"Knowledge coverage for corpus ({total_files} files, {total_fns} functions):",
        f"  File summaries (semantic_summaries): {sem_count}/{total_files} files covered",
        f"  Total knowledge artifacts: {artifact_count}",
        f"    by kind: " + ", ".join(f"{k}={n}" for k, n in by_kind),
        f"  Structural facts extracted:",
        f"    entry points: {entry_pts}  dead code candidates: {dead_code}  "
        f"hot symbols: {hot_syms}  stub files: {stub_files}",
    ]
    if stale_count:
        lines.append(f"  STALE artifacts needing review: {stale_count}")
    if sem_count < total_files:
        lines.append(
            f"  TIP: run extract_design_facts() then describe_file() on uncovered files "
            f"to improve coverage."
        )
    return "\n".join(lines)


# ------------------------------------------------------------------
# WORKFLOW TOOLS
# ------------------------------------------------------------------

def workflow_status(assessor: "Assessor", args: dict) -> str:
    """
    workflow_status() - current next_up, backlog, and recent decisions.
    Optional: kind filter via args['kind'].
    """
    kind = args.get("kind", "").strip() or None
    from determined.intent.workflow_store import format_workflow_status, list_items
    conn = getattr(assessor, "_knowledge_conn", None)
    if conn is None:
        return "No knowledge DB available."
    if kind:
        items = list_items(conn, kind=kind, status="active")
        if not items:
            return f"No active {kind} items."
        lines = [f"Active {kind} items:"]
        for item in items:
            rank_str = f"[#{item['rank']}] " if item["rank"] else ""
            lines.append(f"  {rank_str}{item['id']}. {item['subject']}: {item['content']}")
        return "\n".join(lines)
    return format_workflow_status(conn)


_WIP_MARKERS = ("in progress", "in-progress", "wip", "underway", "started")


def prioritize_work(assessor: "Assessor", args: dict) -> str:
    """
    prioritize_work() - infer what to work on next from workflow signals.

    The tool's own priority reasoning (not a human-assigned rank readback).
    Deterministic. Signals, in order:
      1. In-progress items (finish what's started) - detected from item text.
      2. The human's declared structure: next_up before backlog, by rank.
      3. known_issue findings surfaced alongside (not folded into the single
         pick - bugs-vs-features is the human's call).
    Returns a single RECOMMENDED item with the reason, then the full breakdown.
    """
    from determined.intent.workflow_store import list_items
    conn = getattr(assessor, "_knowledge_conn", None)
    if conn is None:
        return "No knowledge DB available."

    def is_wip(item: dict) -> bool:
        text = (item["subject"] + " " + item["content"]).lower()
        return any(m in text for m in _WIP_MARKERS)

    next_up = list_items(conn, kind="next_up", status="active", limit=20)
    backlog = list_items(conn, kind="backlog", status="active", limit=20)
    future  = list_items(conn, kind="future_plan", status="active", limit=20)
    issues  = assessor.list_artifacts(kind="known_issue") if assessor else []

    wip          = [i for i in (next_up + backlog) if is_wip(i)]
    next_up_rest = [i for i in next_up if not is_wip(i)]
    backlog_rest = [i for i in backlog if not is_wip(i)]

    # Single recommendation: in-progress > next_up > backlog > (else) first issue.
    # Declared workflow outranks incidental issue notes for the single pick.
    if wip:
        rec, reason = wip[0], "already in progress - finish what's started"
    elif next_up_rest:
        rec, reason = next_up_rest[0], "highest-priority declared next_up item"
    elif backlog_rest:
        rec, reason = backlog_rest[0], "top of backlog (no next_up items remain)"
    elif issues:
        rec, reason = None, None
    else:
        rec, reason = None, None

    lines: list[str] = []
    if rec:
        lines.append(f">>> RECOMMENDED: {rec['subject']} ({reason})")
        lines.append(f"    {rec['content']}")
    elif issues:
        lines.append(f">>> RECOMMENDED: fix '{issues[0]['subject']}' "
                     f"(open confirmed issue, no active workflow items)")
        lines.append(f"    {issues[0]['content'][:200]}")
    else:
        lines.append(">>> No active work items. Add next_up items or run discovery.")
    lines.append("")

    def emit(title: str, items: list[dict]):
        lines.append(title)
        for i in items:
            r = f"#{i['rank']} " if i.get("rank") else ""
            lines.append(f"  {r}{i['id']}. {i['subject']}: {i['content'][:80]}")

    if wip:
        emit("IN PROGRESS (finish first):", wip)
    if next_up_rest:
        emit("NEXT UP (declared priority):", next_up_rest)
    if backlog_rest:
        emit("BACKLOG:", backlog_rest[:5])
    if issues:
        lines.append(f"OPEN ISSUES (known_issue findings, {len(issues)}):")
        for a in issues[:5]:
            lines.append(f"  {a['subject']}: {a['content'][:80]}")
    if future:
        lines.append(f"FUTURE PLANS ({len(future)}):")
        for i in future[:5]:
            lines.append(f"  {i['id']}. {i['subject']}: {i['content'][:60]}")
    return "\n".join(lines)


def store_workflow_item(assessor: "Assessor", args: dict) -> str:
    """
    store_workflow_item(kind, subject, content, rank?) - add a workflow item.
    kind: next_up | backlog | future_plan | session_decision
    """
    kind = args.get("kind", "").strip()
    subject = args.get("subject", "").strip()
    content = args.get("content", "").strip()
    rank = args.get("rank")
    if not kind or not subject or not content:
        return "ERROR: kind, subject, and content are required"
    try:
        rank_int = int(rank) if rank is not None else None
        item_id = assessor.add_workflow_item(kind, subject, content, rank_int, "ai-suggested")
        return f"Stored {kind} item #{item_id}: {subject}"
    except (ValueError, RuntimeError) as e:
        return f"ERROR: {e}"


def rerank_workflow(assessor: "Assessor", args: dict) -> str:
    """
    rerank_workflow(order) - rerank items by ID order.
    order: comma-separated item IDs in desired priority order, e.g. "3,1,4,2"
    """
    order_str = args.get("order", "").strip()
    if not order_str:
        return "ERROR: order argument required (comma-separated item IDs)"
    try:
        ids = [int(x.strip()) for x in order_str.split(",") if x.strip()]
        count = assessor.rerank_workflow(ids)
        return f"Reranked {count} items: {' > '.join(str(i) for i in ids)}"
    except ValueError:
        return "ERROR: order must be comma-separated integers (item IDs)"


# ------------------------------------------------------------------
# TRUTH LAYER TOOL
# ------------------------------------------------------------------

def ask_truth_layer(assessor: "Assessor", args: dict) -> str:
    """
    ask_truth_layer(question) - NL query through the Truth Kernel algebra.
    Returns structured answer from the 7 truth views. Use for system-wide
    structural questions, not per-symbol questions (use other tools for those).
    """
    question = args.get("question", "").strip()
    if not question:
        return "ERROR: question argument required"
    try:
        result = assessor.ask(question)
        # result is a QuerySessionResult - extract readable content
        answer = result.get_field("content") if hasattr(result, "get_field") else str(result)
        return f"Truth layer answer:\n{answer}"
    except Exception as e:
        return f"Truth layer error: {e}"


# ------------------------------------------------------------------
# TOOL REGISTRY - maps tool name -> (function, required_arg, layer)
# layer: 'oracle' | 'assessor' (determines which object to pass)
# ------------------------------------------------------------------

def extract_design_facts(assessor: "Assessor", args: dict) -> str:
    """
    extract_design_facts() - scan corpus for structural facts and store in knowledge.db.
    No LLM required. Writes: entry points, dead code candidates, hot symbols, stub files.
    Safe to re-run; skips subjects already stored. Run after ingestion to seed knowledge.
    """
    counts = assessor.extract_design_facts()
    if "error" in counts:
        return f"ERROR: {counts['error']}"
    total = sum(counts.values())
    if total == 0:
        # Already populated — report what's in the DB rather than "0 extracted"
        conn = getattr(assessor, "_knowledge_conn", None)
        if conn:
            summary = {}
            for kind in ("entry", "dead", "hot", "stub"):
                n = conn.execute(
                    "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind = ?", (kind,)
                ).fetchone()[0]
                if n:
                    summary[kind] = n
            if summary:
                return (
                    "Structural facts already populated (nothing new to extract): "
                    + ", ".join(f"{k}={v}" for k, v in summary.items())
                )
        return "No new structural facts to extract (already populated or corpus has no graph data)."
    return (
        f"Extracted {total} structural facts into corpus DB: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    )


def _describe_tool_wrapper(oracle, args: dict) -> str:
    from determined.agent.tool_registry import describe_tool_fn
    return describe_tool_fn(oracle, args)


def discover_docs_tool(oracle: "DBOracle", args: dict) -> str:
    """
    discover_docs() - find all documentation files in the project.
    Returns inventory ranked by design-relevance (constraint score).
    """
    from determined.agent.doc_extractor import discover_docs
    root = oracle.get_project_root()
    if not root:
        return "ERROR: project root not found in corpus DB"
    docs = discover_docs(root)
    if not docs:
        return "No documentation files found in project"
    lines = [f"Documentation inventory ({len(docs)} files, project root: {root}):"]
    for d in docs:
        score_bar = "▓" * int(d.constraint_score * 10) + "░" * (10 - int(d.constraint_score * 10))
        lines.append(
            f"  [{d.doc_type:9s}] {d.rel_path}  "
            f"({d.size_bytes//1024}KB, {d.heading_count} headings, "
            f"constraint density: {score_bar} {d.constraint_score:.2f})"
        )
    return "\n".join(lines)


def ingest_design_docs(assessor: "Assessor", args: dict) -> str:
    """
    ingest_design_docs(min_score?) - extract design rules from all docs and store as
    design_note artifacts. Only processes docs with constraint_score >= min_score (default 0.05).
    Idempotent: skips rules already stored for a subject.
    """
    from determined.agent.doc_extractor import (
        discover_docs, extract_rules, extract_rules_llm,
        detect_conflicts, deduplicate, _split_by_headings,
        _extract_constraint_sentences, _CONSTRAINT_RE,
    )
    oracle = assessor.oracle
    root = oracle.get_project_root()
    if not root:
        return "ERROR: project root not found in corpus DB"
    min_score = float(args.get("min_score", 0.05))
    use_llm = args.get("use_llm", True)
    docs = discover_docs(root)
    design_docs = [d for d in docs if d.constraint_score >= min_score]
    if not design_docs:
        return f"No docs with constraint score >= {min_score} found (run discover_docs to see inventory)"

    stored = 0
    skipped = 0
    errors = 0
    conflicted = 0
    processed_files: list[str] = []
    all_rules = []

    for doc in design_docs:
        try:
            rules = extract_rules(doc.path, doc.rel_path, source_confidence=doc.confidence)
        except Exception:
            errors += 1
            continue
        if not rules:
            continue
        processed_files.append(doc.rel_path)
        all_rules.extend(rules)

        # LLM fallback for sections with design prose but sparse explicit signal
        if use_llm:
            try:
                text = open(doc.path, encoding="utf-8", errors="ignore").read()
                for heading, body in _split_by_headings(text):
                    det_count = len(_extract_constraint_sentences(body))
                    body_has_prose = len(body) > 100
                    lines_with_signal = sum(1 for ln in body.splitlines() if _CONSTRAINT_RE.search(ln))
                    sparse = det_count < 2 and lines_with_signal > 0
                    if body_has_prose and sparse:
                        llm_rules = extract_rules_llm(
                            doc.path, heading, body,
                            source_confidence=doc.confidence,
                            rel_path=doc.rel_path,
                        )
                        all_rules.extend(llm_rules)
            except Exception:
                pass

    # Conflict detection and dedup across all sources
    all_rules = detect_conflicts(all_rules)
    conflicted = sum(1 for r in all_rules if r.confidence == "conflicted")
    all_rules = deduplicate(all_rules)

    for rule in all_rules:
        existing = assessor.get_artifacts(rule.subject)
        already = any(
            a["kind"] == "design_note" and rule.rule[:60] in (a.get("content") or "")
            for a in existing
        )
        if already:
            skipped += 1
            continue
        # Provenance maps confidence to the controlled vocabulary:
        # authoritative/human-authored docs -> human-confirmed
        # everything else -> ai-generated
        prov = "human-confirmed" if rule.confidence == "authoritative" else "ai-generated"
        # Encode confidence + source in content so it is queryable later
        content = f"[{rule.kind.upper()}|{rule.confidence}|{rule.source_file}] {rule.rule}"
        assessor.add_artifact(rule.subject, "design_note", content, provenance=prov)
        stored += 1

    lines = [
        f"Design doc ingestion: {stored} rules stored, {skipped} already present, {errors} errors",
    ]
    if conflicted:
        lines.append(f"  Conflicts detected: {conflicted} rules flagged for human review")
    lines.append(f"Processed {len(processed_files)} docs:")
    for f in processed_files:
        lines.append(f"  {f}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# INCREMENTAL RE-INGEST
# ------------------------------------------------------------------

def reingest_file(assessor: "Assessor", args: dict) -> str:
    """
    reingest_file(file_path) - re-ingest a single changed file into the
    active corpus DB without touching other files. Updates symbols,
    functions, classes, imports, behavioral contracts, mutations,
    symbol references, and outbound graph edges for the named file.
    Inbound edges from other files that referenced removed symbols remain
    as dangling references until those callers are also re-ingested.
    """
    file_path = args.get("file_path", "").strip()
    if not file_path:
        return "ERROR: file_path is required"

    oracle = assessor.oracle
    db_path = getattr(oracle, "db_path", None) or getattr(oracle, "_db_path", None)
    if not db_path:
        return "ERROR: could not determine corpus DB path from oracle"

    from determined.ingestion.reingest_file import reingest_file as _reingest
    try:
        return _reingest(db_path=db_path, file_path=file_path)
    except FileNotFoundError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR during re-ingest: {e}"


# ------------------------------------------------------------------
# GOAL INTAKE
# ------------------------------------------------------------------

def goal_intake(assessor: "Assessor", args: dict) -> str:
    """
    goal_intake(goal) - translate a developer's natural language goal into a
    navigation plan: relevant design rules, hot/safe zones, stubs to extend,
    safe insertion points. Returns an ordered approach the developer can follow.
    """
    goal = args.get("goal", "").strip()
    if not goal:
        return "ERROR: goal argument required (describe what you want to build or change)"

    oracle = assessor.oracle
    _root = (oracle.get_project_root() or "").replace("\\", "/").rstrip("/")

    def _rel(fp: str) -> str:
        fp = (fp or "").replace("\\", "/")
        return fp[len(_root) + 1:] if _root and fp.startswith(_root + "/") else fp

    out = [f"Goal: {goal}", ""]

    # --- Step 1: Find relevant symbols via semantic search ---
    # Use _search_symbols_raw (XIV: one source of truth for symbol lookup + docstring join)
    all_syms = _search_symbols_raw(oracle, "", limit=600)
    sym_rows = [r for r in all_syms if r.get("docstring")]

    # Load distilled file summaries from corpus DB to enrich symbol text
    distilled_by_stem: dict[str, str] = {}
    try:
        dist_rows = oracle.conn.execute(
            "SELECT subject, distilled FROM semantic_summaries "
            "WHERE distilled IS NOT NULL AND distilled != ''"
        ).fetchall()
        for subj, distilled in dist_rows:
            stem = subj.replace("\\", "/").split("/")[-1].replace(".py", "")
            distilled_by_stem[stem] = distilled
    except Exception:
        pass  # semantic_summaries may not exist yet; degrade gracefully

    relevant_symbols: list[tuple] = []  # (name, file_path, score)
    if sym_rows:
        try:
            model = _get_embed_model()
            sym_texts = []
            for r in sym_rows:
                stem = r["file_path"].replace("\\", "/").split("/")[-1].replace(".py", "")
                dist = distilled_by_stem.get(stem, "")
                sym_texts.append(f"{r['name']} {(r['docstring'] or '')[:200]} {dist}")
            vecs = model.encode([goal] + sym_texts, normalize_embeddings=True)
            scores = vecs[1:] @ vecs[0]
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            for idx, score in ranked[:5]:
                if score >= 0.28:
                    relevant_symbols.append((sym_rows[idx]["name"], sym_rows[idx]["file_path"], score))
        except Exception:
            pass

    # --- Step 2: Risk badges for relevant symbols ---
    from determined.agent.risk_annotator import score_risk
    risk_cache: dict[str, dict] = {}

    if relevant_symbols:
        out.append("Relevant area (semantic match):")
        for sym_name, sym_file, score in relevant_symbols:
            if sym_name not in risk_cache:
                risk_cache[sym_name] = score_risk(oracle, sym_name)
            r = risk_cache[sym_name]
            badge = r.get("level", "UNKNOWN")
            fp = _rel(sym_file)
            reasons = "; ".join(r.get("reasons", []))
            out.append(f"  {badge:4}  {sym_name}  ({fp})")
            if reasons:
                out.append(f"        {reasons}")
        out.append("")

    # --- Step 3: Relevant SOTS tenets ---
    from determined.data.sots_loader import search_tenets
    tenet_hits = search_tenets(goal, threshold=0.30, top_n=4)
    if tenet_hits:
        out.append("Design rules that apply (SOTS):")
        for t in tenet_hits:
            out.append(f"  [{t['id']}] {t['title']}: {t['description'][:120]}")
        out.append("")

    # --- Step 4: Stubs near relevant files ---
    relevant_files = {sym_file for _, sym_file, _ in relevant_symbols}
    stub_rows = []  # stubs now detected from corpus DB directly (see stub_syms below)

    # Also check oracle for stub-like symbols (no callers, no body inferred from docstring)
    stub_syms = oracle.conn.execute(
        "SELECT f.name, f.file_path FROM functions f "
        "WHERE f.file_path IN ({}) "
        "AND NOT EXISTS (SELECT 1 FROM graph_edges e WHERE e.callee = f.name) "
        "AND f.name NOT LIKE '__%__' "
        "LIMIT 10".format(",".join("?" * len(relevant_files)) if relevant_files else "'__none__'"),
        list(relevant_files)
    ).fetchall() if relevant_files else []

    if stub_rows or stub_syms:
        out.append("Scaffolding / safe insertion points:")
        seen = set()
        for row in stub_rows:
            subj = row[0]
            if any(f in subj for f in relevant_files) and subj not in seen:
                out.append(f"  [stub file]  {subj}")
                seen.add(subj)
        for sym_name, sym_file in stub_syms:
            if sym_name not in seen:
                fp = _rel(sym_file)
                out.append(f"  [no callers] {sym_name}  ({fp})  -- safe to implement/extend")
                seen.add(sym_name)
        if not seen:
            out.append("  (none found near relevant area)")
        out.append("")

    # --- Step 5: Navigation plan ---
    out.append("Suggested approach:")
    step = 1

    # Read the most relevant HOT symbol first to understand the boundary
    hot = [(n, f) for n, f, _ in relevant_symbols
           if risk_cache.get(n, {}).get("level") == "HOT"]
    warm = [(n, f) for n, f, _ in relevant_symbols
            if risk_cache.get(n, {}).get("level") == "WARM"]
    safe = [(n, f) for n, f, _ in relevant_symbols
            if risk_cache.get(n, {}).get("level") in ("SAFE", "UNKNOWN")]

    if hot:
        for sym_name, sym_file in hot[:2]:
            fp = _rel(sym_file)
            out.append(f"  {step}. READ (do not modify): {sym_name} in {fp} -- HOT, understand the boundary first")
            step += 1
    if warm:
        for sym_name, sym_file in warm[:2]:
            fp = _rel(sym_file)
            out.append(f"  {step}. REVIEW: {sym_name} in {fp} -- WARM, check callers before changing")
            step += 1

    # Stubs and safe symbols are the insertion points
    for sym_name, sym_file in stub_syms[:3]:
        fp = _rel(sym_file)
        out.append(f"  {step}. EXTEND: {sym_name} in {fp} -- no callers, safe insertion point")
        step += 1
    if safe:
        for sym_name, sym_file in safe[:1]:
            fp = _rel(sym_file)
            out.append(f"  {step}. MODIFY: {sym_name} in {fp} -- SAFE zone")
            step += 1

    if step == 1:
        out.append("  No clear insertion point found. Run orient_to_codebase first to populate knowledge.")

    return "\n".join(out)


def _project_status_data(oracle: "DBOracle", assessor: "Assessor") -> dict:
    """
    Gather structural facts needed for project_status synthesis.
    Pure data assembly - no Ollama, no side effects (SOTS XI).
    Returns a dict with: subsystems, critical_stubs, clusters, arch_flags, totals.
    """
    root = (oracle.get_project_root() or "").replace("\\", "/").rstrip("/")

    def _rel(fp: str) -> str:
        fp = (fp or "").replace("\\", "/")
        return fp[len(root) + 1:] if root and fp.startswith(root + "/") else fp

    def _subsystem(rel_path: str) -> str:
        parts = rel_path.split("/")
        if len(parts) == 1:
            return "(root)"
        # Collapse nested dirs to top-level (world/visuals/ -> world/)
        return parts[0] + "/"

    # --- Subsystem matrix ---
    # Per-subsystem: total functions, stubs, entry points (no callers in), hot symbols
    file_rows = oracle.conn.execute(
        "SELECT file_path FROM files"
    ).fetchall()
    all_files = [_rel(r[0]) for r in file_rows]

    fn_rows = oracle.conn.execute(
        "SELECT name, file_path, is_stub FROM functions"
    ).fetchall()

    callee_set = {
        r[0] for r in oracle.conn.execute(
            "SELECT DISTINCT callee FROM graph_edges"
        ).fetchall()
    }
    caller_set = {
        r[0] for r in oracle.conn.execute(
            "SELECT DISTINCT caller FROM graph_edges"
        ).fetchall()
    }

    hot_names = set()
    if assessor._knowledge_conn:
        hot_rows = assessor._knowledge_conn.execute(
            "SELECT subject FROM knowledge_artifacts WHERE kind='hot'"
        ).fetchall()
        for (s,) in hot_rows:
            hot_names.add(s.replace("hot::", "").strip())

    subs: dict[str, dict] = {}
    for name, fp, is_stub in fn_rows:
        key = _subsystem(_rel(fp))
        if key not in subs:
            subs[key] = {"fns": 0, "stubs": 0, "entry_pts": 0, "hot": 0}
        subs[key]["fns"] += 1
        if is_stub:
            subs[key]["stubs"] += 1
        # entry point: called by nobody in the graph
        if name not in callee_set and name in caller_set:
            subs[key]["entry_pts"] += 1
        if name in hot_names:
            subs[key]["hot"] += 1

    # Filter out test subsystems for cleaner output
    prod_subs = {k: v for k, v in subs.items()
                 if "test" not in k.lower() and k not in ("tests/",)}

    # --- Critical path stubs (stubs with callers waiting on them) ---
    stub_names = {
        r[0] for r in oracle.conn.execute(
            "SELECT name FROM functions WHERE is_stub = 1"
        ).fetchall()
    }
    caller_counts: dict[str, int] = {}
    for row in oracle.conn.execute(
        "SELECT callee, COUNT(DISTINCT caller) FROM graph_edges GROUP BY callee"
    ).fetchall():
        callee, cnt = row
        bare = callee.rsplit(".", 1)[-1]
        if bare in stub_names:
            caller_counts[bare] = caller_counts.get(bare, 0) + cnt

    critical_stubs = sorted(
        [{"name": n, "callers": c} for n, c in caller_counts.items() if c > 0],
        key=lambda x: x["callers"], reverse=True
    )[:15]

    # Enrich with file path
    for item in critical_stubs:
        row = oracle.conn.execute(
            "SELECT file_path FROM functions WHERE name = ? AND is_stub = 1 LIMIT 1",
            (item["name"],),
        ).fetchone()
        item["file"] = _rel(row[0]).split("/")[-1] if row else "?"

    # --- Clusters ---
    from determined.agent.graph_utils import find_clusters
    clusters = find_clusters(oracle, min_edges=2)
    prod_clusters = [
        c for c in clusters
        if not any("test" in f.lower() for f in c["files"])
    ][:8]
    cluster_data = [
        {
            "f1": c["files"][0].replace("\\", "/").split("/")[-1],
            "f2": c["files"][1].replace("\\", "/").split("/")[-1],
            "edges": c["edge_count"],
        }
        for c in prod_clusters
    ]

    # --- Architecture flags: SOTS tenets with constraint language ---
    from determined.data.sots_loader import load_tenets
    _constraint_words = ("must not", "never", "forbidden", "prohibited", "must be", "only")
    arch_flags = []
    for t in load_tenets():
        text = (t["description"] + " " + t["ask"]).lower()
        if any(w in text for w in _constraint_words):
            snippet = f"{t['title']}: {t['description'][:120]}"
            arch_flags.append({"subject": f"SOTS {t['id']}", "constraint": snippet})
        if len(arch_flags) >= 15:
            break

    totals = {
        "files": len(all_files),
        "functions": sum(v["fns"] for v in subs.values()),
        "stubs": sum(v["stubs"] for v in subs.values()),
        "entry_points": sum(v["entry_pts"] for v in prod_subs.values()),
    }

    return {
        "subsystems": prod_subs,
        "critical_stubs": critical_stubs,
        "clusters": cluster_data,
        "arch_flags": arch_flags,
        "totals": totals,
        "root": root,
    }


def _format_project_status(data: dict) -> str:
    """Format _project_status_data as readable text (no Ollama)."""
    t = data["totals"]
    lines = [
        f"Project: {data['root'].split('/')[-1]}  "
        f"({t['files']} files, {t['functions']} functions, "
        f"{t['stubs']} stubs, {t['entry_points']} entry points)",
        "",
        "Subsystems (implementation status):",
    ]
    # Sort by stub density (stubs/fns) descending — most skeleton first
    ordered = sorted(
        data["subsystems"].items(),
        key=lambda kv: (kv[1]["stubs"] / max(kv[1]["fns"], 1)),
        reverse=True,
    )
    for key, v in ordered:
        if v["fns"] == 0:
            continue
        stub_pct = int(100 * v["stubs"] / v["fns"])
        done_pct = 100 - stub_pct
        bar = "█" * (done_pct // 10) + "░" * (10 - done_pct // 10)
        status = (
            "SKELETON" if stub_pct >= 40
            else "PARTIAL" if stub_pct >= 10
            else "implemented"
        )
        lines.append(
            f"  {key:18s} fns={v['fns']:4d}  stubs={v['stubs']:3d} [{bar}] {done_pct:3d}% done  [{status}]"
            f"  entry={v['entry_pts']}  hot={v['hot']}"
        )

    if data["critical_stubs"]:
        lines.append("")
        lines.append("Critical path gaps (stubs that callers are waiting on):")
        for s in data["critical_stubs"]:
            flag = " *** BLOCKING" if s["callers"] >= 10 else ""
            lines.append(f"  {s['name']} ({s['file']}) — {s['callers']} callers{flag}")

    if data["clusters"]:
        lines.append("")
        lines.append("Tightly coupled subsystems:")
        for c in data["clusters"]:
            lines.append(f"  {c['f1']} <-> {c['f2']}  ({c['edges']} edges)")

    if data["arch_flags"]:
        lines.append("")
        lines.append("Architecture constraints / flags:")
        for f in data["arch_flags"][:8]:
            lines.append(f"  [{f['subject']}] {f['constraint'][:120]}")

    return "\n".join(lines)


def _synthesize_with_ollama(status_text: str, goal: str, conn=None) -> str | None:
    """
    Pass the structured status to llama-server for narrative synthesis.
    Returns None on failure (SOTS XIII: visible failure, not swallowed).
    Checks semantic cache first if conn is provided.
    """
    from determined.agent.llm_client import generate as _llm_generate, LLM_TIMEOUT
    prompt = (
        f"You are a software architect reviewing a game project's structural analysis.\n\n"
        f"DATA FORMAT GUIDE:\n"
        f"- 'stubs=N' means N functions have empty/placeholder bodies (not yet implemented)\n"
        f"- 'done=X%' means X percent of functions in that subsystem are fully implemented\n"
        f"- [SKELETON] = mostly stubs, largely unimplemented\n"
        f"- [PARTIAL] = some implementation exists but significant gaps remain\n"
        f"- [implemented] = mostly or fully working code\n"
        f"- 'entry=N' = N public entry points (callable surfaces)\n"
        f"- 'hot=N' = N functions called frequently (high in-degree)\n"
        f"- Critical path gaps = stubs that other code is already calling (blocking work)\n\n"
        f"Based ONLY on the data below, answer: {goal}\n\n"
        f"Be specific - name the systems, files, and functions you see. "
        f"Do not invent information not in the data. Under 350 words.\n\n"
        f"STRUCTURAL DATA:\n{status_text}"
    )
    if conn is not None:
        from determined.agent.semantic_cache import lookup, store
        cached = lookup(prompt, conn)
        if cached is not None:
            return cached
    result = _llm_generate(prompt, timeout=LLM_TIMEOUT)
    if result is not None and conn is not None:
        from determined.agent.semantic_cache import store
        store(prompt, result, conn)
    return result


def project_status(assessor: "Assessor", args: dict) -> str:
    """
    project_status(goal?) - structural picture of the whole project: which subsystems
    exist, which are skeleton vs active, what's blocking the critical path, how things
    couple, and what design constraints apply. Optionally synthesizes with Ollama.

    goal: optional question to focus the synthesis (e.g. 'what should I work on first
          to make the game playable?'). If omitted, returns structural breakdown only.
    """
    oracle = assessor.oracle
    data = _project_status_data(oracle, assessor)
    structural = _format_project_status(data)

    # Warn if semantic enrichment is missing (SOTS XVIII: explain why result is limited)
    enrichment_note = ""
    try:
        tables = {r[0] for r in oracle.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "semantic_summaries" not in tables:
            enrichment_note = (
                "\nNote: no semantic summaries found for this corpus. "
                "Re-ingest with --summarize to get LLM-enriched analysis "
                "(domain understanding, distillations, design cross-references)."
            )
        else:
            sem_count = oracle.conn.execute(
                "SELECT COUNT(*) FROM semantic_summaries"
            ).fetchone()[0]
            if sem_count == 0:
                enrichment_note = (
                    "\nNote: semantic_summaries table exists but is empty. "
                    "Re-ingest with --summarize to get LLM-enriched analysis."
                )
    except Exception:
        pass

    goal = args.get("goal", "").strip()
    if not goal:
        return structural + enrichment_note

    # Attempt Ollama synthesis; degrade to structural if unavailable (SOTS XIII)
    synthesis = _synthesize_with_ollama(structural, goal, conn=assessor.oracle.conn)
    if synthesis:
        return structural + enrichment_note + "\n\n--- Synthesis ---\n" + synthesis
    return structural + enrichment_note + "\n\n(llama-server unavailable for synthesis - structural data above)"


def distill_corpus(assessor: "Assessor", args: dict) -> str:
    """
    distill_corpus() - compress each semantic_summary into a one-sentence
    distillation stored in semantic_summaries.distilled (corpus DB).
    Idempotent: skips rows already distilled. Aborts if llama-server is down.
    """
    corpus_conn = assessor.oracle.conn

    # Abort early if llama-server is unreachable (SOTS XIII)
    probe = _distill_to_one_sentence("test", "__probe__")
    if probe is None:
        return "ERROR: llama-server is not reachable. distill_corpus requires llama-server running."

    corpus_tables = {r[0] for r in corpus_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "semantic_summaries" not in corpus_tables:
        return (
            "No semantic_summaries found in corpus DB. "
            "Re-ingest with --summarize to generate them, then run distill_corpus."
        )

    # Rows needing distillation: have content but no distilled value yet (SOTS X)
    pending = corpus_conn.execute(
        "SELECT id, subject, content FROM semantic_summaries "
        "WHERE content IS NOT NULL AND (distilled IS NULL OR distilled = '')"
    ).fetchall()

    already_done = corpus_conn.execute(
        "SELECT COUNT(*) FROM semantic_summaries "
        "WHERE distilled IS NOT NULL AND distilled != ''"
    ).fetchone()[0]

    if not pending:
        if already_done:
            return f"distill_corpus: all {already_done} summaries already distilled."
        return (
            "semantic_summaries table is empty. "
            "Re-ingest with --summarize to populate it, then run distill_corpus."
        )

    stored = 0
    for row_id, subject, content in pending:
        sentence = _distill_to_one_sentence(content, subject, conn=corpus_conn)
        if sentence is None:
            return f"ERROR: llama-server stopped responding mid-run after {stored} stored."
        corpus_conn.execute(
            "UPDATE semantic_summaries SET distilled = ? WHERE id = ?",
            (sentence, row_id),
        )
        corpus_conn.commit()
        stored += 1

    return (
        f"distill_corpus: {stored} distilled, {already_done} already cached "
        f"({stored + already_done} total)"
    )


TOOLS = {
    "search_symbols":    (search_symbols,    "oracle"),
    "search_files":      (search_files,      "oracle"),
    "list_callers":      (list_callers,      "oracle"),
    "list_callees":      (list_callees,      "oracle"),
    "symbols_in_file":   (symbols_in_file,   "oracle"),
    "files_in_directory":(files_in_directory,"oracle"),
    "describe_file":     (describe_file,     "assessor"),
    "symbol_intent":     (symbol_intent,     "oracle"),
    "symbol_brief":      (symbol_brief,      "assessor"),
    "get_findings":         (get_findings,         "assessor"),
    "store_finding":        (store_finding,        "assessor"),
    "knowledge_status":     (knowledge_status,     "assessor"),
    "extract_design_facts": (extract_design_facts, "assessor"),
    "ask_truth_layer":      (ask_truth_layer,      "assessor"),
    "graph_path":           (graph_path,           "oracle"),
    "graph_entry_points":   (graph_entry_points,   "oracle"),
    "graph_most_connected": (graph_most_connected, "oracle"),
    "graph_subgraph":       (graph_subgraph,       "oracle"),
    "graph_clusters":       (graph_clusters,       "oracle"),
    "list_findings_by_kind": (list_findings_by_kind, "assessor"),
    "missing_docstrings":   (missing_docstrings,   "oracle"),
    "find_todos":           (find_todos,           "oracle"),
    "git_log_for":          (git_log_for,          "oracle"),
    "workflow_status":      (workflow_status,      "assessor"),
    "prioritize_work":      (prioritize_work,      "assessor"),
    "store_workflow_item":  (store_workflow_item,  "assessor"),
    "rerank_workflow":      (rerank_workflow,      "assessor"),
    "risk_profile":         (risk_profile,         "assessor"),
    "describe_tool":        (_describe_tool_wrapper, "oracle"),
    # Level-4 edge tools
    "edges_of":             (edges_of,             "oracle"),
    "edge_detail":          (edge_detail,           "oracle"),
    "list_import_deps":     (list_import_deps,      "oracle"),
    "add_edge":             (add_edge,              "assessor"),
    # Bag tools
    "bag_status":           (bag_status,            "assessor"),
    "bag_list":             (bag_list,              "assessor"),
    "bag_add":              (bag_add,               "assessor"),
    "bag_label":            (bag_label,             "assessor"),
    "bag_clear":            (bag_clear,             "assessor"),
    "bag_report":           (bag_report,            "assessor"),
    # Stub tools
    "list_stubs":           (list_stubs,            "oracle"),
    "project_stub":         (project_stub,          "oracle"),
    # Doc tools
    "discover_docs":        (discover_docs_tool,    "oracle"),
    "ingest_design_docs":   (ingest_design_docs,    "assessor"),
    # Goal intake
    "goal_intake":          (goal_intake,           "assessor"),
    # Distillation
    "distill_corpus":       (distill_corpus,        "assessor"),
    # Design violation cross-reference
    "check_design_violations": (check_design_violations, "assessor"),
    # Project-wide synthesis
    "project_status":          (project_status,          "assessor"),
    # Incremental re-ingest
    "reingest_file":           (reingest_file,           "assessor"),
}


def dispatch(tool_name: str, args: dict, oracle: "DBOracle", assessor: "Assessor") -> str:
    """
    Execute a tool by name. Returns result string.

    If a tool returns (text, items) instead of a plain string, the items
    list is forwarded to the system bag (auto-accumulation). The display
    text is returned as usual. This lets tools like edges_of emit EdgeRefs
    into the bag without the caller needing to do anything extra.
    """
    if tool_name not in TOOLS:
        available = ", ".join(TOOLS)
        return f"ERROR: unknown tool '{tool_name}'. Available: {available}"
    fn, layer = TOOLS[tool_name]
    obj = oracle if layer == "oracle" else assessor
    try:
        result = fn(obj, args)
        if isinstance(result, tuple) and len(result) == 2:
            text, items = result
            # Auto-populate system bag if assessor has bags available
            if items and hasattr(assessor, "bags") and assessor.bags is not None:
                assessor.bags.auto_add_items(items)
            return text
        return result
    except Exception as e:
        return f"ERROR in {tool_name}: {type(e).__name__}: {e}"
