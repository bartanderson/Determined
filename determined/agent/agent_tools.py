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
    results = oracle.find_symbols(query, limit=20)
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
    rows = oracle.conn.execute(
        """
        SELECT ge.caller, sr.file_path, ge.line_number
        FROM graph_edges ge
        LEFT JOIN symbol_references sr
            ON ge.caller = sr.caller AND ge.callee = sr.callee
        WHERE ge.callee = ? OR ge.callee LIKE ?
        ORDER BY sr.file_path, ge.line_number
        """,
        (symbol, f"%.{symbol}"),
    ).fetchall()
    if not rows:
        return f"No direct callers found for '{symbol}'"
    lines = [f"Direct callers of '{symbol}':"]
    for r in rows:
        file_short = (r[1] or "?").replace("\\", "/").split("/")[-1]
        lines.append(f"  {r[0]} in {file_short} line {r[2]}")
    return "\n".join(lines)


def list_callees(oracle: "DBOracle", args: dict) -> str:
    """
    list_callees(symbol) - what this symbol calls, from graph_edges.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    # No SQL LIMIT: a function calling print() 30x would otherwise crowd out
    # every real callee. Pull all, drop builtins, dedupe by callee, then cap.
    rows = oracle.conn.execute(
        """
        SELECT ge.callee, sr.file_path, ge.line_number
        FROM graph_edges ge
        LEFT JOIN symbol_references sr
            ON ge.caller = sr.caller AND ge.callee = sr.callee
        WHERE ge.caller = ?
        ORDER BY ge.line_number
        """,
        (symbol,),
    ).fetchall()
    import builtins as _bi
    seen: dict[str, tuple] = {}
    counts: dict[str, int] = {}
    for callee, fp, ln in rows:
        bare = (callee or "").rsplit(".", 1)[-1]
        if not bare or bare in dir(_bi):
            continue  # skip builtins (print, len, ...) - not navigable symbols
        counts[callee] = counts.get(callee, 0) + 1
        if callee not in seen:
            seen[callee] = (fp, ln)
    if not seen:
        return f"No project callees for '{symbol}' (only builtins, or makes no calls)"
    lines = [f"'{symbol}' calls:"]
    for callee, (fp, ln) in list(seen.items())[:30]:
        file_short = (fp or "?").replace("\\", "/").split("/")[-1]
        n = counts[callee]
        suffix = f" (x{n})" if n > 1 else ""
        lines.append(f"  {callee} in {file_short} line {ln}{suffix}")
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
    return f"Summary of '{file_path}'{cache_note}:\n{content}"


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
    Prepends a risk annotation line (HOT/WARM/SAFE).
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    from determined.agent.risk_annotator import score_risk, risk_badge
    r = score_risk(assessor.oracle, symbol)
    badge = risk_badge(r["level"])
    brief = assessor.generate_task_md(symbol)
    risk_line = f"Risk: {badge}  ({'; '.join(r['reasons'])})"
    return risk_line + "\n" + brief


def risk_profile(oracle: "DBOracle", args: dict):
    """
    risk_profile(symbol) - structural change-risk rating for a symbol.
    Returns HOT/WARM/SAFE with the reasons: in-degree, mutations, blast radius.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    from determined.agent.risk_annotator import score_risk, risk_badge
    r = score_risk(oracle, symbol)
    badge = risk_badge(r["level"])
    lines = [f"Risk profile for '{symbol}': {badge}"]
    for reason in r["reasons"]:
        lines.append(f"  - {reason}")
    lines.append(f"  in_degree={r['in_degree']}  out_degree={r['out_degree']}  mutations={r['mutation_count']}")
    row = oracle.conn.execute("SELECT file_path FROM symbols WHERE name = ?", (symbol,)).fetchone()
    file_path = row[0] if row else ""
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
    from determined.agent.graph_utils import most_connected
    from determined.agent.risk_annotator import score_risk, risk_badge
    results = most_connected(oracle, n=15, filter_substr=filter_str)
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
    from determined.agent.graph_utils import subgraph_around
    sg = subgraph_around(oracle, symbol, radius=radius)
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
    lines = [f"File clusters ({len(clusters)} pairs):"]
    for c in clusters[:15]:
        f1 = c['files'][0].replace("\\", "/").split("/")[-1]
        f2 = c['files'][1].replace("\\", "/").split("/")[-1]
        lines.append(f"  {f1} <-> {f2}  ({c['edge_count']} edges)")
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
    if assessor._knowledge_conn is None:
        return "No knowledge DB configured."

    corpus = assessor.knowledge.corpus_key if assessor.knowledge else None
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
        f"Extracted {total} structural facts into knowledge.db: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    )


def _describe_tool_wrapper(oracle, args: dict) -> str:
    from determined.agent.tool_registry import describe_tool_fn
    return describe_tool_fn(oracle, args)


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
    "risk_profile":         (risk_profile,         "oracle"),
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
