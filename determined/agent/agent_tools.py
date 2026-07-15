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
import re
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
    list_callers(symbol, resolved_only=False) - direct callers from graph_edges.
    Matches bare name and module.name qualified forms.
    resolved_only=true restricts to annotation-resolved edges (less noise, less coverage).
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    resolved_only = bool(args.get("resolved_only", False))
    # Check if symbol is defined in multiple files (do before callers lookup)
    decl_rows = oracle.conn.execute(
        "SELECT DISTINCT file_path FROM symbols WHERE name = ?", (symbol,)
    ).fetchall()
    decl_files = [r[0].replace("\\", "/").split("/")[-1] for r in decl_rows]
    rows = _list_callers_raw(oracle, symbol, resolved_only=resolved_only)
    if not rows:
        if len(decl_files) > 1:
            return (f"No direct callers found for '{symbol}' "
                    f"[NOTE: '{symbol}' is defined in {len(decl_files)} files: "
                    f"{', '.join(decl_files)}]")
        return f"No direct callers found for '{symbol}'"
    if len(decl_files) > 1:
        header = (f"Direct callers of '{symbol}' "
                  f"[NOTE: '{symbol}' is defined in {len(decl_files)} files "
                  f"({', '.join(decl_files)}) — callers of all definitions combined]:")
    else:
        file_tag = f" ({decl_files[0]})" if decl_files else ""
        header = f"Direct callers of '{symbol}'{file_tag}:"
    lines = [header]
    for r in rows:
        file_short = (r["file_path"] or "?").replace("\\", "/").split("/")[-1]
        tag = " (annotation-resolved)" if r.get("resolved") else ""
        lines.append(f"  {r['caller']} in {file_short} line {r['line_number']}{tag}")
    return "\n".join(lines)


def blast_radius(oracle: "DBOracle", args: dict) -> str:
    """
    blast_radius(target, resolved_only=False) - what would break if target (file or symbol) were removed.
    If target ends in .py or contains a path separator, treats as a file and lists callers
    of each symbol in that file. Otherwise treats as a symbol and lists its callers + risk.
    resolved_only=true restricts to annotation-resolved edges (less noise, less coverage).
    """
    target = args.get("target", "").strip()
    if not target:
        return "ERROR: target argument required"
    resolved_only = bool(args.get("resolved_only", False))

    is_file = target.endswith(".py") or "/" in target or "\\" in target

    if is_file:
        # File-level blast radius: enumerate symbols, list callers of each
        rows = oracle.conn.execute(
            "SELECT name, 'function' AS symbol_type FROM functions WHERE file_path LIKE ? "
            "UNION SELECT name, 'class' AS symbol_type FROM classes WHERE file_path LIKE ?",
            (f"%{target}%", f"%{target}%"),
        ).fetchall()
        if not rows:
            return f"No symbols found in '{target}' (file not found or empty)"

        lines = [f"Blast radius of '{target}' ({len(rows)} symbols):"]
        total_callers = 0
        no_callers = []
        for row in rows[:15]:
            name = row[0]
            callers = _list_callers_raw(oracle, name, resolved_only=resolved_only)
            if callers:
                total_callers += len(callers)
                caller_names = [c["caller"] for c in callers[:3]]
                suffix = f" (+{len(callers)-3} more)" if len(callers) > 3 else ""
                lines.append(f"  {name}: called by {', '.join(caller_names)}{suffix}")
            else:
                no_callers.append(name)

        if no_callers:
            lines.append(f"  No callers: {', '.join(no_callers[:8])}" + (f" (+{len(no_callers)-8} more)" if len(no_callers) > 8 else ""))

        if total_callers == 0:
            lines.append("\nNo external callers found — file appears safe to remove.")
        else:
            lines.append(f"\n{total_callers} total caller dependencies. Removing this file would break those callers.")
        return "\n".join(lines)

    else:
        # Symbol-level blast radius: list callers + risk profile
        callers = _list_callers_raw(oracle, target, resolved_only=resolved_only)
        from determined.agent.risk_annotator import score_risk, risk_badge
        try:
            risk = score_risk(oracle, target)
            badge = risk_badge(risk["level"])
        except Exception:
            risk = {"level": "UNKNOWN", "reasons": []}
            badge = ""

        lines = [f"Blast radius of '{target}' {badge}:".strip()]
        if not callers:
            lines.append("  No direct callers found — removing this symbol appears safe.")
        else:
            caller_names = [c["caller"] for c in callers[:5]]
            suffix = f" (+{len(callers)-5} more)" if len(callers) > 5 else ""
            lines.append(f"  Direct callers ({len(callers)}): {', '.join(caller_names)}{suffix}")

        # Extended impact via subgraph
        sg = _graph_subgraph_raw(oracle, target, radius=2)
        extended = sorted(set(sg.get("nodes", [])) - {target})
        if extended:
            lines.append(f"  Extended impact ({len(extended)} symbols): {', '.join(extended[:5])}" + (f" ..." if len(extended) > 5 else ""))

        if risk.get("reasons"):
            lines.append(f"  Risk factors: {'; '.join(risk['reasons'][:3])}")

        return "\n".join(lines)


def list_callees(oracle: "DBOracle", args: dict) -> str:
    """
    list_callees(symbol, resolved_only=False) - what this symbol calls, from graph_edges.
    resolved_only=true restricts to annotation-resolved edges (less noise, less coverage).
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    resolved_only = bool(args.get("resolved_only", False))
    rows = _list_callees_raw(oracle, symbol, resolved_only=resolved_only)
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


def _list_callers_raw(oracle: "DBOracle", symbol: str, resolved_only: bool = False) -> list[dict]:
    """
    Direct callers of symbol from graph_edges.
    Returns list[dict]: caller, file_path, line_number, resolved.

    resolved_only=True filters to annotation-resolved edges, suppressing noise
    from bare-name collisions (e.g. a project function named 'get' being treated
    as a caller of stdlib dict.get).

    Queries target_id (canonical bare name) rather than the callee surface column.
    The callee column may store fully-qualified names for cross-module imports
    (e.g. "determined.agent.agent_resolver.ground_question") while target_id is
    always the bare name ("ground_question"). See graph_utils.py header for the
    full two-tier naming contract.
    """
    from determined.identity.symbol_identity import normalize_symbol
    from determined.agent.graph_utils import _has_id_columns
    canonical = normalize_symbol(symbol)
    res_filter = " AND ge.resolved = 1" if resolved_only else ""
    if _has_id_columns(oracle.conn):
        # Try exact canonical match first; if nothing, also try the raw symbol as
        # stored (handles Go "Type.Method" and Rust "Type::Method" where target_id
        # may be the bare method name OR the full FQDN depending on how it was emitted).
        # COALESCE(sr.file_path, f.file_path): symbol_references only exists for Python;
        # for Go/Rust callers fall back to the caller's row in functions for location.
        rows = oracle.conn.execute(
            f"""
            SELECT ge.caller,
                   COALESCE(sr.file_path, f.file_path),
                   COALESCE(ge.line_number, f.line_number),
                   COALESCE(ge.resolved, 0)
            FROM graph_edges ge
            LEFT JOIN symbol_references sr
                ON ge.caller = sr.caller AND ge.callee = sr.callee
            LEFT JOIN functions f
                ON ge.caller = f.name
            WHERE (ge.target_id = ? OR ge.target_id = ?){res_filter}
            ORDER BY COALESCE(sr.file_path, f.file_path), COALESCE(ge.line_number, f.line_number)
            """,
            (canonical, symbol),
        ).fetchall()
    else:
        # Compatibility: test fixtures that predate source_id/target_id columns.
        # Fall back to callee surface column with bare-name and FQ-name match.
        rows = oracle.conn.execute(
            f"""
            SELECT ge.caller,
                   COALESCE(sr.file_path, f.file_path),
                   COALESCE(ge.line_number, f.line_number),
                   COALESCE(ge.resolved, 0)
            FROM graph_edges ge
            LEFT JOIN symbol_references sr
                ON ge.caller = sr.caller AND ge.callee = sr.callee
            LEFT JOIN functions f
                ON ge.caller = f.name
            WHERE (ge.callee = ? OR ge.callee LIKE ?){res_filter}
            ORDER BY COALESCE(sr.file_path, f.file_path), COALESCE(ge.line_number, f.line_number)
            """,
            (canonical, f"%.{canonical}"),
        ).fetchall()
    return [{"caller": r[0], "file_path": r[1], "line_number": r[2], "resolved": bool(r[3])} for r in rows]


def _list_callees_raw(oracle: "DBOracle", symbol: str, resolved_only: bool = False) -> list[dict]:
    """
    Project callees of symbol from graph_edges (builtins filtered out).
    Returns list[dict]: callee, file_path, line_number, count, resolved.

    resolved_only=True filters to annotation-resolved edges only, reducing
    noise from bare-name collisions on generic method names (get, set, all, etc.).
    """
    import builtins as _bi
    res_filter = " AND ge.resolved = 1" if resolved_only else ""
    rows = oracle.conn.execute(
        f"""
        SELECT ge.callee,
               COALESCE(sr.file_path, f.file_path),
               COALESCE(ge.line_number, f.line_number),
               COALESCE(ge.resolved, 0)
        FROM graph_edges ge
        LEFT JOIN symbol_references sr
            ON ge.caller = sr.caller AND ge.callee = sr.callee
        LEFT JOIN functions f
            ON ge.callee = f.name
        WHERE ge.caller = ?{res_filter}
        ORDER BY COALESCE(ge.line_number, f.line_number)
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


def _graph_subgraph_raw(oracle: "DBOracle", symbol: str, radius: int = 2, resolved_only: bool = False) -> dict:
    """
    Nodes and edges within radius hops of symbol.
    Returns dict: nodes (set[str]), edges (list[tuple[str, str]]).
    resolved_only=True filters to annotation-resolved edges only (reduced noise, lower coverage).
    """
    from determined.agent.graph_utils import subgraph_around
    return subgraph_around(oracle, symbol, radius=radius, resolved_only=resolved_only)


def _auto_distill_and_store(conn, subject: str, content: str) -> None:
    """
    Compress `content` to one sentence and write it to semantic_summaries.distilled.
    Called synchronously after a fresh describe_file generation. Silently skips
    if llama-server is unreachable or content is a stub.
    """
    sentence = _distill_to_one_sentence(content, subject, conn=conn)
    if not sentence:
        return
    try:
        conn.execute(
            "UPDATE semantic_summaries SET distilled = ? WHERE subject = ?",
            (sentence, subject),
        )
        conn.commit()
    except Exception:
        pass


def _trigger_background_summary(db_path: str, file_path: str, project_root: str | None) -> None:
    """
    Fire a daemon thread to generate a semantic summary + distillation for
    `file_path`. The thread opens its own DB connection (check_same_thread=False
    is set on the main connection, but separate connections avoid write contention).
    Returns immediately; next symbol_brief call will find the cached result.
    """
    import threading, sqlite3 as _sq3
    from pathlib import Path

    def _work():
        try:
            conn = _sq3.connect(db_path, check_same_thread=False)
            # Read source
            p = Path(file_path)
            if not p.is_absolute() and project_root:
                p = Path(project_root) / file_path
            source_text = ""
            try:
                source_text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return
            if not source_text.strip():
                return
            from determined.intent.semantic_summary import get_or_generate_summary
            result = get_or_generate_summary(conn, file_path, "file", source_text)
            content = result.get("content", "")
            if content and not content.startswith("["):
                _auto_distill_and_store(conn, file_path, content)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()


def _source_skeleton(source_text: str, max_chars: int = 500) -> str:
    """Extract import lines and class/def signatures from source — no bodies."""
    lines = source_text.splitlines()
    out = []
    for line in lines:
        stripped = line.lstrip()
        if (stripped.startswith("import ") or stripped.startswith("from ") or
                stripped.startswith("class ") or stripped.startswith("def ") or
                stripped.startswith("async def ")):
            out.append(line)
    return "\n".join(out)[:max_chars]


def _distill_to_one_sentence(content: str, subject: str, conn=None) -> str | None:
    """
    Compress `content` into one sentence via llama-server.
    Returns None if llama-server is unreachable - callers must handle this explicitly
    so the failure is visible rather than silently swallowed (SOTS XIII).
    Does NOT use semantic cache — cache stored stale results from the old prompt.
    """
    from determined.agent.llm_client import generate as _llm_generate, LLM_TIMEOUT
    # Uses skeleton (signatures only) when content looks like source; otherwise raw content.
    body = _source_skeleton(content) if "\ndef " in content or "\nclass " in content else content[:500]
    prompt = f"# {subject}\n{body}\n\n# Purpose: "
    result = _llm_generate(prompt, timeout=LLM_TIMEOUT, max_tokens=60)
    if not result:
        return result
    # Extract first sentence only
    text = result.strip()
    for sep in (".", "!", "\n"):
        idx = text.find(sep)
        if 5 < idx < 160:
            return text[:idx + 1]
    return text[:160]


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

    # Prepend distilled preamble if available; trigger background generation if not
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
        else:
            _trigger_background_summary(assessor.oracle.db_path, file_path,
                                        assessor.oracle.get_project_root())

    return distilled_line + risk_line + "\n" + brief + design_frame


_CONSTRAINT_PATTERNS = (
    "must not", "never", "only", "forbidden", "must be", "shall not",
    "do not", "cannot", "prohibited", "required", "always",
)


def _check_import_layer_violations(conn, file_path: str) -> list[dict]:
    """
    Deterministic layer-import check against structured layer_rule artifacts.
    Each result: {from_layer, forbidden_import, line_number, to_layer, source}.
    Returns empty list with a hint if no layer_rules are defined yet.
    """
    import json

    if not file_path:
        return []

    # Determine this file's layers from all path segments (handles absolute paths)
    norm = file_path.replace("\\", "/")
    segments = [p for p in norm.split("/") if p and p != "." and p != ".."]
    if not segments:
        return []
    dir_segments = segments[:-1]  # exclude filename
    # Build all individual segments and dot-joined suffixes so "routes" matches
    # in both relative ("routes/foo.py") and absolute ("/home/user/proj/routes/foo.py")
    file_layer_prefixes = set(dir_segments)
    for i in range(len(dir_segments)):
        file_layer_prefixes.add(".".join(dir_segments[i:]))

    rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='layer_rule'"
    ).fetchall()

    if not rows:
        return [{"_hint": (
            "No layer rules defined. We've created LAYER_RULES.md in your project folder "
            "with examples to get you started. Open it, uncomment the rules that fit your "
            "project, and run ingest_design_docs to activate them. Layer rules tell Determined "
            "which parts of your code shouldn't be importing from other parts — catching "
            "architectural drift before it becomes a problem."
        )}]

    violations = []
    for (content,) in rows:
        try:
            rule = json.loads(content)
        except Exception:
            continue
        if rule.get("direction") != "forbidden":
            continue
        from_layer = rule.get("from_layer", "")
        to_layer = rule.get("to_layer", "")
        if not from_layer or not to_layer:
            continue
        # Check if this file belongs to from_layer
        if not any(lp == from_layer or lp.startswith(from_layer + ".") or lp.endswith("." + from_layer) for lp in file_layer_prefixes):
            continue
        # Check imports table for forbidden to_layer imports
        hits = conn.execute(
            "SELECT module, line_number FROM imports "
            "WHERE file_path = ? AND (module = ? OR module LIKE ?)",
            (file_path, to_layer, f"{to_layer}.%"),
        ).fetchall()
        for module, line_no in hits:
            violations.append({
                "from_layer": from_layer,
                "forbidden_import": module,
                "line_number": line_no,
                "to_layer": to_layer,
                "source": rule.get("source", ""),
            })

    return violations


def _check_design_violations_core(
    assessor: "Assessor", symbol: str, file_path: str
) -> list[dict]:
    """
    Pure analysis: collect symbol context, retrieve matching design norms
    (design_notes + SOTS tenets), return list[dict]: subject, content, score.
    Returns empty list on embedding failure (XIII). SOTS XI: pure, no mutations.
    """
    import re
    from determined.agent.evaluator import collect_symbol_context, retrieve_evidence_scored
    from determined.data.sots_loader import tenet_texts
    from determined.data.grasp_loader import principle_texts

    query = collect_symbol_context(assessor.oracle.conn, symbol)
    scored = retrieve_evidence_scored(
        query,
        assessor.oracle.conn,
        surfaces=["design_note"],
        top_n=5,
        threshold=0.30,
        extra_items=list(tenet_texts()) + list(principle_texts()),
    )
    _sots_re = re.compile(r"^\[([IVX]+)\]")
    _grasp_re = re.compile(r"^\[GRASP-(\d+)\]")
    results = []
    for score, content in scored:
        ms = _sots_re.match(content)
        mg = _grasp_re.match(content)
        if mg:
            subject = f"GRASP-{mg.group(1)}"
        elif ms:
            subject = f"SOTS {ms.group(1)}"
        else:
            subject = "design_note"
        results.append({"subject": subject, "content": content, "score": score})
    return results


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

    import_violations = _check_import_layer_violations(assessor.oracle.conn, file_path)
    hits = _check_design_violations_core(assessor, symbol, file_path)

    if not import_violations and not hits:
        from determined.data.sots_loader import load_tenets
        from determined.data.grasp_loader import load_principles
        return (
            f"No design violations detected for '{symbol}' "
            f"(checked {len(load_tenets())} SOTS tenets + {len(load_principles())} GRASP principles, "
            f"none matched above threshold)."
        )

    lines = [f"Design violation check for '{symbol}':"]

    # Hint returned when no layer_rules are defined yet
    hint_items = [v for v in import_violations if "_hint" in v]
    real_violations = [v for v in import_violations if "_hint" not in v]

    if hint_items:
        lines.append("")
        lines.append(f"  Note: {hint_items[0]['_hint']}")

    if real_violations:
        lines.append("")
        lines.append("  CONFIRMED layer-import violations (deterministic):")
        for v in real_violations:
            lines.append(
                f"    [VIOLATION] {v['from_layer']} imports `{v['forbidden_import']}` "
                f"(line {v['line_number']}) -- forbidden by rule in {v['source']}"
            )

    if hits:
        lines.append("")
        lines.append("  Potential violations (similarity match -- review manually):")
        for h in hits:
            label = h["subject"] or "general"
            lines.append(f"    [{label}] (score={h['score']:.2f})")
            lines.append(f"      {h['content'][:200]}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RM48: Design-to-code delta
# ---------------------------------------------------------------------------

_REQUIREMENT_KINDS = re.compile(
    r"^\[(REQUIREMENT|CONSTRAINT)\|", re.I
)
_MUST_RE_INLINE = re.compile(
    r"\b(must(?!\s+not)|shall(?!\s+not)|required\s+to|is\s+required)\b",
    re.IGNORECASE,
)


def _extract_design_requirements(conn) -> list[dict]:
    """
    Pull all design_note artifacts that represent requirements (must/shall/required to).
    Returns list[dict]: content, subject, source_file.
    Two paths:
      1. Content starts with [REQUIREMENT|...] prefix (new RM52+ format)
      2. Content body matches _MUST_RE_INLINE (pre-existing rows without prefix)
    """
    rows = conn.execute(
        "SELECT content, subject, source FROM knowledge_artifacts WHERE kind='design_note'"
    ).fetchall()
    results = []
    for content, subject, source in rows:
        if not content:
            continue
        if _REQUIREMENT_KINDS.match(content) or _MUST_RE_INLINE.search(content):
            results.append({"content": content, "subject": subject or "", "source": source or ""})
    return results


def _match_level_a(oracle, req_text: str, threshold: float = 0.45) -> list[dict]:
    """
    Level A: semantic embedding match against all symbols (name + docstring).
    Returns list of matching symbols with similarity score.
    """
    try:
        from determined.oracle.embedding_model import embed_text, cosine_similarity
    except Exception:
        return []
    try:
        req_vec = embed_text(req_text)
    except Exception:
        return []

    # Fetch all symbols with docstrings (or name only if no docstring)
    rows = oracle.conn.execute(
        "SELECT f.name, f.file_path, f.docstring FROM functions f"
    ).fetchall()
    class_rows = oracle.conn.execute(
        "SELECT c.name, c.file_path, c.docstring FROM classes c"
    ).fetchall()

    matches = []
    for name, file_path, doc in list(rows) + list(class_rows):
        text = f"{name} {doc or ''}".strip()
        try:
            vec = embed_text(text)
            score = cosine_similarity(req_vec, vec)
            if score >= threshold:
                matches.append({"name": name, "file_path": file_path or "", "score": round(score, 3)})
        except Exception:
            continue

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:3]


def _match_level_b(oracle, subject: str, req_text: str) -> list[str]:
    """
    Level B: file path substring match on keywords from subject + requirement text.
    Returns list of matching file paths.
    """
    # Extract keywords: words >= 4 chars from subject, skip stop words
    _stop = frozenset("must shall never only from that this with into when will are the and for its any all required".split())
    import re as _re
    words = set(_re.findall(r"\b[a-z][a-z_]{3,}\b", (subject + " " + req_text).lower()))
    keywords = [w for w in words if w not in _stop]
    if not keywords:
        return []

    rows = oracle.conn.execute("SELECT DISTINCT file_path FROM symbols").fetchall()
    file_paths = [r[0] for r in rows if r[0]]

    matched = []
    for fp in file_paths:
        fp_lower = fp.lower().replace("\\", "/")
        if any(kw in fp_lower for kw in keywords):
            matched.append(fp)
    return matched[:3]


def _match_level_c(oracle, subject: str, req_text: str) -> list[dict]:
    """
    Level C: import graph match. Look for files whose import chain connects
    keywords from the requirement to existing graph edges.
    Returns list of matching graph edges {caller, callee, file_path}.
    """
    import re as _re
    _stop = frozenset("must shall never only from that this with into when will are the and for its any all required".split())
    words = set(_re.findall(r"\b[a-z][a-z_]{3,}\b", (subject + " " + req_text).lower()))
    keywords = [w for w in words if w not in _stop]
    if not keywords:
        return []

    rows = oracle.conn.execute(
        "SELECT caller, callee FROM graph_edges LIMIT 2000"
    ).fetchall()

    matched = []
    seen = set()
    for caller, callee in rows:
        combined = f"{caller} {callee}".lower()
        if any(kw in combined for kw in keywords):
            key = (caller, callee)
            if key not in seen:
                seen.add(key)
                matched.append({"caller": caller, "callee": callee})
    return matched[:3]


def design_gaps(assessor: "Assessor", args: dict) -> str:
    """
    design_gaps(scope?, show_satisfied?, threshold?) - surface design requirements
    with no detectable implementation in the corpus.

    Arguments:
      scope           - optional keyword to filter requirements (filename or subject word)
      show_satisfied  - if true, also list satisfied requirements (default false)
      threshold       - Level A embedding similarity threshold (default 0.45)

    Reads kind='design_note' artifacts that contain requirement language (must/shall).
    For each, attempts Level A (embedding), Level B (file path), Level C (import graph).
    Reports GAP / PARTIAL / SATISFIED.
    """
    oracle = assessor.oracle
    scope = args.get("scope", "").strip().lower()
    show_satisfied = bool(args.get("show_satisfied", False))
    threshold = float(args.get("threshold", 0.45))

    reqs = _extract_design_requirements(oracle.conn)
    if not reqs:
        return (
            "No design notes found. Run ingest_design_docs first, or check that "
            "design_note artifacts exist in this corpus."
        )

    if scope:
        reqs = [r for r in reqs if scope in r["subject"].lower() or scope in r["content"].lower() or scope in r["source"].lower()]
        if not reqs:
            return f"No design requirements matching scope='{scope}' found."

    db_name = oracle.conn.execute("PRAGMA database_list").fetchone()
    db_label = db_name[2] if db_name else "unknown"

    gaps = []
    partials = []
    satisfied = []

    for req in reqs:
        content = req["content"]
        subject = req["subject"]
        source = req["source"]

        # Strip prefix bracket for cleaner display
        import re as _re
        display_text = _re.sub(r"^\[[^\]]+\]\s*", "", content).strip()

        # Determine modal kind for display
        if _re.search(r"\bmust\s+not\b|\bshall\s+not\b|\bnever\b", content, _re.I):
            modal = "MUST NOT"
        elif _re.search(r"\bmust\b", content, _re.I):
            modal = "MUST"
        elif _re.search(r"\bshall\b", content, _re.I):
            modal = "SHALL"
        else:
            modal = "REQUIRED"

        level_a = _match_level_a(oracle, display_text, threshold=threshold)
        level_b = _match_level_b(oracle, subject, display_text) if not level_a else []
        level_c = _match_level_c(oracle, subject, display_text) if not level_a and not level_b else []

        if level_a:
            best = level_a[0]
            satisfied.append({
                "modal": modal, "text": display_text, "source": source, "subject": subject,
                "match": f"{best['name']} in {best['file_path']} (similarity {best['score']:.2f})",
            })
        elif level_b or level_c:
            hint = ""
            if level_b:
                hint = f"File: {level_b[0]} exists. No function matching requirement found."
            elif level_c:
                edge = level_c[0]
                hint = f"Import edge: {edge['caller']} -> {edge['callee']} (keyword match only)."
            partials.append({
                "modal": modal, "text": display_text, "source": source, "subject": subject,
                "hint": hint,
            })
        else:
            # Suggest search terms based on keywords
            _stop = frozenset("must shall never only from that this with into when are and for its any all required".split())
            import re as _re2
            kws = [w for w in _re2.findall(r"\b[a-zA-Z][a-zA-Z_]{3,}\b", display_text)
                   if w.lower() not in _stop][:3]
            suggestion = " / ".join(f"search_symbols('{w}')" for w in kws) if kws else ""
            gaps.append({
                "modal": modal, "text": display_text, "source": source, "subject": subject,
                "suggestion": suggestion,
            })

    lines = [
        f"Design gaps for corpus: {db_label}",
        f"({len(reqs)} requirements checked from design docs)",
        "",
    ]

    if gaps:
        lines.append(f"GAPS ({len(gaps)} -- no implementation found):")
        for i, g in enumerate(gaps, 1):
            lines.append(f"  {i}. [{g['modal']}] \"{g['text'][:120]}\"")
            if g["source"]:
                lines.append(f"     Source: {g['source']} > {g['subject']}")
            if g["suggestion"]:
                lines.append(f"     Suggested search: {g['suggestion']}")
        lines.append("")

    if partials:
        lines.append(f"PARTIAL ({len(partials)} -- file/edge exists but no clear implementing function):")
        for i, p in enumerate(partials, 1):
            lines.append(f"  {i}. [{p['modal']}] \"{p['text'][:120]}\"")
            if p["source"]:
                lines.append(f"     Source: {p['source']} > {p['subject']}")
            lines.append(f"     {p['hint']}")
            lines.append(f"     Check: symbols_in_file('{p['source']}')")
        lines.append("")

    if show_satisfied and satisfied:
        lines.append(f"SATISFIED ({len(satisfied)}):")
        for i, s in enumerate(satisfied, 1):
            lines.append(f"  {i}. [{s['modal']}] \"{s['text'][:120]}\"")
            lines.append(f"     Matched: {s['match']}")
        lines.append("")
    elif satisfied:
        lines.append(f"SATISFIED: {len(satisfied)} requirements have detectable implementations (use show_satisfied=true to see them).")

    if not gaps and not partials:
        lines.append("No unimplemented design requirements detected.")

    return "\n".join(lines)


def data_flow_edges(assessor: "Assessor", args: dict) -> str:
    """
    data_flow_edges(symbol, direction?) - show data_flow edges for a symbol.

    direction: 'out' (default) = what functions consume this symbol's return value
               'in'            = what functions this symbol consumes return values from
               'both'          = both directions

    Only data_flow edges (fn_b calls fn_a and uses its return value as an argument)
    are shown. Use bfs_callees/bfs_callers for full control-flow traversal.
    """
    oracle = assessor.oracle
    conn = oracle.conn
    symbol = args.get("symbol", "").strip()
    direction = args.get("direction", "out")

    if not symbol:
        return "trace_data_flow requires a symbol argument."

    lines = [f"Data flow edges for: {symbol}", ""]

    if direction in ("in", "both"):
        # what does this symbol consume? (symbol is fn_b, find fn_a's it calls)
        rows = conn.execute(
            "SELECT target_id FROM graph_edges WHERE source_id = ? AND edge_type = 'data_flow'",
            (symbol,),
        ).fetchall()
        if rows:
            lines.append(f"CONSUMES return values from ({len(rows)}):")
            for (tgt,) in rows:
                lines.append(f"  <- {tgt}")
        else:
            lines.append("CONSUMES: none detected")
        lines.append("")

    if direction in ("out", "both"):
        # what consumes this symbol's return value? (symbol is fn_a, find fn_b's that call it)
        rows = conn.execute(
            "SELECT source_id FROM graph_edges WHERE target_id = ? AND edge_type = 'data_flow'",
            (symbol,),
        ).fetchall()
        if rows:
            lines.append(f"RETURN VALUE consumed by ({len(rows)}):")
            for (src,) in rows:
                lines.append(f"  -> {src}")
        else:
            lines.append("RETURN VALUE: not consumed as a direct argument in any detected call")
        lines.append("")

    total = conn.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE edge_type = 'data_flow'"
    ).fetchone()[0]
    lines.append(f"(Total data_flow edges in corpus: {total})")

    return "\n".join(lines)


def trace_http_chain(assessor: "Assessor", args: dict) -> str:
    """
    trace_http_chain(url) - show the full browser-to-business-logic chain for a URL.

    Matches the URL against Flask route handlers (http_fetch and decorator edges),
    then shows:
      - HTMX elements and JS functions that call this route (http_fetch edges)
      - DOM elements that trigger those JS functions (js_event_binding edges)
      - Downstream callees of the Flask handler (static edges, depth=2)

    url: URL pattern to look up (e.g. '/api/party/create', '/character/<id>/basic')
    """
    oracle = assessor.oracle
    conn = oracle.conn

    url = args.get("url", "").strip()
    if not url:
        return "trace_http_chain requires a url argument."

    from determined.ingestion.dynamic_edges import _normalize_url, _url_matches
    import json as _json

    # Primary: use http_route column if it was populated during ingest (TODO-1 fix)
    fn_cols = {row[1] for row in conn.execute("PRAGMA table_info(functions)").fetchall()}
    matched_handlers: list[str] = []

    if "http_route" in fn_cols:
        route_rows = conn.execute(
            "SELECT name, http_route FROM functions WHERE http_route IS NOT NULL"
        ).fetchall()
        for name, route_url in route_rows:
            if _url_matches(url, route_url):
                matched_handlers.append(name)

    # Fallback for corpora ingested before http_route column existed:
    # parse route URL out of decorators_json string representation.
    # Real decorators_json stores ast.unparse output, e.g. "app.route('/api/foo')"
    # which contains quoted URL substrings the regex can extract.
    if not matched_handlers:
        import re as _re
        handler_rows = conn.execute(
            "SELECT name, decorators_json FROM functions WHERE decorators_json IS NOT NULL"
        ).fetchall()
        for name, decs_json in handler_rows:
            try:
                decs = _json.loads(decs_json or "[]")
            except Exception:
                continue
            for dec in (decs if isinstance(decs, list) else []):
                dec_str = dec if isinstance(dec, str) else str(dec)
                if "route" in dec_str:
                    m = _re.search(r'["\']([^"\']+)["\']', dec_str)
                    if m and _url_matches(url, m.group(1)):
                        matched_handlers.append(name)
                        break

    # Last-resort fallback: for corpora with http_fetch edges but no route metadata,
    # surface all http_fetch edge targets so the chain is still partially visible.
    if not matched_handlers:
        fetch_rows = conn.execute(
            "SELECT DISTINCT target_id FROM graph_edges WHERE edge_type = 'http_fetch'"
        ).fetchall()
        matched_handlers = [r[0] for r in fetch_rows if r[0] not in ("__htmx__", "__http_client__")]

    lines = [f"HTTP chain for: {url}", ""]

    if not matched_handlers:
        lines.append("No Flask handler found for this URL.")
        lines.append("(Tip: re-ingest the corpus after RM38 to populate http_fetch edges)")
        return "\n".join(lines)

    for handler in matched_handlers:
        lines.append(f"Flask handler: {handler}")
        lines.append("")

        # Who calls this handler from the browser?
        callers = conn.execute(
            "SELECT source_id, edge_type FROM graph_edges "
            "WHERE target_id = ? AND edge_type IN ('http_fetch', 'decorator')",
            (handler,),
        ).fetchall()

        htmx_callers = [r[0] for r in callers if r[1] == 'http_fetch' and r[0] == '__htmx__']
        js_fn_callers = [r[0] for r in callers if r[1] == 'http_fetch' and r[0] not in ('__htmx__', '__http_client__')]

        if htmx_callers:
            lines.append(f"  HTMX: {len(htmx_callers)} HTMX element(s) call this route directly")

        if js_fn_callers:
            lines.append(f"  JS fetch from: {', '.join(js_fn_callers)}")
            # For each JS function, find what DOM element triggers it
            for js_fn in js_fn_callers:
                dom_callers = conn.execute(
                    "SELECT source_id FROM graph_edges "
                    "WHERE target_id = ? AND edge_type = 'js_event_binding'",
                    (js_fn,),
                ).fetchall()
                if dom_callers:
                    triggers = ', '.join(r[0] for r in dom_callers)
                    lines.append(f"    triggered by: {triggers}")

        if not callers:
            lines.append("  (No browser callers detected -- re-ingest to populate http_fetch edges)")

        lines.append("")

        # Downstream: what does the Flask handler call? (depth 2)
        lines.append("  Downstream calls:")
        direct = conn.execute(
            "SELECT DISTINCT callee FROM graph_edges "
            "WHERE caller = ? AND edge_type = 'static' LIMIT 10",
            (handler,),
        ).fetchall()
        if direct:
            for (callee,) in direct:
                lines.append(f"    -> {callee}")
                # One more level
                deeper = conn.execute(
                    "SELECT DISTINCT callee FROM graph_edges "
                    "WHERE caller = ? AND edge_type = 'static' LIMIT 5",
                    (callee,),
                ).fetchall()
                for (d,) in deeper:
                    lines.append(f"       -> {d}")
        else:
            lines.append("    (none found)")
        lines.append("")

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
    Includes chain depth: how many stub-to-stub hops below this stub before reaching
    a non-stub or dead end. depth=0 means a chain-tail (implement first).
    """
    limit = int(args.get("limit", 20))
    conn = oracle.conn

    rows = conn.execute(
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

    # Compute chain depth for each stub via recursive CTE (max depth 20 to avoid cycles)
    def _chain_depth(stub_name: str) -> int:
        try:
            result = conn.execute(
                """
                WITH RECURSIVE chain(node, depth) AS (
                    SELECT ?, 0
                    UNION ALL
                    SELECT ge.callee, chain.depth + 1
                    FROM chain
                    JOIN graph_edges ge ON ge.caller = chain.node
                    JOIN functions f ON (f.name = ge.callee OR ge.callee LIKE '%.' || f.name)
                    WHERE f.is_stub = 1 AND chain.depth < 20
                )
                SELECT MAX(depth) FROM chain
                """,
                (stub_name,),
            ).fetchone()
            return result[0] or 0
        except Exception:
            return 0

    lines = [f"Stub functions ({len(rows)} shown, ranked by caller count):"]
    for r in rows:
        fp = (r[1] or "").replace("\\", "/").split("/")[-1]
        callers = r[2] or 0
        depth = _chain_depth(r[0])
        depth_tag = f"depth={depth}" if depth > 0 else "tail"
        lines.append(f"  {r[0]} in {fp}  ({callers} callers, {depth_tag})")
    return "\n".join(lines)


def find_abc_gaps(oracle: "DBOracle", args: dict) -> str:
    """
    find_abc_gaps() - find abstract-interface methods (defined on ABC subclasses as stubs)
    that have no concrete non-stub override anywhere in the corpus.
    These are the unimplemented interface frontier — different from direct caller->stub edges
    because nothing calls them yet; they block any subclass from being instantiated.
    """
    import json as _json

    conn = oracle.conn

    # 1. Collect all classes that inherit from ABC (or Abstract bases)
    abc_classes = conn.execute(
        "SELECT name, methods_json, file_path FROM classes "
        "WHERE base_classes_json LIKE '%ABC%' OR base_classes_json LIKE '%Abstract%'"
    ).fetchall()

    if not abc_classes:
        return "No ABC/Abstract base classes found in corpus."

    # 2. For each ABC class, collect abstract methods (via @abstractmethod decorator)
    abstract_stubs: list[tuple[str, str, str]] = []  # (method_name, class_name, file_path)
    for cls_name, methods_json, file_path in abc_classes:
        try:
            methods = _json.loads(methods_json or "[]")
        except Exception:
            continue
        for method in methods:
            row = conn.execute(
                "SELECT decorators_json FROM functions WHERE name = ? AND file_path = ? LIMIT 1",
                (method, file_path),
            ).fetchone()
            if row:
                try:
                    decs = _json.loads(row[0] or "[]")
                except Exception:
                    decs = []
                if any("abstractmethod" in d for d in decs):
                    abstract_stubs.append((method, cls_name, file_path))

    if not abstract_stubs:
        return "No abstract methods found on ABC classes."

    # 3. Find concrete subclasses of each ABC class
    #    and check which are missing overrides per-method.
    from collections import defaultdict

    # Map abc class name -> set of abstract method names
    abc_method_map: dict[str, set] = defaultdict(set)
    for method, cls_name, _ in abstract_stubs:
        abc_method_map[cls_name].add(method)

    # Find all concrete subclasses (classes whose base_classes_json mentions an ABC class)
    abc_names = list(abc_method_map.keys())
    concrete_gaps: list[tuple[str, str, list[str]]] = []  # (subclass, abc_base, missing_methods)

    all_classes = conn.execute(
        "SELECT name, base_classes_json, file_path FROM classes"
    ).fetchall()

    for sub_name, bases_json, sub_file in all_classes:
        try:
            bases = _json.loads(bases_json or "[]")
        except Exception:
            bases = []
        # Also fetch this subclass's own method list
        sub_methods_row = conn.execute(
            "SELECT methods_json FROM classes WHERE name = ? AND file_path = ? LIMIT 1",
            (sub_name, sub_file),
        ).fetchone()
        try:
            sub_methods = set(_json.loads(sub_methods_row[0] or "[]")) if sub_methods_row else set()
        except Exception:
            sub_methods = set()

        for abc_name in abc_names:
            if abc_name not in bases:
                continue
            # Check each abstract method against this subclass's own method list
            missing = []
            for method in sorted(abc_method_map[abc_name]):
                if method not in sub_methods:
                    missing.append(method)
            if missing:
                concrete_gaps.append((sub_name, abc_name, missing))

    if not concrete_gaps:
        return "All ABC stub methods have at least one non-stub override in the corpus."

    lines = [
        f"ABC interface gaps ({len(concrete_gaps)} concrete subclass(es) with missing overrides):",
        "",
    ]
    for sub_name, abc_name, missing in sorted(concrete_gaps):
        lines.append(f"  {sub_name}  (inherits {abc_name})")
        for m in missing:
            lines.append(f"    {m}  [not overridden]")
    return "\n".join(lines)


_ENTRY_POINT_PATH_HINTS = {
    "route", "routes", "view", "views", "handler", "handlers",
    "endpoint", "endpoints", "cli", "commands", "command",
    "webhook", "webhooks", "task", "tasks", "signal", "signals",
    "middleware", "main",
}
_ENTRY_POINT_NAME_PREFIXES = ("handle_", "on_", "route_", "cmd_", "do_")


def _is_entry_point_hint(file_path: str, fn_name: str) -> bool:
    """Heuristic: is this function likely an externally-triggered entry point?"""
    parts = set((file_path or "").replace("\\", "/").lower().replace(".", "/").split("/"))
    if parts & _ENTRY_POINT_PATH_HINTS:
        return True
    lname = fn_name.lower()
    if any(lname.startswith(p) for p in _ENTRY_POINT_NAME_PREFIXES):
        return True
    return False


_STRUCTURAL_DECORATORS = {"property", "staticmethod", "classmethod"}


def _has_framework_decorator(decorators_json) -> bool:
    if not decorators_json:
        return False
    import json as _json
    try:
        decs = _json.loads(decorators_json)
    except Exception:
        return False
    return any(d.split("(")[0].split(".")[-1] not in _STRUCTURAL_DECORATORS for d in decs)


def _get_abc_gap_set(conn) -> set:
    """Return set of abstract method names that have at least one concrete subclass
    missing an override. Uses per-subclass methods_json check, not global name search."""
    import json as _json

    abc_classes = conn.execute(
        "SELECT name, methods_json, file_path FROM classes "
        "WHERE base_classes_json LIKE '%ABC%' OR base_classes_json LIKE '%Abstract%'"
    ).fetchall()

    # Build map of abc_name -> set of abstract method names (via @abstractmethod decorator)
    abc_method_map: dict[str, set] = {}
    for cls_name, methods_json, file_path in abc_classes:
        try:
            methods = _json.loads(methods_json or "[]")
        except Exception:
            continue
        abstract = set()
        for method in methods:
            row = conn.execute(
                "SELECT decorators_json FROM functions WHERE name = ? AND file_path = ? LIMIT 1",
                (method, file_path),
            ).fetchone()
            if row:
                try:
                    decs = _json.loads(row[0] or "[]")
                except Exception:
                    decs = []
                if any("abstractmethod" in d for d in decs):
                    abstract.add(method)
        if abstract:
            abc_method_map[cls_name] = abstract

    if not abc_method_map:
        return set()

    # Find concrete subclasses and check per-subclass for missing overrides
    gaps: set[str] = set()
    all_classes = conn.execute("SELECT name, base_classes_json, methods_json, file_path FROM classes").fetchall()
    for sub_name, bases_json, sub_methods_json, sub_file in all_classes:
        try:
            bases = _json.loads(bases_json or "[]")
            sub_methods = set(_json.loads(sub_methods_json or "[]"))
        except Exception:
            continue
        for abc_name, abstract_methods in abc_method_map.items():
            if abc_name not in bases:
                continue
            for method in abstract_methods:
                if method not in sub_methods:
                    gaps.add(method)
    return gaps


def _get_chain_positions(conn) -> tuple[set, set, set]:
    """
    Classify each stub into chain-tail, chain-middle, or chain-head.

    chain-tail   — stub with stub callers but NO stub callees (implement first)
    chain-middle — stub with stub callers AND stub callees (blocked above and below)
    chain-head   — stub with functional callers AND stub callees (bridges real code into chain)

    Returns (tail_set, middle_set, head_set).  A stub may appear in only one set.
    """
    # Stubs that have at least one stub callee
    has_stub_callee = {r[0] for r in conn.execute(
        """
        SELECT DISTINCT f.name FROM functions f
        JOIN graph_edges ge ON ge.caller = f.name
        JOIN functions callee_fn ON (callee_fn.name = ge.callee OR ge.callee LIKE '%.' || callee_fn.name)
        WHERE f.is_stub = 1 AND callee_fn.is_stub = 1
        """
    ).fetchall()}

    # Stubs that have at least one functional (non-stub) caller
    has_functional_caller = {r[0] for r in conn.execute(
        """
        SELECT DISTINCT f.name FROM functions f
        JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        JOIN functions caller_fn ON caller_fn.name = ge.caller
        WHERE f.is_stub = 1 AND caller_fn.is_stub = 0
        """
    ).fetchall()}

    # Stubs that have at least one stub caller
    has_stub_caller = {r[0] for r in conn.execute(
        """
        SELECT DISTINCT f.name FROM functions f
        JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        JOIN functions caller_fn ON caller_fn.name = ge.caller
        WHERE f.is_stub = 1 AND caller_fn.is_stub = 1
        """
    ).fetchall()}

    head_set   = has_functional_caller & has_stub_callee
    # middle: stub callers, stub callees, but no functional callers
    middle_set = (has_stub_caller & has_stub_callee) - has_functional_caller
    # tail: stub callers, no stub callees (leaf of the chain)
    tail_set   = has_stub_caller - has_stub_callee

    return tail_set, middle_set, head_set


def detect_topology(oracle: "DBOracle", args: dict) -> str:
    """
    detect_topology() - inventory the incompleteness shapes present in the corpus.
    Returns counts for each known topology shape. Chain is broken into three
    positions (head/middle/tail) and entry-point stubs are separated from
    truly-disconnected stubs. Use before frontier_priority or find_orphaned_impls
    to understand which shapes dominate this corpus.
    """
    conn = oracle.conn

    # Shape 1: Direct-call — stubs with at least one functional (non-stub) caller
    direct_call = conn.execute(
        """
        SELECT COUNT(DISTINCT f.name)
        FROM functions f
        JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        JOIN functions caller_fn ON caller_fn.name = ge.caller
        WHERE f.is_stub = 1 AND caller_fn.is_stub = 0
        """
    ).fetchone()[0]

    # Shape 2: ABC-interface gaps
    abc_gap_set = _get_abc_gap_set(conn)
    abc_gap_count = len(abc_gap_set)

    # Shape 3: Chain positions
    tail_set, middle_set, head_set = _get_chain_positions(conn)
    chain_tail   = len(tail_set)
    chain_middle = len(middle_set)
    chain_head   = len(head_set)

    # Shape 4: Orphaned-impl (exclude framework-decorated entry points)
    total_non_stub = conn.execute("SELECT COUNT(*) FROM functions WHERE is_stub = 0").fetchone()[0]
    orphaned_rows = conn.execute(
        """
        SELECT DISTINCT f.name, f.file_path, f.decorators_json
        FROM functions f
        WHERE f.is_stub = 0
          AND NOT EXISTS (
            SELECT 1 FROM graph_edges ge
            JOIN functions caller_fn ON caller_fn.name = ge.caller
            WHERE (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
              AND caller_fn.is_stub = 0
          )
        """
    ).fetchall()
    orphaned_impl = sum(1 for _, _, dj in orphaned_rows if not _has_framework_decorator(dj))

    # Shape 5a: Entry-point stubs — disconnected by graph but likely externally triggered
    all_disconnected = conn.execute(
        """
        SELECT f.name, f.file_path FROM functions f
        WHERE f.is_stub = 1
          AND NOT EXISTS (SELECT 1 FROM graph_edges ge WHERE ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
          AND NOT EXISTS (SELECT 1 FROM graph_edges ge WHERE ge.caller = f.name)
        """
    ).fetchall()
    entry_point_stubs = sum(1 for name, fp in all_disconnected if _is_entry_point_hint(fp, name))
    disconnected = len(all_disconnected) - entry_point_stubs

    total_stubs = conn.execute("SELECT COUNT(*) FROM functions WHERE is_stub = 1").fetchone()[0]

    lines = [
        "CORPUS TOPOLOGY",
        f"  Total stubs: {total_stubs}  |  Total implemented: {total_non_stub}",
        "",
        "  Shape                  Count  Description",
        "  ──────────────────────────────────────────────────────────────",
        f"  Direct-call            {direct_call:>5}  stubs called by functional code",
        f"  ABC-interface          {abc_gap_count:>5}  abstract methods with no concrete override",
        f"  Chain-head             {chain_head:>5}  stubs: functional callers + stub callees [bridge]",
        f"  Chain-middle           {chain_middle:>5}  stubs: stub callers + stub callees [blocked]",
        f"  Chain-tail             {chain_tail:>5}  stubs: stub callers only [implement first]",
        f"  Orphaned-impl          {orphaned_impl:>5}  implementations with no functional callers",
        f"  Entry-point            {entry_point_stubs:>5}  stubs in route/handler/cli files [external trigger]",
        f"  Disconnected           {disconnected:>5}  stubs with no graph connections",
        "",
        "  Action queues:",
        f"    Implement now:  chain-tail ({chain_tail}) > direct-call ({direct_call}) > abc-interface ({abc_gap_count}) > chain-head ({chain_head})",
        f"    Write callers:  orphaned-impl ({orphaned_impl})",
        f"    Decide:         disconnected ({disconnected}) | entry-point ({entry_point_stubs})",
    ]
    return "\n".join(lines)


def frontier_coverage(oracle: "DBOracle", args: dict) -> str:
    """
    frontier_coverage() - what fraction of the implemented corpus is blocked behind stubs?

    A function is "stub-gated" if every path that could call it passes through at least
    one stub. Computed as: implemented functions whose only callers are stubs (direct edge
    only — one-hop approximation, fast and conservative).

    Returns: total implemented, stub-gated count, coverage %, and per-shape context.
    """
    conn = oracle.conn

    total_impl = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE is_stub = 0"
    ).fetchone()[0]

    if total_impl == 0:
        return "No implemented functions in corpus."

    total_stubs = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE is_stub = 1"
    ).fetchone()[0]

    # Implemented functions that have at least one caller that is a stub
    has_stub_caller = conn.execute(
        """
        SELECT COUNT(DISTINCT f.name)
        FROM functions f
        JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        JOIN functions caller_fn ON caller_fn.name = ge.caller
        WHERE f.is_stub = 0 AND caller_fn.is_stub = 1
        """
    ).fetchone()[0]

    # Implemented functions that have at least one caller that is also implemented
    has_impl_caller = conn.execute(
        """
        SELECT COUNT(DISTINCT f.name)
        FROM functions f
        JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        JOIN functions caller_fn ON caller_fn.name = ge.caller
        WHERE f.is_stub = 0 AND caller_fn.is_stub = 0
        """
    ).fetchone()[0]

    # Stub-gated: has a stub caller but no implemented caller (one-hop)
    stub_gated = conn.execute(
        """
        SELECT COUNT(DISTINCT f.name)
        FROM functions f
        WHERE f.is_stub = 0
          AND EXISTS (
            SELECT 1 FROM graph_edges ge
            JOIN functions caller_fn ON caller_fn.name = ge.caller
            WHERE (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
              AND caller_fn.is_stub = 1
          )
          AND NOT EXISTS (
            SELECT 1 FROM graph_edges ge
            JOIN functions caller_fn ON caller_fn.name = ge.caller
            WHERE (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
              AND caller_fn.is_stub = 0
          )
        """
    ).fetchone()[0]

    pct = (stub_gated / total_impl * 100) if total_impl else 0.0

    # Unreachable implemented: no callers at all (orphaned-impl overlap)
    no_callers = conn.execute(
        """
        SELECT COUNT(DISTINCT f.name)
        FROM functions f
        WHERE f.is_stub = 0
          AND NOT EXISTS (
            SELECT 1 FROM graph_edges ge
            WHERE ge.callee = f.name OR ge.callee LIKE '%.' || f.name
          )
        """
    ).fetchone()[0]

    lines = [
        "FRONTIER COVERAGE",
        f"  Implemented functions : {total_impl}",
        f"  Stubs in corpus       : {total_stubs}",
        "",
        f"  Stub-gated (1-hop)    : {stub_gated}  ({pct:.1f}% of implemented corpus)",
        f"  Has impl caller       : {has_impl_caller}  (reachable through functional code)",
        f"  Has stub caller only  : {stub_gated}  (blocked until stub(s) above are implemented)",
        f"  No callers at all     : {no_callers}  (orphaned — see find_orphaned_impls)",
        "",
    ]

    if pct >= 40:
        lines.append("  Signal: HIGH stub pressure — large fraction of implemented work is blocked.")
    elif pct >= 20:
        lines.append("  Signal: MODERATE stub pressure — meaningful implemented code waiting on stubs.")
    else:
        lines.append("  Signal: LOW stub pressure — most implemented code is reachable.")

    lines.append("  Note: 1-hop approximation. Multi-hop chains reported by detect_topology.")
    return "\n".join(lines)


def _dominant_shape(direct: int, abc: int, chain: int, disconnected: int) -> str:
    shapes = [("direct-call", direct), ("ABC-interface", abc), ("chain", chain), ("disconnected", disconnected)]
    shapes.sort(key=lambda x: x[1], reverse=True)
    top = shapes[0]
    if top[1] == 0:
        return "none (no stubs detected)"
    second = shapes[1]
    if second[1] > 0 and second[1] >= top[1] * 0.5:
        return f"{top[0]} + {second[0]}"
    return top[0]


def frontier_priority(oracle: "DBOracle", args: dict) -> str:
    """
    frontier_priority(limit?) - rank stubs by composite frontier score.

    Score = functional caller count + chain-position bonus + ABC-interface bonus.
    Chain bonuses:
      tail   = +5  (leaf node: implement to start unblocking the chain upward)
      middle = +2  (blocked above and below; implement after tails)
      head   = +1  (already captured in caller count; bonus is marginal)
    ABC bonus = +3 (gates subclassing, not just a call)

    Orphaned-impls are explicitly excluded — they need callers written, not
    implementations; use find_orphaned_impls() for those.
    """
    limit = int(args.get("limit", 20))
    conn = oracle.conn

    # All stubs with at least one functional caller (direct-call shape only)
    stubs = conn.execute(
        """
        SELECT f.name, f.file_path, COUNT(DISTINCT ge.caller) AS callers
        FROM functions f
        JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        JOIN functions caller_fn ON caller_fn.name = ge.caller AND caller_fn.is_stub = 0
        WHERE f.is_stub = 1
        GROUP BY f.name, f.file_path
        """,
    ).fetchall()

    # Chain-tail stubs (no functional callers but reachable via stub chain from functional code)
    # Include them even though they have 0 direct functional callers — they're highest priority
    tail_set, middle_set, head_set = _get_chain_positions(conn)

    # Collect all stubs in any queue-A shape
    stub_map: dict[str, tuple[str, int]] = {}  # name -> (file_path, caller_count)
    for name, fp, callers in stubs:
        stub_map[name] = (fp, callers)

    # Add chain-tail/middle stubs even if they have no direct functional callers
    for name_set in (tail_set, middle_set):
        for name in name_set:
            if name not in stub_map:
                row = conn.execute(
                    "SELECT file_path FROM functions WHERE name = ? AND is_stub = 1 LIMIT 1", (name,)
                ).fetchone()
                if row:
                    stub_map[name] = (row[0], 0)

    abc_gap_set = _get_abc_gap_set(conn)

    scored = []
    for name, (file_path, callers) in stub_map.items():
        shapes = []
        bonus = 0
        if callers > 0:
            shapes.append("direct-call")
        if name in tail_set:
            shapes.append("chain-tail")
            bonus += 5
        elif name in middle_set:
            shapes.append("chain-mid")
            bonus += 2
        elif name in head_set:
            shapes.append("chain-head")
            bonus += 1
        if name in abc_gap_set:
            shapes.append("abc")
            bonus += 3
        score = callers + bonus
        scored.append((score, callers, name, file_path, shapes))

    if not scored:
        return "No implementable stubs found. Use list_stubs() to see all stubs."

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    scored = scored[:limit]

    lines = [
        "Frontier priority  (score = caller count + bonuses: chain-tail=+5, chain-mid=+2, chain-head=+1, abc=+3)",
        "Orphaned-impls excluded — use find_orphaned_impls() for those.",
        "",
        "  Score  Callers  Shapes           Name",
        "  ──────────────────────────────────────────────────────────────",
    ]
    for score, callers, name, file_path, shapes in scored:
        fp = (file_path or "").replace("\\", "/").split("/")[-1]
        shape_str = "+".join(shapes) if shapes else "chain-only"
        lines.append(f"  {score:>5}  {callers:>7}  {shape_str:<16}  {name}  ({fp})")
    return "\n".join(lines)


def implementation_order(oracle: "DBOracle", args: dict) -> str:
    """
    implementation_order(scope?) - topological sort of all incomplete symbols (stubs +
    ABC gaps) into a dependency-ordered implementation plan.

    Returns a numbered wave list: symbols in wave 1 have no incomplete callees (implement
    first); symbols in later waves depend only on earlier waves. Cyclic groups are
    reported as a set to implement together.

    Args:
        scope: optional file path prefix to restrict output (e.g. "movement.py")
    """
    from collections import deque

    conn = oracle.conn
    scope = args.get("scope", "")

    # Step 1: collect incomplete set S (stubs + ABC gap methods)
    stub_rows = conn.execute(
        "SELECT name, file_path, line_number FROM functions WHERE is_stub = 1"
    ).fetchall()

    abc_names = _get_abc_gap_set(conn)

    # Build S: name -> (file_path, line_number)
    incomplete: dict[str, tuple] = {}
    for name, fp, ln in stub_rows:
        incomplete[name] = (fp or "", ln or 0)

    # Add ABC gap methods (may not have their own stub row; look up best location)
    for name in abc_names:
        if name not in incomplete:
            row = conn.execute(
                "SELECT file_path, line_number FROM functions WHERE name = ? LIMIT 1",
                (name,),
            ).fetchone()
            incomplete[name] = (row[0] or "", row[1] or 0) if row else ("", 0)

    if not incomplete:
        return "No incomplete symbols found (no stubs, no ABC gaps)."

    # Apply scope filter
    if scope:
        incomplete = {n: v for n, v in incomplete.items() if scope in v[0]}
        if not incomplete:
            return f"No incomplete symbols found matching scope '{scope}'."

    S = set(incomplete.keys())

    # Step 2: build restricted call graph (S -> S edges only)
    # Try resolved=1 first; fall back to all edges
    resolved_rows = conn.execute(
        "SELECT caller, callee FROM graph_edges WHERE resolved = 1 AND caller IN ({}) AND callee IN ({})".format(
            ",".join("?" * len(S)), ",".join("?" * len(S))
        ),
        list(S) + list(S),
    ).fetchall() if S else []

    if resolved_rows:
        edges = resolved_rows
    else:
        placeholders = ",".join("?" * len(S))
        edges = conn.execute(
            f"SELECT caller, callee FROM graph_edges WHERE caller IN ({placeholders}) AND callee IN ({placeholders})",
            list(S) + list(S),
        ).fetchall() if S else []

    # Adjacency: caller -> set of callees in S (caller must implement after callee)
    callees_of: dict[str, set] = {n: set() for n in S}
    callers_of: dict[str, set] = {n: set() for n in S}
    for caller, callee in edges:
        if caller in S and callee in S and caller != callee:
            callees_of[caller].add(callee)
            callers_of[callee].add(caller)

    # Step 3: Kahn's algorithm
    in_degree = {n: len(callees_of[n]) for n in S}  # "must implement X first" count
    queue = deque(n for n in S if in_degree[n] == 0)
    waves: list[list[str]] = []
    current_wave: list[str] = []
    processed = set()
    order_wave: dict[str, int] = {}

    # Process wave by wave
    remaining = set(S)
    wave_num = 0
    while remaining:
        ready = [n for n in remaining if in_degree[n] == 0]
        if not ready:
            # Cycle: report remaining as a group
            cycle_group = sorted(remaining)
            waves.append(cycle_group)
            for n in cycle_group:
                order_wave[n] = wave_num
            break
        wave_num += 1
        waves.append(sorted(ready))
        for n in ready:
            order_wave[n] = wave_num
            remaining.remove(n)
            for caller in callers_of[n]:
                if caller in remaining:
                    in_degree[caller] -= 1

    # Step 4: format output
    lines = [
        "IMPLEMENTATION ORDER",
        f"  {len(S)} incomplete symbols",
        f"  {wave_num} wave(s) — implement wave 1 first",
        "",
    ]

    item_num = 0
    for w_idx, wave in enumerate(waves):
        is_cycle = w_idx == len(waves) - 1 and any(n in callees_of and callees_of[n] & set(wave) for n in wave)
        if is_cycle and len(wave) > 1:
            lines.append(f"  [CYCLE — implement together]")
            for name in wave:
                item_num += 1
                fp, ln = incomplete[name]
                short = (fp or "").replace("\\", "/").split("/")[-1]
                deps = sorted(callees_of[name] & set(wave))
                dep_str = f"  mutually depends on: {', '.join(deps)}" if deps else ""
                lines.append(f"  {item_num:>3}. {name}  ({short}:{ln}){dep_str}")
        else:
            wave_label = f"Wave {w_idx + 1}"
            lines.append(f"  {wave_label}")
            for name in wave:
                item_num += 1
                fp, ln = incomplete[name]
                short = (fp or "").replace("\\", "/").split("/")[-1]
                deps = sorted(callees_of[name])
                if deps:
                    dep_str = f"\n       After: {', '.join(deps)}"
                else:
                    dep_str = ""
                lines.append(f"  {item_num:>3}. {name}  ({short}:{ln}){dep_str}")
        lines.append("")

    return "\n".join(lines)


def find_orphaned_impls(oracle: "DBOracle", args: dict) -> str:
    """
    find_orphaned_impls(limit?) - find implemented functions that are never called
    by other implemented functions.

    Labels each result:
      ready-but-blocked — no callers, same file has stubs (implementation waiting for its stub to be wired)
      anticipatory — no callers, no stubs nearby (written ahead of its interface)
      possibly-stranded — has stub callers only (was connected, stubs were never implemented)

    ready-but-blocked is the highest-signal case: the implementation exists and works,
    but the stub that should call it has not been wired up yet.
    """
    limit = int(args.get("limit", 30))
    conn = oracle.conn

    raw_rows = conn.execute(
        """
        SELECT f.name, f.file_path, f.line_number,
               COUNT(ge.caller) AS total_callers,
               SUM(CASE WHEN caller_fn.is_stub = 1 THEN 1 ELSE 0 END) AS stub_callers,
               SUM(CASE WHEN caller_fn.name IS NULL THEN 1 ELSE 0 END) AS missing_callers,
               f.decorators_json
        FROM functions f
        LEFT JOIN graph_edges ge ON (ge.callee = f.name OR ge.callee LIKE '%.' || f.name)
        LEFT JOIN functions caller_fn ON caller_fn.name = ge.caller
        WHERE f.is_stub = 0
        GROUP BY f.name, f.file_path, f.line_number
        HAVING total_callers = 0
            OR (stub_callers + missing_callers) = total_callers
        ORDER BY f.file_path, f.line_number
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    rows = [r for r in raw_rows if not _has_framework_decorator(r[6])]

    if not rows:
        return "No orphaned implementations found."

    files_with_stubs = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT file_path FROM functions WHERE is_stub = 1"
        ).fetchall()
    }

    # Build name→files map for duplicate detection
    name_files: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT name, file_path FROM functions WHERE is_stub = 0"
    ).fetchall():
        n, fp = row
        fp_short = (fp or "").replace("\\", "/").split("/")[-1]
        name_files.setdefault(n, []).append(fp_short)

    lines = [
        f"Orphaned implementations ({len(rows)} shown)",
        "  ready-but-blocked = no callers, same file has stubs (wire the stub to call this)",
        "  anticipatory = no callers, no stubs nearby (write the caller)",
        "  possibly-stranded = only stub callers (verify still needed before investing nearby)",
        "",
    ]
    prev_file = None
    for name, file_path, line_no, total_callers, stub_callers, missing_callers, _decs in rows:
        fp = (file_path or "").replace("\\", "/")
        fp_short = fp.split("/")[-1]
        if fp_short != prev_file:
            lines.append(f"  {fp_short}")
            prev_file = fp_short
        if total_callers == 0:
            label = "ready-but-blocked" if file_path in files_with_stubs else "anticipatory"
        else:
            label = f"possibly-stranded ({int(stub_callers)} stub callers)"
        other_files = [f for f in name_files.get(name, []) if f != fp_short]
        dupe_note = f"  ⚠ also in {', '.join(other_files)}" if other_files else ""
        lines.append(f"    {name}  line {line_no}  [{label}]{dupe_note}")
    return "\n".join(lines)


def find_conditional_stubs(oracle: "DBOracle", args: dict) -> str:
    """
    find_conditional_stubs(limit?) - find implemented functions that contain
    'raise NotImplementedError' inside a conditional branch (if/elif/else).
    These pass stub detection (the function has real logic) but will crash
    at runtime on specific inputs.

    Scans source files for functions marked is_stub=0 that contain the pattern.
    """
    import re as _re
    limit = int(args.get("limit", 30))
    conn = oracle.conn

    # Get all non-stub functions with their source file paths
    fn_rows = conn.execute(
        "SELECT name, file_path, line_number FROM functions WHERE is_stub = 0 ORDER BY file_path, line_number"
    ).fetchall()
    if not fn_rows:
        return "No implemented functions found."

    # Read each unique file once, scan for conditional NotImplementedError
    from pathlib import Path as _Path
    file_lines: dict[str, list[str]] = {}
    results: list[tuple[str, str, int, int]] = []  # (name, file_path, fn_line, hit_line)

    # Pattern: raise NotImplementedError inside an if/elif/else block
    # We approximate by finding functions where the raise appears but is indented
    # more than the function's base indent (meaning it's inside a conditional)
    _nie_pat = _re.compile(r"raise\s+NotImplementedError")
    _if_pat  = _re.compile(r"^\s*(if |elif |else:)")

    for name, file_path, fn_line in fn_rows:
        if not file_path or not _Path(file_path).exists():
            continue
        if file_path not in file_lines:
            try:
                file_lines[file_path] = _Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                file_lines[file_path] = []
        lines_src = file_lines[file_path]
        if not lines_src or fn_line < 1 or fn_line > len(lines_src):
            continue

        # Scan from fn_line forward to the next function at same/lower indent
        fn_indent = len(lines_src[fn_line - 1]) - len(lines_src[fn_line - 1].lstrip())
        found_if = False
        for i in range(fn_line, min(fn_line + 80, len(lines_src))):
            src_line = lines_src[i]
            if not src_line.strip():
                continue
            cur_indent = len(src_line) - len(src_line.lstrip())
            # Stop at next top-level definition
            if cur_indent <= fn_indent and i > fn_line and src_line.lstrip().startswith(("def ", "class ", "async def ")):
                break
            if _if_pat.match(src_line):
                found_if = True
            if found_if and _nie_pat.search(src_line):
                results.append((name, file_path, fn_line, i + 1))
                break

        if len(results) >= limit:
            break

    if not results:
        return "No conditional stubs found (no non-stub functions with conditional NotImplementedError)."

    lines = [
        f"Conditional stubs ({len(results)} found) — implemented functions with raise NotImplementedError in a branch:",
        "(These pass stub detection but will crash on specific inputs)",
        "",
    ]
    prev_file = None
    for name, file_path, fn_line, hit_line in results:
        fp_short = (file_path or "").replace("\\", "/").split("/")[-1]
        if fp_short != prev_file:
            lines.append(f"  {fp_short}")
            prev_file = fp_short
        lines.append(f"    {name}  (def line {fn_line}, raise line {hit_line})")
    return "\n".join(lines)


def project_stub(oracle: "DBOracle", args: dict) -> str:
    """
    project_stub(symbol) - generate a concrete implementation for a stub function
    using its call-graph context, behavioral contracts, and sibling code.
    Requires llama-server running. May take 20-40 seconds.
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


def scaffold_from_pattern(assessor: "Assessor", args: dict) -> str:
    """
    scaffold_from_pattern(symbol[, limit]) - find structurally similar complete
    implementations in the corpus and extract a fill-in-the-blanks scaffold.

    Finds siblings by: (1) same file/directory with matching return_type, and
    (2) embedding similarity on "{name}: {docstring}" (threshold 0.50).
    Extracts structural skeleton of each match (first-statement type, return
    shape, error handling) and synthesizes a template showing canonical patterns
    and variation points.

    Args:
        symbol: target function name (required)
        limit:  max sibling matches to analyze (default 5)
    """
    import json as _json
    import os

    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    limit = int(args.get("limit", 5))

    oracle = assessor.oracle
    conn = oracle.conn

    # 1. Fetch target function row
    fn_row = conn.execute(
        "SELECT name, file_path, line_number, is_stub, return_type, docstring, param_types_json "
        "FROM functions WHERE name = ? LIMIT 1",
        (symbol,),
    ).fetchone()
    if not fn_row:
        return f"ERROR: symbol '{symbol}' not found in functions table"

    fn_name, file_path, line_num, is_stub, return_type, docstring, param_json = fn_row
    short_fp = (file_path or "").replace("\\", "/").split("/")[-1]
    target_dir = os.path.dirname(file_path or "").replace("\\", "/") if file_path else ""

    lines = [
        f"Scaffold from pattern for '{fn_name}'  ({short_fp}:{line_num})",
        "",
    ]

    # 2. Module-family siblings: same file or same directory, non-stub, matching return_type
    family_rows = []
    if file_path:
        # Same file first (strongest signal)
        same_file = conn.execute(
            "SELECT name, file_path, line_number, return_type, docstring "
            "FROM functions WHERE file_path = ? AND name != ? AND is_stub = 0 "
            "AND (return_type = ? OR ? IS NULL) "
            "ORDER BY line_number LIMIT ?",
            (file_path, symbol, return_type, return_type, limit * 2),
        ).fetchall()
        family_rows.extend(same_file)

        if len(family_rows) < limit and target_dir:
            # Same directory, different file
            same_dir = conn.execute(
                "SELECT name, file_path, line_number, return_type, docstring "
                "FROM functions WHERE file_path != ? AND is_stub = 0 "
                "AND replace(replace(file_path,'\\\\','/'), '\\', '/') LIKE ? "
                "AND (return_type = ? OR ? IS NULL) "
                "ORDER BY file_path, line_number LIMIT ?",
                (file_path, f"{target_dir}/%", return_type, return_type, limit * 2),
            ).fetchall()
            family_rows.extend(same_dir)

    seen = {symbol}
    family_candidates = []
    for r in family_rows:
        if r[0] not in seen:
            seen.add(r[0])
            family_candidates.append(dict(zip(
                ["name", "file_path", "line_number", "return_type", "docstring"], r
            )))
        if len(family_candidates) >= limit:
            break

    # 3. Embedding-similarity siblings (threshold 0.50, looser than find_duplicates)
    embed_candidates = []
    if docstring:
        try:
            import numpy as np
            from determined.agent.embed_utils import embed_text

            target_text = f"{fn_name}: {docstring[:400]}"
            target_vec = embed_text(target_text)

            # Load non-stub functions with docstrings
            candidate_rows = conn.execute(
                "SELECT name, file_path, line_number, return_type, docstring "
                "FROM functions WHERE is_stub = 0 AND name != ? "
                "AND docstring IS NOT NULL AND trim(docstring) != '' "
                "ORDER BY file_path, name LIMIT 2000",
                (symbol,),
            ).fetchall()

            if candidate_rows:
                model = _get_embed_model()
                c_texts = [f"{r[0]}: {r[4][:400]}" for r in candidate_rows]
                c_vecs = model.encode(c_texts, normalize_embeddings=True, show_progress_bar=False)
                scores = np.dot(c_vecs, target_vec)
                ranked = sorted(zip(scores, candidate_rows), key=lambda x: -x[0])
                for score, r in ranked:
                    if score < 0.50:
                        break
                    if r[0] not in seen:
                        seen.add(r[0])
                        embed_candidates.append({
                            "name": r[0], "file_path": r[1], "line_number": r[2],
                            "return_type": r[3], "docstring": r[4],
                            "embed_score": float(score),
                        })
                    if len(embed_candidates) >= limit:
                        break
        except Exception:
            pass  # embedding unavailable — fall back to module-family only

    # 4. Merge: family first (stronger prior), then embedding, up to limit
    all_siblings = []
    for c in family_candidates:
        all_siblings.append({**c, "source": "module-family"})
    for c in embed_candidates:
        if c["name"] not in {s["name"] for s in all_siblings}:
            all_siblings.append({**c, "source": f"embedding({c['embed_score']:.2f})"})
    all_siblings = all_siblings[:limit]

    if not all_siblings:
        lines.append("No structural siblings found.")
        lines.append("  (No non-stub functions in the same module with matching return_type,")
        lines.append("   and no embedding-similar functions above threshold 0.50)")
        return "\n".join(lines)

    lines.append(f"STRUCTURAL SIBLINGS  ({len(all_siblings)} found)")
    for s in all_siblings:
        s_fp = (s["file_path"] or "").replace("\\", "/").split("/")[-1]
        lines.append(f"  - {s['name']}  ({s_fp}:{s['line_number']})  [{s['source']}]")
    lines.append("")

    # 5. Extract skeleton for each sibling
    from determined.agent.stub_projector import _get_source_lines, _extract_structural_skeleton

    skeletons = []
    for s in all_siblings:
        raw = _get_source_lines(s["file_path"], s["line_number"], window=60)
        # Strip line-number prefixes to get plain source for AST parsing
        plain_lines = []
        for raw_line in raw.splitlines():
            # format is "   N  <code>"
            if len(raw_line) > 6 and raw_line[:6].strip().isdigit():
                plain_lines.append(raw_line[6:])
            else:
                plain_lines.append(raw_line)
        plain_source = "\n".join(plain_lines)
        skel = _extract_structural_skeleton(plain_source, s["name"])
        skeletons.append({**s, "skeleton": skel})

    # 6. Synthesize template
    lines.append("STRUCTURAL ANALYSIS")
    field_labels = [
        ("first_stmt_type", "First statement"),
        ("return_shape", "Return shape"),
        ("error_handling", "Error handling"),
        ("has_guard", "Has guard clause"),
    ]
    for field, label in field_labels:
        vals = [sk["skeleton"][field] for sk in skeletons]
        counts: dict = {}
        for v in vals:
            counts[str(v)] = counts.get(str(v), 0) + 1
        if len(counts) == 1:
            lines.append(f"  {label}: {list(counts.keys())[0]}  [canonical — all {len(skeletons)} siblings agree]")
        else:
            options = ", ".join(f"{v}×{n}" for v, n in sorted(counts.items(), key=lambda x: -x[1]))
            lines.append(f"  {label}: VARIATION POINT  [{options}]")
    lines.append("")

    # 7. Template scaffold
    lines.append("SCAFFOLD TEMPLATE")
    lines.append("```python")
    # Reconstruct signature from target
    try:
        param_types = _json.loads(param_json or "{}")
    except Exception:
        param_types = {}
    params_str = ", ".join(
        f"{p}: {t}" if t else p for p, t in param_types.items()
    ) if param_types else "..."
    ret_str = f" -> {return_type}" if return_type else ""
    lines.append(f"def {fn_name}({params_str}){ret_str}:")

    # Determine canonical choices
    first_stmt_vals = [sk["skeleton"]["first_stmt_type"] for sk in skeletons]
    most_common_first = max(set(first_stmt_vals), key=first_stmt_vals.count)
    err_vals = [sk["skeleton"]["error_handling"] for sk in skeletons]
    most_common_err = max(set(err_vals), key=err_vals.count)
    ret_vals = [sk["skeleton"]["return_shape"] for sk in skeletons]
    most_common_ret = max(set(ret_vals), key=ret_vals.count)
    guard_vals = [sk["skeleton"]["has_guard"] for sk in skeletons]
    majority_guard = sum(1 for v in guard_vals if v) > len(guard_vals) / 2

    if majority_guard and most_common_first == "if_guard":
        lines.append("    if not <condition>:  # FILL IN: guard clause")
        lines.append("        return <early_exit>")

    if most_common_err == "try_except":
        lines.append("    try:")
        lines.append("        # FILL IN: main logic")
        lines.append("        <result> = <operation>")
        lines.append("    except Exception as e:")
        lines.append("        # FILL IN: error handling")
        lines.append("        raise")
    elif most_common_err == "raise":
        lines.append("    # FILL IN: main logic")
        lines.append("    if not <check>:")
        lines.append("        raise ValueError('...')")
    else:
        lines.append("    # FILL IN: main logic")

    if most_common_ret == "dict":
        lines.append("    return {")
        lines.append("        # FILL IN: result keys")
        lines.append("    }")
    elif most_common_ret == "list":
        lines.append("    return [  # FILL IN: result list  ]")
    elif most_common_ret == "none":
        lines.append("    return None  # or omit")
    else:
        lines.append("    return <result>  # FILL IN")
    lines.append("```")
    lines.append("")

    # 8. Reference each sibling briefly for manual inspection
    lines.append("REFERENCE IMPLEMENTATIONS")
    for s in all_siblings:
        s_fp = (s["file_path"] or "").replace("\\", "/").split("/")[-1]
        snippet = (s.get("docstring") or "")[:80].replace("\n", " ")
        lines.append(f"  {s['name']}  ({s_fp}:{s['line_number']})")
        if snippet:
            lines.append(f"    {snippet}")
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
    lines.append("")
    lines.append(_gap_summary_block(assessor))
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
        _extract_layer_rules, write_seed_layer_rules_doc,
        DesignRule,
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

    from determined.ingestion.structure_induction import run as _si_run
    induced_stored = 0

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

        # Multi-method structure induction pre-pass (RM52)
        # Seeds = constraint sentences already found by the deterministic extractor.
        try:
            doc_text = open(doc.path, encoding="utf-8", errors="ignore").read()
            seeds = [
                s
                for r in rules
                for s in r.rule.replace(f"[{r.source_heading}] ", "").split(" | ")
                if s.strip()
            ]
            induced = _si_run(doc_text, seeds)
            for item in induced:
                if item.tier == "review":
                    continue  # not stored until confirmed
                # Convert to DesignRule with tier encoded in kind/confidence
                if item.tier == "convergent":
                    si_conf = doc.confidence
                    si_kind = "requirement"
                else:  # discriminant
                    si_conf = "medium"
                    si_kind = "requirement"
                prefix = f"[SI:{item.tier}|{item.tag or 'convergent'}] " if item.tag else f"[SI:{item.tier}] "
                all_rules.append(DesignRule(
                    subject=doc.rel_path.split("/")[-1].split(".")[0],
                    rule=prefix + item.text,
                    source_file=doc.rel_path,
                    source_heading="structure_induction",
                    extraction="si",
                    confidence=si_conf,
                    provenance=f"{si_conf}:{doc.rel_path}:si",
                    kind=si_kind,
                ))
                induced_stored += 1
        except Exception:
            pass

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

    # Build embedding index of all design_notes already in DB for semantic dedup.
    # Compared against each candidate rule; skip if cosine similarity >= 0.85.
    import re
    _SEM_DUP_THRESHOLD = 0.85
    _bracket_re = re.compile(r"^\[[^\]]+\]\s*")
    _sem_vecs: list[np.ndarray] = []
    try:
        from determined.oracle.embedding_model import embed_text as _embed, cosine_similarity as _cos_sim
        _embedding_ready = True
        for (_nc,) in oracle.conn.execute(
            "SELECT content FROM knowledge_artifacts WHERE kind='design_note'"
        ).fetchall():
            _sem_vecs.append(_embed(_bracket_re.sub("", _nc)))
    except Exception:
        _embedding_ready = False

    def _is_semantic_dup(rule_text: str) -> bool:
        if not _embedding_ready or not _sem_vecs:
            return False
        vec = _embed(rule_text)
        return any(_cos_sim(vec, e) >= _SEM_DUP_THRESHOLD for e in _sem_vecs)

    for rule in all_rules:
        # Semantic dedup: skip if this rule is too similar to an existing design_note
        if _is_semantic_dup(rule.rule):
            skipped += 1
            continue
        # Legacy prefix-match dedup (fast, catches exact re-runs without embedding cost)
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
        if _embedding_ready:
            _sem_vecs.append(_embed(rule.rule))  # track within-run to catch run-internal dups
        stored += 1

    # Extract and store structured layer rules from all processed docs
    layer_rules_stored = 0
    for doc in design_docs:
        try:
            text = open(doc.path, encoding="utf-8", errors="ignore").read()
            for lr in _extract_layer_rules(text, doc.rel_path):
                import json
                content = json.dumps(lr)
                existing = oracle.conn.execute(
                    "SELECT COUNT(*) FROM knowledge_artifacts "
                    "WHERE kind='layer_rule' AND content = ?", (content,)
                ).fetchone()[0]
                if not existing:
                    assessor.add_artifact(doc.rel_path, "layer_rule", content, provenance="human-confirmed")
                    layer_rules_stored += 1
        except Exception:
            pass

    # If no layer rules were found at all, write the seed doc and tell the user
    total_layer_rules = oracle.conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='layer_rule'"
    ).fetchone()[0]
    seed_msg = ""
    if total_layer_rules == 0:
        dest = write_seed_layer_rules_doc(root)
        if dest:
            seed_msg = (
                f"\n\nWe didn't find any layer rules for this project. "
                f"We've created LAYER_RULES.md in your project folder with some examples to get you started. "
                f"Open it, uncomment the rules that fit your project, and run ingest_design_docs to activate them. "
                f"Layer rules tell Determined which parts of your code shouldn't be importing from other parts "
                f"— catching architectural drift before it becomes a problem."
            )

    lines = [
        f"Design doc ingestion: {stored} rules stored, {skipped} already present, {errors} errors",
    ]
    if induced_stored:
        lines.append(f"  Structure induction (RM52): {induced_stored} additional candidates (convergent + discriminant)")
    if conflicted:
        lines.append(f"  Conflicts detected: {conflicted} rules flagged for human review")
    if layer_rules_stored:
        lines.append(f"  Layer rules stored: {layer_rules_stored}")
    lines.append(f"Processed {len(processed_files)} docs:")
    for f in processed_files:
        lines.append(f"  {f}")
    if seed_msg:
        lines.append(seed_msg)
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
    Pure data assembly - no LLM, no side effects (SOTS XI).
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

    from determined.agent.graph_utils import _has_id_columns as _hic
    _use_ids = _hic(oracle.conn)
    callee_set = {
        r[0] for r in oracle.conn.execute(
            "SELECT DISTINCT target_id FROM graph_edges" if _use_ids
            else "SELECT DISTINCT callee FROM graph_edges"
        ).fetchall()
    }
    caller_set = {
        r[0] for r in oracle.conn.execute(
            "SELECT DISTINCT source_id FROM graph_edges" if _use_ids
            else "SELECT DISTINCT caller FROM graph_edges"
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
    """Format _project_status_data as readable text (no LLM)."""
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
    from determined.agent.llm_client import generate_quality as _llm_generate, LLM_QUALITY_TIMEOUT as LLM_TIMEOUT
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
    couple, and what design constraints apply. Optionally synthesizes with LLM.

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

    # Attempt LLM synthesis; degrade to structural if unavailable (SOTS XIII)
    synthesis = _synthesize_with_ollama(structural, goal, conn=assessor.oracle.conn)
    if synthesis:
        return structural + enrichment_note + "\n\n--- Synthesis ---\n" + synthesis
    return structural + enrichment_note + "\n\n(llama-server unavailable for synthesis - structural data above)"


def symbol_context(assessor: "Assessor", args: dict) -> str:
    """
    symbol_context(symbol[, file_path]) - everything known about a named symbol.
    Replaces chaining symbol_intent + list_callers + list_callees + get_findings + check_design_violations.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    file_hint = args.get("file_path", "").strip()
    oracle = assessor.oracle
    conn = oracle.conn

    # 1. Declaration
    sym_rows = conn.execute(
        "SELECT name, file_path, line_number, symbol_type FROM symbols WHERE name = ?",
        (symbol,),
    ).fetchall()
    if file_hint:
        sym_rows = [r for r in sym_rows if file_hint in r[1]] or sym_rows

    # Build file-qualified header so the model can distinguish same-named symbols
    distinct_files = list(dict.fromkeys(r[1] for r in sym_rows))  # order-preserving dedup
    if len(distinct_files) > 1:
        short_files = [f.replace("\\", "/").split("/")[-1] for f in distinct_files]
        header = f"=== symbol_context: {symbol} (defined in {len(distinct_files)} files: {', '.join(short_files)}) ===\n"
    elif distinct_files:
        short_file = distinct_files[0].replace("\\", "/").split("/")[-1]
        header = f"=== symbol_context: {symbol} ({short_file}) ===\n"
    else:
        header = f"=== symbol_context: {symbol} ===\n"
    lines = [header]

    if sym_rows:
        lines.append(f"[DECLARATION]")
        if len(distinct_files) > 1:
            lines.append(f"  NOTE: '{symbol}' exists in {len(distinct_files)} files — each is a distinct symbol.")
        for r in sym_rows:
            short = r[1].replace("\\", "/").split("/")[-1]
            lines.append(f"  {symbol} ({short}):  line {r[2]}, type {r[3]}, file {r[1]}")
        # class container (use first row)
        cls_row = conn.execute(
            "SELECT class_name FROM class_attributes WHERE attribute = ? LIMIT 1",
            (symbol,),
        ).fetchone()
        if cls_row:
            lines.append(f"  class: {cls_row[0]}")
    else:
        lines.append("[DECLARATION] not found in symbols table")

    # 2. Docstring — when symbol appears in multiple files, show each separately
    lines.append(f"\n[DOCSTRING]")
    if len(distinct_files) > 1:
        for file_path in distinct_files:
            short = file_path.replace("\\", "/").split("/")[-1]
            doc = None
            for table in ("functions", "classes"):
                row = conn.execute(
                    f"SELECT docstring FROM {table} WHERE name = ? AND file_path = ?",
                    (symbol, file_path),
                ).fetchone()
                if row and row[0]:
                    doc = row[0]
                    break
            lines.append(f"  {symbol} ({short}): {doc[:200] if doc else '(none)'}")
    else:
        doc = None
        for table in ("functions", "classes"):
            row = conn.execute(
                f"SELECT docstring FROM {table} WHERE name = ?", (symbol,)
            ).fetchone()
            if row and row[0]:
                doc = row[0]
                break
        lines.append(f"  {doc[:300] if doc else '(none)'}")

    # 3. Risk badge
    from determined.agent.risk_annotator import score_risk
    risk = score_risk(oracle, symbol)
    lines.append(f"\n[RISK]  {risk['level']}")
    for reason in risk.get("reasons", []):
        lines.append(f"  - {reason}")

    # 4. Find-references
    decl_files = {r[1] for r in sym_rows}
    usage_rows = conn.execute(
        "SELECT file_path, line_number, caller FROM symbol_references WHERE callee LIKE ? ORDER BY file_path, line_number",
        (f"%{symbol}",),
    ).fetchall()
    out_rows = conn.execute(
        "SELECT file_path, line_number, callee FROM symbol_references WHERE caller = ? ORDER BY file_path, line_number",
        (symbol,),
    ).fetchall()
    lines.append(f"\n[FIND-REFERENCES]")
    lines.append(f"  declarations: {len(decl_files)} file(s): {', '.join(sorted(decl_files)) or '(none)'}")
    if usage_rows:
        lines.append(f"  usages ({len(usage_rows)}):")
        for fp, ln, ctx in usage_rows[:10]:
            lines.append(f"    {fp}:{ln}  (in {ctx})")
        if len(usage_rows) > 10:
            lines.append(f"    ... {len(usage_rows) - 10} more")
    else:
        lines.append("  usages: (none found)")
    if out_rows:
        lines.append(f"  outgoing calls ({len(out_rows)}):")
        for fp, ln, tgt in out_rows[:5]:
            lines.append(f"    -> {tgt}  {fp}:{ln}")

    # 5-6. Callers / callees
    callers = _list_callers_raw(oracle, symbol)
    callees = _list_callees_raw(oracle, symbol)
    lines.append(f"\n[CALLERS]  {len(callers)} total")
    for c in callers[:5]:
        tag = " (resolved)" if c["resolved"] else ""
        lines.append(f"  {c['caller']}{tag}  {c['file_path'] or ''}:{c['line_number'] or ''}")
    if len(callers) > 5:
        lines.append(f"  ... {len(callers) - 5} more")
    lines.append(f"\n[CALLEES]  {len(callees)} total")
    for c in callees[:5]:
        tag = " (resolved)" if c["resolved"] else ""
        lines.append(f"  {c['callee']}{tag}  {c['file_path'] or ''}:{c['line_number'] or ''}")
    if len(callees) > 5:
        lines.append(f"  ... {len(callees) - 5} more")

    # 7. Class attributes (if symbol is a class)
    attr_rows = conn.execute(
        "SELECT attribute, inferred_type FROM class_attributes WHERE class_name = ? ORDER BY attribute",
        (symbol,),
    ).fetchall()
    if attr_rows:
        lines.append(f"\n[CLASS ATTRIBUTES]")
        for attr, itype in attr_rows:
            lines.append(f"  .{attr}: {itype or '?'}")

    # 8. Design frame
    fp_for_frame = sym_rows[0][1] if sym_rows else (file_hint or "")
    frame = _get_design_frame(assessor, symbol, fp_for_frame)
    if frame.strip():
        lines.append(f"\n[DESIGN FRAME]\n{frame}")

    # 9. Known findings
    findings = get_findings(assessor, {"symbol": symbol})
    if not findings.startswith("No stored"):
        lines.append(f"\n[FINDINGS]\n{findings}")

    return "\n".join(lines)


def completion_contract(assessor: "Assessor", args: dict) -> str:
    """
    completion_contract(symbol[, include_projection]) - everything needed before writing
    the first line of a stub implementation: signature, callers, available callees,
    behavioral contracts, design constraints, and stub dependencies.

    Args:
        symbol: function name (required)
        include_projection: if true, append an LLM-generated "Suggested approach" block
    """
    import json as _json

    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    include_projection = str(args.get("include_projection", "false")).lower() == "true"

    oracle = assessor.oracle
    conn = oracle.conn

    # 1. Function row
    fn_row = conn.execute(
        "SELECT name, file_path, line_number, is_stub, param_types_json, return_type, docstring "
        "FROM functions WHERE name = ? LIMIT 1",
        (symbol,),
    ).fetchone()
    if not fn_row:
        return f"ERROR: symbol '{symbol}' not found in functions table"

    fn_name, file_path, line_num, is_stub, param_json, return_type, docstring = fn_row
    short_fp = (file_path or "").replace("\\", "/").split("/")[-1]

    lines = [
        f"Completion contract for '{fn_name}'  ({short_fp}:{line_num})",
        "",
    ]

    # 2. SIGNATURE
    try:
        param_types = _json.loads(param_json or "{}")
    except Exception:
        param_types = {}
    if param_types or return_type:
        params_str = ", ".join(
            f"{p}: {t}" if t else p for p, t in param_types.items()
        ) if param_types else "..."
        ret_str = f" -> {return_type}" if return_type else ""
        lines.append("SIGNATURE")
        lines.append(f"  {fn_name}({params_str}){ret_str}")
    else:
        lines.append("SIGNATURE")
        lines.append(f"  {fn_name}(...)  [no type annotations found]")
    lines.append("")

    # 3. CALLERS
    caller_rows = _list_callers_raw(oracle, symbol)
    if caller_rows:
        lines.append(f"CALLERS ({len(caller_rows)}) — must satisfy these")
        for r in caller_rows[:10]:
            c_fp = (r["file_path"] or "").replace("\\", "/").split("/")[-1]
            c_ln = r["line_number"] or ""
            loc = f"({c_fp}:{c_ln})" if c_fp else ""
            lines.append(f"  - {r['caller']}  {loc}")
        if len(caller_rows) > 10:
            lines.append(f"  ... and {len(caller_rows) - 10} more")
    else:
        lines.append("CALLERS")
        lines.append("  (none — this function is uncalled or an entry point)")
    lines.append("")

    # 4. CALLEES — split into implemented vs stubs
    callee_rows = _list_callees_raw(oracle, symbol)
    if callee_rows:
        callee_names = [r["callee"] for r in callee_rows]
        stub_set = set()
        if callee_names:
            placeholders = ",".join("?" * len(callee_names))
            stub_rows = conn.execute(
                f"SELECT name FROM functions WHERE name IN ({placeholders}) AND is_stub = 1",
                callee_names,
            ).fetchall()
            stub_set = {r[0] for r in stub_rows}

        implemented = [r for r in callee_rows if r["callee"] not in stub_set]
        stubs = [r for r in callee_rows if r["callee"] in stub_set]

        if implemented:
            lines.append("CALLEES AVAILABLE (already implemented)")
            for r in implemented[:8]:
                c_fp = (r["file_path"] or "").replace("\\", "/").split("/")[-1]
                lines.append(f"  - {r['callee']}  ({c_fp})" if c_fp else f"  - {r['callee']}")
        if stubs:
            lines.append("STUBS THIS DEPENDS ON (implement those first — see implementation_order)")
            for r in stubs:
                c_fp = (r["file_path"] or "").replace("\\", "/").split("/")[-1]
                lines.append(f"  - {r['callee']}  ({c_fp})" if c_fp else f"  - {r['callee']}")
        lines.append("")

    # 5. CONTRACTS (from behavioral_contracts table)
    contract_rows = conn.execute(
        "SELECT description FROM behavioral_contracts WHERE function_name = ? ORDER BY line_number",
        (symbol,),
    ).fetchall()
    if contract_rows:
        lines.append("CONTRACTS")
        for (desc,) in contract_rows:
            lines.append(f"  - {desc.strip()}")
        lines.append("")
    elif docstring:
        # Fall back to docstring excerpt if no structured contracts
        excerpt = docstring.strip().splitlines()[0][:120]
        lines.append("CONTRACTS")
        lines.append(f"  (from docstring) {excerpt}")
        lines.append("")

    # 6. DESIGN CONSTRAINTS (from check_design_violations_core)
    try:
        violations = _check_design_violations_core(assessor, symbol, file_path or "")
        if violations:
            lines.append("DESIGN CONSTRAINTS")
            for v in violations[:5]:
                subject = v.get("subject", "")
                content = v.get("content", "")[:120]
                lines.append(f"  - {subject}: {content}")
            lines.append("")
    except Exception:
        pass  # embedding may be unavailable; skip gracefully

    # 7. Optional LLM projection
    if include_projection and is_stub:
        try:
            from determined.agent.stub_projector import gather_context
            ctx = gather_context(conn, symbol)
            if ctx:
                lines.append("SUGGESTED APPROACH (LLM projection — use with caution)")
                lines.append("  (run project_stub for full projection)")
                lines.append("")
        except Exception:
            pass

    return "\n".join(lines)


def readiness_check(assessor: "Assessor", args: dict) -> str:
    """
    readiness_check(symbol[, include_design_check]) - fast gate: is this symbol
    safe to start implementing?

    Returns READY or BLOCKED with a tiered list of blockers:
      Tier 1 - symbol exists and is actually incomplete
      Tier 2 - stub callees (must be implemented first)
      Tier 3 - unknown type annotations (external or not-yet-defined)
      Tier 4 - design constraint flags (SOTS/GRASP violations >= 0.4)
      Tier 5 - cycle in the stub dependency graph

    Args:
        symbol:               function name (required)
        include_design_check: if true, run embedding-based design constraint check
                              (Tier 4); default false (can be slow)
    """
    import json as _json

    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    include_design = str(args.get("include_design_check", "false")).lower() == "true"

    oracle = assessor.oracle
    conn = oracle.conn

    # ── Tier 1: symbol exists and is incomplete ───────────────────────
    fn_row = conn.execute(
        "SELECT name, file_path, line_number, is_stub, param_types_json, return_type "
        "FROM functions WHERE name = ? LIMIT 1",
        (symbol,),
    ).fetchone()
    if not fn_row:
        return f"NOT FOUND: '{symbol}' not in functions table"

    fn_name, file_path, line_num, is_stub, param_json, return_type = fn_row
    short_fp = (file_path or "").replace("\\", "/").split("/")[-1]
    header = f"readiness_check: '{fn_name}'  ({short_fp}:{line_num})\n"

    abc_gaps = _get_abc_gap_set(conn)
    if not is_stub and fn_name not in abc_gaps:
        return header + "ALREADY COMPLETE — not a stub and no ABC gap. Nothing to implement."

    blockers: list[str] = []

    # ── Tier 2: stub callees ──────────────────────────────────────────
    callee_rows = _list_callees_raw(oracle, symbol)
    if callee_rows:
        callee_names = [r["callee"].rsplit(".", 1)[-1] for r in callee_rows]
        if callee_names:
            placeholders = ",".join("?" * len(callee_names))
            stub_callees = conn.execute(
                f"SELECT name, file_path, line_number FROM functions "
                f"WHERE name IN ({placeholders}) AND is_stub = 1",
                callee_names,
            ).fetchall()
            for sc_name, sc_fp, sc_ln in stub_callees:
                sc_short = (sc_fp or "").replace("\\", "/").split("/")[-1]
                blockers.append(
                    f"STUB CALLEE: {sc_name}  ({sc_short}:{sc_ln}) — implement first"
                )

    # ── Tier 3: unknown type annotations ─────────────────────────────
    try:
        param_types = _json.loads(param_json or "{}")
    except Exception:
        param_types = {}
    unknown_types: list[str] = []
    for param, type_str in param_types.items():
        if not type_str:
            continue
        # Strip generics/optionals: "list[Foo]" → "Foo", "Optional[Bar]" → "Bar"
        bare = type_str.strip().rstrip("]")
        for part in bare.replace("[", ",").split(","):
            t = part.strip()
            if not t or t[0].islower() or t in ("None", "str", "int", "float", "bool",
                                                  "list", "dict", "tuple", "set", "Any",
                                                  "Optional", "Union", "Callable", "Type"):
                continue
            found = conn.execute(
                "SELECT 1 FROM functions WHERE name = ? UNION SELECT 1 FROM classes WHERE name = ? LIMIT 1",
                (t, t),
            ).fetchone()
            if not found:
                unknown_types.append(f"UNKNOWN TYPE: {t} (param '{param}') — external or not yet defined")
    blockers.extend(unknown_types)

    # ── Tier 4: design constraint flags (opt-in) ─────────────────────
    if include_design and file_path:
        try:
            violations = _check_design_violations_core(assessor, symbol, file_path)
            for v in violations:
                if v.get("score", 0) >= 0.4:
                    snippet = v["content"][:100].replace("\n", " ")
                    blockers.append(
                        f"DESIGN NOTE: {v['subject']} (score {v['score']:.2f}) — {snippet}"
                    )
        except Exception:
            pass  # embedding unavailable — silently skip

    # ── Tier 5: cycle in stub dependency graph ────────────────────────
    # BFS from symbol over stub-only subgraph; if symbol reappears → cycle
    try:
        from collections import deque as _deque
        stub_set_q = "SELECT name FROM functions WHERE is_stub = 1"
        stub_names = {r[0] for r in conn.execute(stub_set_q)}
        stub_names.update(abc_gaps)

        visited: set[str] = {symbol}
        queue: _deque = _deque([symbol])
        cycle_found = False
        while queue and not cycle_found:
            current = queue.popleft()
            callee_rows_bfs = conn.execute(
                "SELECT DISTINCT callee FROM graph_edges WHERE caller = ?", (current,)
            ).fetchall()
            for (callee,) in callee_rows_bfs:
                bare_callee = callee.rsplit(".", 1)[-1] if "." in callee else callee
                if bare_callee not in stub_names:
                    continue
                if bare_callee == symbol:
                    cycle_found = True
                    break
                if bare_callee not in visited:
                    visited.add(bare_callee)
                    queue.append(bare_callee)
        if cycle_found:
            blockers.append(
                f"CYCLE: '{symbol}' appears in its own stub dependency graph — "
                "circular stub dependency, resolve before implementing"
            )
    except Exception:
        pass

    # ── Output ────────────────────────────────────────────────────────
    lines = [header.rstrip()]
    if not blockers:
        lines.append("READY — all dependency checks passed. Safe to implement.")
        lines.append("")
        # Positive summary
        if param_types:
            resolved = [f"{p}: {t}" for p, t in param_types.items() if t]
            if resolved:
                lines.append("Types resolved: " + ", ".join(resolved))
        complete_callees = [r["callee"].rsplit(".", 1)[-1] for r in callee_rows
                            if r["callee"].rsplit(".", 1)[-1] not in
                            {b.split(":")[1].split("(")[0].strip() for b in blockers}]
        if complete_callees:
            lines.append("Callees available: " + ", ".join(complete_callees[:8]))
        design_note = " (design check skipped — pass include_design_check=true to enable)" if not include_design else ""
        lines.append(f"Next: run completion_contract('{symbol}') for the implementation brief.{design_note}")
    else:
        lines.append(f"BLOCKED — {len(blockers)} issue(s) must be resolved first:")
        lines.append("")
        for i, b in enumerate(blockers, 1):
            lines.append(f"  {i}. {b}")
        lines.append("")
        stub_blockers = [b for b in blockers if b.startswith("STUB CALLEE")]
        if stub_blockers:
            lines.append("Tip: run implementation_order() to get a wave plan for resolving stub callees.")

    return "\n".join(lines)


def concept_search(assessor: "Assessor", args: dict) -> str:
    """
    concept_search(query) - search a term/concept across all text surfaces,
    ranked by semantic similarity. Exploration tool (vs search_symbols name-locator).
    """
    query = args.get("query", "").strip()
    if not query:
        return "ERROR: query argument required"
    oracle = assessor.oracle
    conn = oracle.conn
    like_q = f"%{query}%"

    hits: list[dict] = []  # {surface, name, file_path, line_number, snippet}

    # 1. Symbol names
    for r in _search_symbols_raw(oracle, query, limit=100):
        hits.append({
            "surface": "symbol_name",
            "name": r["name"],
            "file_path": r.get("file_path", ""),
            "line_number": r.get("line_number"),
            "snippet": r.get("docstring", "")[:120] if r.get("docstring") else "",
        })

    # 2. Docstrings (functions + classes) - deduplicate against surface 1
    existing_names = {h["name"] for h in hits}
    for table in ("functions", "classes"):
        rows = conn.execute(
            f"SELECT name, file_path, line_number, docstring FROM {table} WHERE docstring LIKE ?",
            (like_q,),
        ).fetchall()
        for name, fp, ln, doc in rows:
            if name not in existing_names:
                hits.append({
                    "surface": "docstring",
                    "name": name,
                    "file_path": fp or "",
                    "line_number": ln,
                    "snippet": (doc or "")[:120],
                })
                existing_names.add(name)

    # 3. Behavioral contracts
    try:
        rows = conn.execute(
            "SELECT function_name, file_path, line_number, description FROM behavioral_contracts WHERE description LIKE ?",
            (like_q,),
        ).fetchall()
        for fname, fp, ln, desc in rows:
            hits.append({
                "surface": "contract",
                "name": fname,
                "file_path": fp or "",
                "line_number": ln,
                "snippet": (desc or "")[:120],
            })
    except Exception:
        pass

    # 4. Design notes
    try:
        rows = conn.execute(
            "SELECT subject, content FROM knowledge_artifacts WHERE kind='design_note' AND content LIKE ?",
            (like_q,),
        ).fetchall()
        for subj, content in rows:
            hits.append({
                "surface": "design_note",
                "name": subj,
                "file_path": "",
                "line_number": None,
                "snippet": (content or "")[:120],
            })
    except Exception:
        pass

    # 5. Distilled summaries
    try:
        rows = conn.execute(
            "SELECT subject, distilled FROM semantic_summaries WHERE distilled LIKE ?",
            (like_q,),
        ).fetchall()
        for subj, dist in rows:
            hits.append({
                "surface": "distilled_summary",
                "name": subj,
                "file_path": subj if "/" in subj or "\\" in subj else "",
                "line_number": None,
                "snippet": (dist or "")[:120],
            })
    except Exception:
        pass

    if not hits:
        return f"No results for '{query}'"

    # Semantic re-ranking
    try:
        from determined.oracle.embedding_model import embed_text
        import numpy as np
        q_vec = embed_text(query)
        texts = [h["snippet"] or h["name"] for h in hits]
        model = _get_embed_model()
        vecs = model.encode(texts, normalize_embeddings=True)
        scores = np.dot(vecs, q_vec)
        threshold = 0.25
        ranked = sorted(
            [(float(s), h) for s, h in zip(scores, hits) if float(s) >= threshold],
            key=lambda x: x[0],
            reverse=True,
        )
        if ranked:
            hits = [h for _, h in ranked]
        # else fall through with original order
    except Exception:
        pass

    # Group by surface and format
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for h in hits:
        groups[h["surface"]].append(h)

    surface_order = ["symbol_name", "docstring", "contract", "design_note", "distilled_summary"]
    out = [f"concept_search: '{query}'  ({len(hits)} results)\n"]
    for surface in surface_order:
        group = groups.get(surface, [])
        if not group:
            continue
        out.append(f"[{surface.upper()}]  {len(group)} hit(s)")
        for h in group[:8]:
            loc = f"  {h['file_path']}:{h['line_number']}" if h.get("line_number") else (f"  {h['file_path']}" if h["file_path"] else "")
            snip = f"  >> {h['snippet']}" if h["snippet"] else ""
            out.append(f"  {h['name']}{loc}")
            if snip:
                out.append(snip)
        if len(group) > 8:
            out.append(f"  ... {len(group) - 8} more")
        out.append("")

    return "\n".join(out)


def docstring_health(assessor: "Assessor", args: dict) -> str:
    """
    docstring_health([file][, module][, propose]) - surfaces missing and stale docstrings.
    Missing: no docstring at all. Stale: docstring cosine-distance from distilled summary < 0.55.
    propose=True (default): store proposals in the workflow queue for editor write-back.
    """
    import json
    file_scope = args.get("file", "").strip()
    module_scope = args.get("module", "").strip()
    propose = str(args.get("propose", "true")).lower() not in ("false", "0", "no")

    oracle = assessor.oracle
    conn = oracle.conn

    scope_clause = ""
    scope_params: list = []
    if file_scope:
        scope_clause = " AND file_path = ?"
        scope_params = [file_scope]
    elif module_scope:
        scope_clause = " AND file_path LIKE ?"
        scope_params = [f"%{module_scope}%"]

    # --- Missing docstrings ---
    missing: list[dict] = []
    for table in ("functions", "classes"):
        rows = conn.execute(
            f"SELECT name, file_path, line_number FROM {table} "
            f"WHERE (docstring IS NULL OR docstring = ''){scope_clause} "
            f"ORDER BY file_path, line_number",
            scope_params,
        ).fetchall()
        for name, fp, ln in rows:
            missing.append({"name": name, "file_path": fp, "line_number": ln, "table": table})

    # --- Stale docstrings ---
    stale: list[dict] = []
    try:
        from determined.oracle.embedding_model import embed_text, cosine_similarity
        for table in ("functions", "classes"):
            rows = conn.execute(
                f"SELECT name, file_path, line_number, docstring FROM {table} "
                f"WHERE docstring IS NOT NULL AND docstring != ''{scope_clause}",
                scope_params,
            ).fetchall()
            for name, fp, ln, doc in rows:
                dist_row = conn.execute(
                    "SELECT distilled FROM semantic_summaries WHERE subject = ? AND distilled IS NOT NULL",
                    (fp,),
                ).fetchone()
                if dist_row and dist_row[0]:
                    score = cosine_similarity(embed_text(doc), embed_text(dist_row[0]))
                    if score < 0.55:
                        stale.append({
                            "name": name,
                            "file_path": fp,
                            "line_number": ln,
                            "score": round(score, 3),
                            "distilled": dist_row[0],
                        })
    except Exception as e:
        stale_err = str(e)
    else:
        stale_err = None

    # --- Proposals ---
    stored_proposals = 0
    if propose:
        from determined.intent.workflow_store import add_item
        k_conn = assessor._knowledge_conn
        for sym in missing:
            dist_row = conn.execute(
                "SELECT distilled FROM semantic_summaries WHERE subject = ? AND distilled IS NOT NULL",
                (sym["file_path"],),
            ).fetchone()
            if dist_row and dist_row[0]:
                content = json.dumps({
                    "proposed_docstring": dist_row[0],
                    "file_path": sym["file_path"],
                    "line_number": sym["line_number"],
                })
                add_item(k_conn, kind="next_up",
                         subject=f"docstring::{sym['file_path']}::{sym['name']}",
                         content=content, provenance="llm-proposed")
                stored_proposals += 1
        for sym in stale:
            content = json.dumps({
                "proposed_docstring": sym["distilled"],
                "file_path": sym["file_path"],
                "line_number": sym["line_number"],
                "staleness_score": sym["score"],
            })
            add_item(k_conn, kind="next_up",
                     subject=f"docstring::{sym['file_path']}::{sym['name']}",
                     content=content, provenance="llm-proposed")
            stored_proposals += 1

    # --- Format output ---
    scope_label = file_scope or module_scope or "whole corpus"
    lines = [f"=== docstring_health: {scope_label} ===\n"]

    lines.append(f"[MISSING]  {len(missing)} symbol(s) with no docstring")
    for s in missing[:30]:
        lines.append(f"  {s['file_path']}:{s['line_number']}  {s['name']}  ({s['table']})")
    if len(missing) > 30:
        lines.append(f"  ... {len(missing) - 30} more")

    lines.append(f"\n[STALE]  {len(stale)} symbol(s) with low docstring/code similarity")
    if stale_err:
        lines.append(f"  (staleness check skipped: {stale_err})")
    else:
        for s in stale[:30]:
            score = s["score"]
            flag = "STALE" if score < 0.55 else "REVIEW"
            lines.append(f"  [{flag} {score:.2f}]  {s['file_path']}:{s['line_number']}  {s['name']}")
        if len(stale) > 30:
            lines.append(f"  ... {len(stale) - 30} more")

    if propose:
        lines.append(f"\n[PROPOSALS]  {stored_proposals} proposal(s) stored in workflow queue")
        lines.append("  Use workflow_status() to see them; accept/dismiss via the UI.")

    return "\n".join(lines)


def annotate_function(assessor: "Assessor", args: dict) -> str:
    """
    annotate_function(symbol[, file_path][, write_back]) - infer param types,
    return type, behavioral contract, and docstring for an unannotated function.

    Assembles source + callers + callees + inline notes + design notes, calls
    LLM to produce structured inference, stores result as kind='inferred_annotation'
    in knowledge_artifacts. Labeled as inferred, never written to source without
    explicit write_back=True and user confirmation.

    Args:
        symbol     - function name (required)
        file_path  - disambiguates when name is shared across files (optional)
        write_back - if True, also propose docstring edit via workflow queue (default False)
    """
    import json
    from datetime import datetime, timezone

    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    file_path_hint = args.get("file_path", "").strip()
    write_back = str(args.get("write_back", "false")).lower() not in ("false", "0", "no")

    oracle = assessor.oracle
    conn = oracle.conn

    # --- 1. Resolve function row ---
    if file_path_hint:
        row = conn.execute(
            "SELECT name, file_path, line_number, docstring, arguments_json, return_type, param_types_json "
            "FROM functions WHERE name = ? AND file_path = ? LIMIT 1",
            (symbol, file_path_hint),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT name, file_path, line_number, docstring, arguments_json, return_type, param_types_json "
            "FROM functions WHERE name = ? LIMIT 1",
            (symbol,),
        ).fetchone()
    if not row:
        return f"ERROR: function '{symbol}' not found in corpus"

    fn_name, fn_file, fn_line, fn_doc, fn_args_json, fn_return, fn_param_json = row
    fn_args = json.loads(fn_args_json or "[]")
    fn_param_types = json.loads(fn_param_json or "{}") if fn_param_json else {}

    # --- 2. Source code ---
    from determined.agent.stub_projector import _get_source_lines
    source = _get_source_lines(fn_file, fn_line, window=50)

    # --- 3. Callers (up to 20) ---
    callers = _list_callers_raw(oracle, fn_name)[:20]
    caller_names = [c["caller"] for c in callers]

    # --- 4. Callees with return types ---
    callees = _list_callees_raw(oracle, fn_name)
    callee_info = []
    for ce in callees[:15]:
        ce_row = conn.execute(
            "SELECT return_type FROM functions WHERE name = ? LIMIT 1",
            (ce["callee"].rsplit(".", 1)[-1],),
        ).fetchone()
        callee_info.append({
            "callee": ce["callee"],
            "return_type": ce_row[0] if ce_row else None,
        })

    # --- 5. Inline notes for this function ---
    inline_rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='inline_note' AND subject=?",
        (fn_name,),
    ).fetchall()
    inline_notes = [r[0] for r in inline_rows]

    # --- 6. Design notes mentioning this symbol or file ---
    design_rows = conn.execute(
        "SELECT content FROM knowledge_artifacts "
        "WHERE kind IN ('design_note','layer_rule') AND (content LIKE ? OR content LIKE ?) LIMIT 5",
        (f"%{fn_name}%", f"%{fn_file}%"),
    ).fetchall()
    design_notes = [r[0] for r in design_rows]

    # --- 7. Build LLM prompt ---
    sig = f"def {fn_name}({', '.join(fn_args)})"
    if fn_return:
        sig += f" -> {fn_return}"

    prompt_parts = [
        "You are a Python type inference assistant. Analyze the function below and infer:",
        "  - param_types: dict mapping each parameter name to its Python type string",
        "  - return_type: Python type string for the return value",
        "  - pre_conditions: list of pre-conditions (what must be true before calling)",
        "  - post_conditions: list of post-conditions (what the function guarantees)",
        "  - raises: list of exception scenarios",
        "  - docstring: one sentence describing the function's purpose",
        "  - confidence: float 0.0-1.0 based on evidence quality",
        "  - inference_basis: list of concrete reasons supporting the inferences",
        "",
        "Return ONLY a valid JSON object with exactly these keys. No explanation outside JSON.",
        "",
        f"FUNCTION SIGNATURE: {sig}",
    ]

    if fn_doc:
        prompt_parts += ["", f'EXISTING DOCSTRING: """{fn_doc[:200]}"""']

    if source:
        prompt_parts += ["", "SOURCE CODE:", source[:2000]]

    if callers:
        prompt_parts += ["", f"CALLED BY ({len(callers)} callers):"]
        for c in callers[:10]:
            prompt_parts.append(f"  - {c['caller']}" + (f" ({c['file_path']})" if c["file_path"] else ""))

    if callee_info:
        prompt_parts += ["", "CALLS INTO:"]
        for ce in callee_info:
            rt = f" -> {ce['return_type']}" if ce["return_type"] else ""
            prompt_parts.append(f"  - {ce['callee']}{rt}")

    if inline_notes:
        prompt_parts += ["", "INLINE NOTES FROM SOURCE:"]
        for note in inline_notes[:5]:
            prompt_parts.append(f"  {note[:150]}")

    if design_notes:
        prompt_parts += ["", "RELEVANT DESIGN CONTEXT:"]
        for dn in design_notes[:3]:
            prompt_parts.append(f"  {dn[:200]}")

    prompt_parts += [
        "",
        "Respond with JSON only. Example structure:",
        '{"param_types": {"x": "int"}, "return_type": "str", "pre_conditions": [], '
        '"post_conditions": [], "raises": [], "docstring": "...", "confidence": 0.7, '
        '"inference_basis": ["reason1"]}',
    ]

    prompt = "\n".join(prompt_parts)

    # --- 8. Call LLM ---
    try:
        from determined.agent.llm_client import generate_quality as _llm_generate
        raw = _llm_generate(prompt, max_tokens=600, temperature=0.1)
    except Exception as e:
        return f"ERROR: LLM call failed: {e}"

    # Extract JSON from response
    import re as _re
    json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
    if not json_match:
        return f"ERROR: LLM did not return valid JSON.\nRaw response:\n{raw[:500]}"
    try:
        result = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        return f"ERROR: JSON parse failed: {e}\nRaw:\n{raw[:500]}"

    # Validate required keys
    required_keys = {"param_types", "return_type", "pre_conditions", "post_conditions",
                     "raises", "docstring", "confidence", "inference_basis"}
    missing_keys = required_keys - set(result.keys())
    if missing_keys:
        # Fill missing keys with empty defaults
        for k in missing_keys:
            if k in ("param_types",):
                result[k] = {}
            elif k in ("pre_conditions", "post_conditions", "raises", "inference_basis"):
                result[k] = []
            elif k == "confidence":
                result[k] = 0.5
            else:
                result[k] = ""

    # Ensure inference_basis is non-empty
    if not result.get("inference_basis"):
        basis = []
        if callers:
            basis.append(f"{len(callers)} caller(s) found in call graph")
        if callee_info:
            basis.append(f"{len(callee_info)} callee(s) analyzed")
        if inline_notes:
            basis.append(f"{len(inline_notes)} inline note(s) from source")
        result["inference_basis"] = basis or ["inferred from source code structure"]

    # --- 9. Store as inferred_annotation ---
    content = json.dumps(result)
    created_at = datetime.now(timezone.utc).isoformat()
    # Delete stale annotation for this function first
    conn.execute(
        "DELETE FROM knowledge_artifacts WHERE kind='inferred_annotation' AND subject=?",
        (fn_name,),
    )
    conn.execute(
        "INSERT INTO knowledge_artifacts "
        "(subject, kind, content, provenance, created_at, file_hash, needs_review, corpus) "
        "VALUES (?, 'inferred_annotation', ?, 'llm-inferred', ?, NULL, 1, NULL)",
        (fn_name, content, created_at),
    )
    conn.commit()

    # --- 10. Optionally propose docstring via workflow queue ---
    if write_back and result.get("docstring"):
        from determined.intent.workflow_store import add_item
        k_conn = assessor._knowledge_conn
        add_item(k_conn, kind="next_up",
                 subject=f"docstring::{fn_file}::{fn_name}",
                 content=json.dumps({
                     "proposed_docstring": result["docstring"],
                     "file_path": fn_file,
                     "line_number": fn_line,
                 }),
                 provenance="llm-inferred")

    # --- 11. Format output ---
    conf = result.get("confidence", 0.0)
    lines = [
        f"=== annotate_function: {fn_name} ===",
        f"File: {fn_file}:{fn_line}",
        f"Confidence: {conf:.2f}",
        "",
        "[INFERRED PARAM TYPES]",
    ]
    pt = result.get("param_types") or {}
    if pt:
        for param, typ in pt.items():
            lines.append(f"  {param}: {typ}")
    else:
        lines.append("  (none inferred)")

    rt = result.get("return_type") or ""
    lines += ["", f"[INFERRED RETURN TYPE]  {rt or '(unknown)'}"]

    doc = result.get("docstring") or ""
    lines += ["", f"[INFERRED DOCSTRING]  {doc}"]

    pre = result.get("pre_conditions") or []
    post = result.get("post_conditions") or []
    raises = result.get("raises") or []
    if pre or post or raises:
        lines.append("")
        lines.append("[BEHAVIORAL CONTRACT]")
        for p in pre:
            lines.append(f"  PRE:    {p}")
        for p in post:
            lines.append(f"  POST:   {p}")
        for r in raises:
            lines.append(f"  RAISES: {r}")

    basis = result.get("inference_basis") or []
    if basis:
        lines += ["", "[INFERENCE BASIS]"]
        for b in basis:
            lines.append(f"  - {b}")

    lines += ["", f"[STORED] inferred_annotation saved to knowledge_artifacts (subject='{fn_name}')"]
    if write_back:
        lines.append("[WRITE_BACK] docstring proposal queued in workflow (use workflow_status to review)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RM51: Annotation pass driver
# ---------------------------------------------------------------------------

def _build_annotation_queue(oracle, scope: str = "") -> list:
    """
    Return list of (name, file_path, caller_count) for functions that lack
    inferred or real param types, ordered by caller_count descending.
    Filters to is_stub=0 (complete functions with missing type info).
    """
    conn = oracle.conn

    # Functions missing real type annotations and not already annotated by LLM
    already_annotated = {
        row[0]
        for row in conn.execute(
            "SELECT subject FROM knowledge_artifacts WHERE kind='inferred_annotation'"
        ).fetchall()
    }

    scope_clause = ""
    scope_params: list = []
    if scope:
        scope_clause = " AND f.file_path LIKE ?"
        scope_params = [f"%{scope}%"]

    rows = conn.execute(
        f"SELECT f.name, f.file_path, "
        f"  (SELECT COUNT(*) FROM graph_edges WHERE callee=f.name) AS caller_count "
        f"FROM functions f "
        f"WHERE f.is_stub=0 "
        f"  AND (f.param_types_json IS NULL OR f.param_types_json='{{}}' OR f.param_types_json='')"
        # Plain JS/JSX have no type syntax; exclude them — TS/TSX stay in
        f"  AND f.file_path NOT LIKE '%.js' AND f.file_path NOT LIKE '%.jsx'"
        f"{scope_clause} "
        f"ORDER BY caller_count DESC",
        scope_params,
    ).fetchall()

    return [
        {"name": r[0], "file_path": r[1], "caller_count": r[2]}
        for r in rows
        if r[0] not in already_annotated
    ]


def run_annotation_pass(assessor: "Assessor", args: dict) -> str:
    """
    run_annotation_pass([scope][, max_functions][, convergence_threshold]) -
    priority-ordered annotation pass over unannotated functions.

    Builds a queue of complete (non-stub) functions that lack param_types_json,
    ordered by caller count descending (most-called first). Calls annotate_function
    for each, up to max_functions or until convergence_threshold consecutive
    LLM failures occur.

    Args:
        scope                - optional file path prefix/substring to restrict the pass
        max_functions        - max functions to annotate per run (default 20)
        convergence_threshold - stop after this many consecutive LLM failures (default 3)
    """
    scope = args.get("scope", "").strip()
    max_functions = int(args.get("max_functions", 20))
    convergence_threshold = int(args.get("convergence_threshold", 3))

    oracle = assessor.oracle
    queue = _build_annotation_queue(oracle, scope)

    if not queue:
        return (
            "run_annotation_pass: queue is empty.\n"
            "All qualifying functions are already annotated, or no functions match the scope.\n"
            f"(scope={scope!r})"
        )

    total_eligible = len(queue)
    to_process = queue[:max_functions]

    results = []
    annotated = 0
    skipped = 0
    consecutive_failures = 0

    for item in to_process:
        fn_name = item["name"]
        fn_file = item["file_path"]
        caller_count = item["caller_count"]

        result_text = annotate_function(assessor, {
            "symbol": fn_name,
            "file_path": fn_file,
            "write_back": False,
        })

        if result_text.startswith("ERROR"):
            consecutive_failures += 1
            skipped += 1
            results.append(f"  SKIP  {fn_name} ({fn_file}) -- {result_text[:80]}")
            if consecutive_failures >= convergence_threshold:
                results.append(
                    f"\n[STOPPED] {convergence_threshold} consecutive failures -- "
                    "LLM may be unavailable."
                )
                break
        else:
            consecutive_failures = 0
            annotated += 1
            # Extract confidence from output for summary
            conf_line = next(
                (ln for ln in result_text.splitlines() if ln.startswith("Confidence:")),
                ""
            )
            conf = conf_line.split(":", 1)[-1].strip() if conf_line else "?"
            results.append(
                f"  OK    {fn_name} ({fn_file.split('/')[-1].split(chr(92))[-1]}) "
                f"callers={caller_count} conf={conf}"
            )

    summary_lines = [
        f"=== run_annotation_pass ===",
        f"Scope:     {scope or '(all)'}",
        f"Eligible:  {total_eligible} functions in queue",
        f"Processed: {len(to_process)} (max_functions={max_functions})",
        f"Annotated: {annotated}",
        f"Skipped:   {skipped}",
        "",
        "Results:",
    ] + results

    if total_eligible > max_functions:
        remaining = total_eligible - len(to_process)
        summary_lines.append(
            f"\n{remaining} more functions remain. Run again to continue the pass."
        )

    return "\n".join(summary_lines)


def evaluate_claim(assessor: "Assessor", args: dict) -> str:
    """
    evaluate_claim(claim, question[, surfaces][, top_n]) - evaluate one
    observation against design constraints stored in the corpus.

    Runs the Observe->Situate->Evaluate kernel:
      1. Retrieve evidence: cosine-search knowledge_artifacts for the claim
      2. Evaluate: single focused LLM call -> structured Judgment
      3. Return verdict, reasoning, confidence, and which evidence drove it

    Args:
        claim    - the observation to evaluate (required)
        question - what relationship to look for (required)
        surfaces - comma-separated knowledge_artifacts kinds to search
                   (default: "design_note")
        top_n    - max evidence items to retrieve (default: 5)
    """
    claim = args.get("claim", "").strip()
    question = args.get("question", "").strip()
    if not claim:
        return "ERROR: claim argument required"
    if not question:
        return "ERROR: question argument required"

    surfaces_raw = args.get("surfaces", "design_note")
    surfaces = [s.strip() for s in surfaces_raw.split(",") if s.strip()]
    top_n = int(args.get("top_n", 5))

    from determined.agent.evaluator import evaluate, retrieve_evidence
    conn = assessor.oracle.conn

    evidence = retrieve_evidence(claim, conn, surfaces=surfaces, top_n=top_n)
    if not evidence:
        return (
            f"EVALUATE: no evidence found in surfaces {surfaces!r} for claim:\n"
            f"  {claim}\n\n"
            "Run ingest_design_docs first, or check that design_note artifacts exist."
        )

    judgment = evaluate(claim, evidence, question)

    # Auto-waypoint: pin actionable findings so they surface in the Pins tab
    if judgment.verdict not in {"UNRELATED", "UNCERTAIN"}:
        try:
            import json as _json
            from determined.intent.knowledge_artifact import add_artifact as _add_artifact
            k_conn = assessor._knowledge_conn
            if k_conn is not None:
                _add_artifact(k_conn, subject=claim[:120], kind="waypoint", content=_json.dumps({
                    "name": claim[:120],
                    "view_origin": "evaluate_claim",
                    "note": judgment.reasoning,
                    "verdict": judgment.verdict,
                    "confidence": judgment.confidence,
                    "trail": [],
                }), provenance="ai-generated")
        except Exception:
            pass  # waypoint creation is best-effort

    lines = [
        f"EVALUATE CLAIM",
        f"  Claim:    {claim}",
        f"  Question: {question}",
        f"",
        f"  Verdict:    {judgment.verdict}",
        f"  Confidence: {int(judgment.confidence * 100)}%",
        f"  Reasoning:  {judgment.reasoning}",
    ]
    if judgment.evidence_used:
        lines.append(f"  Evidence:   {judgment.evidence_used[0][:120]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ROLE PATTERN LIBRARY
# ---------------------------------------------------------------------------

# Role patterns derived from Responsibility-Driven Design (Wirfs-Brock et al., 2003).
# These six roles cover the primary behavioral responsibilities a function/method can hold,
# inferred from calling structure alone (callers, callees, params, file stem) without
# reading the function body. Source: "Object Design: Roles, Responsibilities, and
# Collaborations", Rebecca Wirfs-Brock & Alan McKean.
_ROLE_PATTERNS = [
    {
        "subject": "pattern::information-holder",
        "content": (
            "INFORMATION-HOLDER (Wirfs-Brock): knows and provides information to others. "
            "Profile: high in-degree (called by many), returns data without calling many "
            "other functions, params are keys or identifiers, callers use the return value "
            "directly. File stem contains store, registry, repository, cache, config, state, "
            "or db. Does not make decisions or trigger side effects."
        ),
    },
    {
        "subject": "pattern::structurer",
        "content": (
            "STRUCTURER (Wirfs-Brock): maintains relationships between objects or components. "
            "Profile: manages collections, graphs, or hierarchies; methods include add, remove, "
            "link, attach, register, or connect; params are objects to relate rather than "
            "primitive values. File stem contains graph, tree, map, registry, index, or topology. "
            "Owns the shape of a data structure but not its business meaning."
        ),
    },
    {
        "subject": "pattern::service-provider",
        "content": (
            "SERVICE-PROVIDER (Wirfs-Brock): performs a well-defined unit of work on request "
            "and returns a result. Profile: called by many, calls few; encapsulates a capability "
            "(compute, generate, fetch, format); params are inputs to the computation; return "
            "value is the product. File stem contains service, engine, processor, generator, "
            "renderer, calculator, or formatter. Stateless or nearly so."
        ),
    },
    {
        "subject": "pattern::coordinator",
        "content": (
            "COORDINATOR (Wirfs-Brock): orchestrates a complete use-case or workflow by "
            "sequencing calls to multiple collaborators. Profile: 4+ distinct callees across "
            "different modules; few or no callers; sequences steps (validate → process → store "
            "→ respond) without owning the business logic itself; returns a terminal result "
            "(response, redirect, summary) after all steps complete. Examples: HTTP route "
            "handlers that validate then call services then return a response; use-case "
            "orchestrators; pipeline entry points. Distinct from INTERFACER: COORDINATOR "
            "sequences multiple steps; INTERFACER is a thin 1-to-1 translator."
        ),
    },
    {
        "subject": "pattern::controller",
        "content": (
            "CONTROLLER (Wirfs-Brock): makes decisions and directs the actions of other objects. "
            "Profile: contains conditional logic (if/switch on state or input type); calls "
            "different collaborators depending on the decision; returns a verdict, status, or "
            "routes to a handler. File stem contains controller, adjudicator, router, dispatcher, "
            "validator, judge, or policy. Distinct from coordinator: it decides, not just delegates."
        ),
    },
    {
        "subject": "pattern::interfacer",
        "content": (
            "INTERFACER (Wirfs-Brock): thin adapter that translates a single request across "
            "a system boundary. Profile: 1 primary inbound source, 1 primary outbound target; "
            "translates format, validates, or enforces a contract; typically 1-3 callees total; "
            "does NOT sequence multiple workflow steps. File stem contains boundary, adapter, "
            "gateway, bridge, facade, proxy, or interface. If a function sequences 4+ service "
            "calls or orchestrates a complete use-case, it is COORDINATOR not INTERFACER."
        ),
    },
]


def _ensure_pattern_library(conn) -> int:
    """
    Seed role patterns into knowledge_artifacts as kind='pattern'.
    Upserts content so updated descriptions take effect in existing DBs.
    Returns number of patterns inserted or updated.
    """
    existing = {
        r[0]: r[1] for r in conn.execute(
            "SELECT subject, content FROM knowledge_artifacts WHERE kind='pattern'"
        ).fetchall()
    }
    changed = 0
    for p in _ROLE_PATTERNS:
        if p["subject"] not in existing:
            conn.execute(
                "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at) "
                "VALUES (?, 'pattern', ?, 'human-confirmed', datetime('now'))",
                (p["subject"], p["content"]),
            )
            changed += 1
        elif existing[p["subject"]] != p["content"]:
            conn.execute(
                "UPDATE knowledge_artifacts SET content=? "
                "WHERE subject=? AND kind='pattern'",
                (p["content"], p["subject"]),
            )
            changed += 1
    if changed:
        conn.commit()
    return changed


def infer_behavior(assessor: "Assessor", args: dict) -> str:
    """
    infer_behavior(symbol) - infer the behavioral role of an undocumented symbol
    from its calling context (callers, callees, param names, file stem).

    Uses the role pattern library (coordinator / boundary / pipeline-stage /
    adjudicator / factory / observer) stored as kind='pattern' artifacts.
    Seeds the library on first call if not present.

    Returns the best-matching role + confidence + reasoning.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"

    result = _infer_behavior_for_symbol(assessor, symbol)

    lines = [
        f"INFER BEHAVIOR: {symbol}",
        f"  Context:    {result.get('context', '')[:200]}",
        f"",
        f"  Verdict:    {result['verdict']}",
        f"  Role:       {result['role']}",
        f"  Confidence: {int(result['confidence'] * 100)}%",
        f"  Reasoning:  {result['reasoning']}",
    ]
    return "\n".join(lines)


def _infer_behavior_for_symbol(assessor: "Assessor", symbol: str) -> dict:
    """
    Core logic of infer_behavior for a single symbol, returns a dict with
    role/confidence/verdict/reasoning so batch mode can aggregate results
    and store them without re-running the full string-formatting path.
    """
    from determined.agent.evaluator import collect_symbol_context, evaluate

    conn = assessor.oracle.conn
    _ensure_pattern_library(conn)
    context_query = collect_symbol_context(conn, symbol)

    # Force-fetch all patterns: this is a classification over a fixed set, not a
    # retrieval question. Threshold-gated similarity would silently drop patterns
    # that don't embed-match the context, producing false "no match" results.
    pattern_rows = conn.execute(
        "SELECT content FROM knowledge_artifacts WHERE kind='pattern' ORDER BY subject"
    ).fetchall()
    evidence = [r[0] for r in pattern_rows]

    if not evidence:
        return {"symbol": symbol, "role": "UNKNOWN", "confidence": 0.0,
                "verdict": "NO_PATTERNS", "reasoning": "pattern library empty"}

    question = (
        "Does this function's calling profile match one of the described architectural "
        "role patterns? If so, return MATCHES_PATTERN. If the profile is ambiguous or "
        "too sparse, return UNCERTAIN."
    )
    judgment = evaluate(context_query, evidence, question)

    matched_role = ""
    if judgment.evidence_used:
        matched_role = judgment.evidence_used[0].split(":")[0].strip()

    return {
        "symbol": symbol,
        "context": context_query,
        "role": matched_role or "(uncertain)",
        "confidence": judgment.confidence,
        "verdict": judgment.verdict,
        "reasoning": judgment.reasoning,
    }


def infer_behavior_batch(assessor: "Assessor", args: dict) -> str:
    """
    infer_behavior_batch(module) - run infer_behavior on every function in a module
    and store results as knowledge_artifacts with kind='role_inference'.

    module  - relative file path or module stem (e.g. 'world/encounter_generator.py'
              or just 'encounter_generator'). Functions already having a stored
              role_inference artifact are skipped unless force=true.
    force   - (optional) 'true' to re-run even if a stored result exists.

    Returns a summary table: symbol | role | confidence.
    """
    module = args.get("module", "").strip()
    if not module:
        return "ERROR: module argument required"
    force = str(args.get("force", "false")).lower() == "true"

    oracle = assessor.oracle
    conn = oracle.conn

    _ensure_pattern_library(conn)

    # Resolve module to a file_path suffix
    normalized = module.replace("\\", "/")
    if not normalized.endswith(".py"):
        normalized = normalized + ".py"

    rows = conn.execute(
        """
        SELECT name FROM functions WHERE file_path LIKE ?
        ORDER BY line_number
        """,
        (f"%{normalized}",),
    ).fetchall()

    if not rows:
        return f"infer_behavior_batch: no functions found matching '{module}'"

    symbols = [r[0] for r in rows]

    # Check which already have stored results
    stored: set[str] = set()
    if not force:
        for sym in symbols:
            exists = conn.execute(
                "SELECT 1 FROM knowledge_artifacts WHERE kind='role_inference' AND subject=? LIMIT 1",
                (sym,),
            ).fetchone()
            if exists:
                stored.add(sym)

    to_run = [s for s in symbols if s not in stored]
    skipped = len(stored)

    results = []
    for sym in to_run:
        r = _infer_behavior_for_symbol(assessor, sym)
        results.append(r)

        # Persist as knowledge_artifact
        content = (
            f"role: {r['role']}  confidence: {int(r['confidence']*100)}%  "
            f"verdict: {r['verdict']}  reasoning: {r['reasoning'][:200]}"
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_artifacts
                (subject, kind, content, provenance, created_at)
            VALUES (?, 'role_inference', ?, 'infer_behavior_batch', datetime('now'))
            """,
            (sym, content),
        )
    conn.commit()

    # Build output table
    lines = [
        f"INFER BEHAVIOR BATCH: {module}",
        f"  Processed: {len(to_run)}  Skipped (cached): {skipped}  Total: {len(symbols)}",
        "",
        f"  {'Symbol':<45} {'Role':<22} {'Conf':>5}  Verdict",
        f"  {'-'*45} {'-'*22} {'-'*5}  {'-'*15}",
    ]

    # Include cached results in the table
    cached_rows = []
    if stored:
        cache_data = conn.execute(
            f"SELECT subject, content FROM knowledge_artifacts "
            f"WHERE kind='role_inference' AND subject IN ({','.join('?'*len(stored))})",
            list(stored),
        ).fetchall()
        for subject, content in cache_data:
            role = "(unknown)"
            conf = "?"
            verdict = "(cached)"
            for part in content.split("  "):
                if part.startswith("role:"):
                    role = part[5:].strip()
                elif part.startswith("confidence:"):
                    conf = part[11:].strip()
                elif part.startswith("verdict:"):
                    verdict = part[8:].strip()
            cached_rows.append((subject, role, conf, verdict))

    for sym, role, conf, verdict in cached_rows:
        sym_short = sym.rsplit(".", 1)[-1] if "." in sym else sym
        lines.append(f"  {sym_short:<45} {role:<22} {conf:>5}  {verdict} [cached]")

    for r in results:
        sym_short = r["symbol"].rsplit(".", 1)[-1] if "." in r["symbol"] else r["symbol"]
        conf_str = f"{int(r['confidence']*100)}%"
        lines.append(f"  {sym_short:<45} {r['role']:<22} {conf_str:>5}  {r['verdict']}")

    return "\n".join(lines)


def trace_data_flow(assessor: "Assessor", args: dict) -> str:
    """
    trace_data_flow(symbol[, depth]) - walk the callee graph from symbol,
    annotating each step with whether it mutates external state.

    At each node: retrieve design_note evidence, run evaluate() with the
    question "Does this step mutate external state or produce side effects?"
    Accumulates a mutation log. Returns an annotated call tree.

    Args:
        symbol - root symbol to trace (required)
        depth  - max recursion depth (default: 3)
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    max_depth = int(args.get("depth", 3))

    from determined.agent.evaluator import evaluate, retrieve_evidence
    oracle = assessor.oracle
    conn = oracle.conn

    _MUTATION_QUESTION = (
        "Does this function mutate external state, modify shared data structures, "
        "call I/O, or produce side effects beyond returning a value?"
    )

    # Name-based mutation prefixes — reliable regardless of evidence
    _MUTATING_VERBS = frozenset({
        "save", "write", "insert", "update", "delete", "remove", "add",
        "append", "push", "pop", "set", "put", "store", "commit", "flush",
        "execute", "exec", "run", "send", "emit", "dispatch", "publish",
        "create", "destroy", "drop", "reset", "clear", "init", "initialize",
        "register", "unregister", "load", "reload",
    })

    def _name_mutates(sym: str) -> bool:
        """Return True if the bare function name starts with a known mutation verb."""
        bare = sym.rsplit(".", 1)[-1].lstrip("_").lower()
        return any(bare == v or bare.startswith(v + "_") for v in _MUTATING_VERBS)

    visited: set[str] = set()
    lines: list[str] = [f"DATA FLOW TRACE: {symbol} (depth={max_depth})", ""]

    _PURE_ROLES = frozenset({"information-holder", "interfacer", "pure fabrication"})

    def _annotate(sym: str, depth: int, prefix: str) -> None:
        import json as _json
        if depth > max_depth or sym in visited:
            return
        visited.add(sym)

        # Build claim from callee context
        callees = _list_callees_raw(oracle, sym)[:10]
        callee_names = [c["callee"] for c in callees]
        claim = f"{sym} calls: {', '.join(callee_names[:8]) or '(none)'}"

        # Retrieve design_note evidence
        evidence = retrieve_evidence(claim, conn, surfaces=["design_note"], top_n=5)
        if not evidence:
            evidence = retrieve_evidence(sym, conn, surfaces=["design_note"], top_n=3)

        # Append role_inference evidence for this symbol if available
        role_row = conn.execute(
            "SELECT content FROM knowledge_artifacts WHERE kind='role_inference' AND subject=? LIMIT 1",
            (sym,)
        ).fetchone()
        inferred_role = ""
        if role_row and role_row[0]:
            try:
                rd = _json.loads(role_row[0])
                inferred_role = rd.get("role", "")
                role_conf = rd.get("confidence", 0.0)
                if inferred_role:
                    evidence.append(
                        f"Inferred role: {inferred_role} (confidence {role_conf:.0%}). "
                        f"{rd.get('reasoning', '')}"
                    )
            except Exception:
                pass

        # Name-based pre-check: verbs like save/execute/append are reliable signals
        if _name_mutates(sym):
            flag = "[MUTATES]"
            conf = 95
            reason = "(name heuristic: mutation verb)"
        elif inferred_role and inferred_role.lower() in _PURE_ROLES and not _name_mutates(sym):
            # Role evidence is sufficient — skip LLM call for obviously pure symbols
            flag = "[pure   ]"
            conf = 95
            reason = f"(role: {inferred_role})"
        elif evidence:
            judgment = evaluate(claim, evidence, _MUTATION_QUESTION)
            # Detect mutation from reasoning text — verdict alone is ambiguous
            # because CONFIRMS means "consistent with evidence", not "yes mutates"
            neg_phrases = ("does not", "no side", "no external", "not modify", "not mutate",
                           "pure", "read-only", "readonly", "no i/o", "no io")
            r_lower = judgment.reasoning.lower()
            negated = any(p in r_lower for p in neg_phrases)
            unrelated = judgment.verdict in ("UNRELATED", "UNCERTAIN")
            mutates = not negated and not unrelated and judgment.confidence >= 0.7
            flag = "[MUTATES]" if mutates else "[pure   ]"
            conf = int(judgment.confidence * 100)
            reason = judgment.reasoning[:80]
        else:
            flag = "[?      ]"
            conf = 0
            reason = "no evidence"

        lines.append(f"{prefix}{flag} {sym} ({conf}%) — {reason}")

        # Recurse into callees
        child_prefix = prefix + "  "
        for c in callees[:6]:
            _annotate(c["callee"], depth + 1, child_prefix)

    _annotate(symbol, 0, "")

    if len(lines) <= 2:
        lines.append("  (no callees found)")
    return "\n".join(lines)


def match_structural_pattern(assessor: "Assessor", args: dict) -> str:
    """
    match_structural_pattern(symbol[, radius]) - check whether the call subgraph
    around a symbol matches a known architectural pattern (coordinator, pipeline,
    adjudicator, etc.) stored in the pattern library.

    Args:
        symbol - root symbol (required)
        radius - BFS radius around symbol (default: 2)
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"
    radius = int(args.get("radius", 2))

    oracle = assessor.oracle
    conn = oracle.conn

    _ensure_pattern_library(conn)

    from determined.agent.evaluator import collect_subgraph_context, retrieve_evidence, evaluate

    subgraph = _graph_subgraph_raw(oracle, symbol, radius)
    if not subgraph.get("nodes"):
        return f"match_structural_pattern: no subgraph found around '{symbol}'"

    claim = collect_subgraph_context(conn, subgraph)
    evidence = retrieve_evidence(claim, conn, surfaces=["pattern"])

    if not evidence:
        return (
            "match_structural_pattern: pattern library is empty. "
            "Run infer_behavior on a symbol first to seed it."
        )

    question = (
        "Does the topology and naming of this call subgraph match one of the described "
        "architectural patterns? Return MATCHES_PATTERN if it fits clearly, UNCERTAIN if "
        "the subgraph is too small or ambiguous to classify."
    )
    judgment = evaluate(claim, evidence, question)

    matched = judgment.evidence_used[0][:120] if judgment.evidence_used else "(none)"
    n_nodes = len(subgraph.get("nodes", set()))
    n_edges = len(subgraph.get("edges", []))

    lines = [
        f"STRUCTURAL PATTERN MATCH: {symbol} (radius={radius})",
        f"  Subgraph: {n_nodes} nodes, {n_edges} edges",
        f"  Verdict:  {judgment.verdict} ({int(judgment.confidence * 100)}%)",
        f"  Reason:   {judgment.reasoning}",
        f"  Pattern:  {matched}",
    ]
    return "\n".join(lines)


def gap_analysis(assessor: "Assessor", args: dict) -> str:
    """
    gap_analysis([file][, module][, symbol]) - on-demand LLM gap analysis.
    No args: uses gap summary to pick highest-signal area automatically.
    Output is generative/idea-mode — proposals, not prescriptions.
    """
    file_scope = args.get("file", "").strip()
    module_scope = args.get("module", "").strip()
    symbol_scope = args.get("symbol", "").strip()

    oracle = assessor.oracle
    conn = oracle.conn

    scope_label = file_scope or module_scope or symbol_scope or "whole corpus"

    # 1. Semantic summaries — the real signal from distill_corpus
    all_summaries = assessor.list_semantic_summaries(kind="file")
    if file_scope:
        summaries = [s for s in all_summaries if file_scope in s.get("subject", "")]
    elif module_scope:
        summaries = [s for s in all_summaries if module_scope in s.get("subject", "")]
    else:
        summaries = all_summaries

    # Cap at ~50 summaries; prefer core game files over utility/stub files
    _CORE_PATTERNS = ("world", "session", "event", "action", "tool", "adjudic",
                      "dungeon", "game_state", "ai_boundary", "narrative", "player")
    summaries.sort(key=lambda s: (
        0 if any(p in s.get("subject", "") for p in _CORE_PATTERNS) else 1
    ))
    summaries = summaries[:50]

    summary_block = "\n\n".join(
        f"[{s.get('subject', '?')}]\n{s.get('content', '').strip()[:300]}"
        for s in summaries
    ) or "  (no summaries available — run --summarize first)"

    # 2. Design notes for context
    if file_scope or module_scope:
        key = file_scope or module_scope
        dn_rows = conn.execute(
            "SELECT content FROM knowledge_artifacts WHERE kind='design_note' AND subject LIKE ? LIMIT 10",
            (f"%{key.strip('%')}%",),
        ).fetchall()
    else:
        dn_rows = conn.execute(
            "SELECT content FROM knowledge_artifacts WHERE kind='design_note' LIMIT 15"
        ).fetchall()
    design_block = "\n".join(f"  - {r[0][:150]}" for r in dn_rows) or "  (none)"

    # 3. Gap metrics block for grounding
    gap_block = _gap_summary_block(assessor)

    # 4. Prompt the quality-tier model with game-domain framing
    from determined.agent.llm_client import chat_quality as chat
    prompt_msgs = [
        {"role": "system", "content":
            "You are analyzing a Python codebase for an AI-driven dungeon-master (DM) game. "
            "The game uses an LLM as the DM's voice and judgment, but the LLM never mutates state — "
            "all state changes flow through a deterministic Intent->Adjudication->Action chain. "
            "Key game subsystems include: world state, session management, event logging, "
            "tool dispatch, action adjudication, and AI boundary enforcement. "
            "Given per-file semantic summaries, identify what game features are missing, "
            "incomplete, or disconnected. Propose typed fills:\n"
            "  extend   — add missing capability to an existing module\n"
            "  bridge   — connect two modules that should interact but don't\n"
            "  mirror   — add analogous coverage that exists elsewhere but is missing here\n"
            "  consolidate — merge fragmented logic into one place\n"
            "Be concrete: name the file, the gap, and what the fix looks like. "
            "5-10 proposals. Focus on game functionality, not documentation."},
        {"role": "user", "content":
            f"Scope: {scope_label}\n\n"
            f"=== Per-file semantic summaries ===\n{summary_block}\n\n"
            f"=== Design notes ===\n{design_block}\n\n"
            f"=== Coverage metrics ===\n{gap_block}\n\n"
            "What game features are missing, incomplete, or disconnected? "
            "Propose typed fills (extend/bridge/mirror/consolidate)."},
    ]
    llm_response = chat(prompt_msgs, timeout=300)

    if llm_response is None:
        return "ERROR: llama-server did not respond. gap_analysis requires a running LLM."

    # 5. Store proposals
    from determined.intent.workflow_store import add_item
    k_conn = assessor._knowledge_conn
    add_item(k_conn, kind="backlog",
             subject=f"gap::{scope_label}",
             content=llm_response, provenance="llm-proposed")

    lines = [
        "GAP ANALYSIS (generative — proposals may be off target):",
        f"Area: {scope_label}",
        "",
        llm_response,
        "",
        "Stored as backlog item. Use workflow_status(kind=backlog) to review.",
    ]
    return "\n".join(lines)


def _gap_summary_block(assessor: "Assessor") -> str:
    """Fast DB-only gap summary — no LLM. Used by knowledge_status and gap_analysis."""
    conn = assessor.oracle.conn
    k_conn = assessor._knowledge_conn

    total_fns = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
    missing_docs = conn.execute(
        "SELECT COUNT(*) FROM functions WHERE docstring IS NULL OR docstring = ''"
    ).fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    distilled = conn.execute(
        "SELECT COUNT(*) FROM semantic_summaries WHERE distilled IS NOT NULL AND distilled != ''"
    ).fetchone()[0]
    design_note_count = k_conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='design_note'"
    ).fetchone()[0]

    # Per-module docstring gaps (first path segment)
    mod_rows = conn.execute(
        "SELECT REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') as fp, "
        "SUM(CASE WHEN docstring IS NULL OR docstring='' THEN 1 ELSE 0 END) as missing, "
        "COUNT(*) as total FROM functions GROUP BY fp"
    ).fetchall()
    # Group by top dir
    from collections import defaultdict
    mod_gaps: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for fp, miss, tot in mod_rows:
        parts = fp.replace("\\", "/").split("/")
        mod = parts[0] if parts else "."
        mod_gaps[mod][0] += miss
        mod_gaps[mod][1] += tot

    gap_lines = []
    for mod, (miss, tot) in sorted(mod_gaps.items(), key=lambda x: -x[1][0]):
        if miss > 0:
            gap_lines.append(f"    {mod}: {miss}/{tot} missing")

    lines = [
        "GAPS AT A GLANCE:",
        f"  Docstring coverage:    {total_fns - missing_docs}/{total_fns} functions documented",
        f"  Distillation coverage: {distilled}/{total_files} files distilled",
        f"  Design notes:          {design_note_count} total",
    ]
    if gap_lines:
        lines.append("  Modules with missing docstrings:")
        lines.extend(gap_lines[:10])
    return "\n".join(lines)


def _filter_gaps_by_design_intent(
    assessor: "Assessor", analysis_text: str
) -> tuple[str, str]:
    """
    Split 27B gap analysis into individual blocks and evaluate each against
    design_notes using the evaluate kernel.

    Returns (real_gaps_text, noise_text):
      real_gaps_text  - gaps that VIOLATE or are UNCERTAIN against design intent
      noise_text      - gaps that CONFIRM or EXPLAIN design intent (intentional)

    If no design_notes exist, returns (analysis_text, "") unchanged.
    """
    from determined.agent.evaluator import retrieve_evidence, evaluate

    conn = assessor.oracle.conn

    # Check design_notes exist — if not, skip filtering entirely
    note_count = conn.execute(
        "SELECT COUNT(*) FROM knowledge_artifacts WHERE kind='design_note'"
    ).fetchone()[0]
    if note_count == 0:
        return analysis_text, ""

    # Split on the markdown separator between gap blocks.
    # The 27B uses '---' on its own line between numbered sections.
    import re
    blocks = re.split(r'\n---\n', analysis_text)
    blocks = [b.strip() for b in blocks if b.strip()]

    # The first block is often a preamble (no "**N." heading) — keep it always
    preamble = ""
    gap_blocks = []
    for block in blocks:
        if re.search(r'\*\*\d+\.', block):
            gap_blocks.append(block)
        else:
            preamble = block

    if not gap_blocks:
        # Couldn't parse blocks — return unchanged
        return analysis_text, ""

    real_gaps = []
    noise = []

    question = (
        "Is this missing connection intentional by design "
        "(e.g., the architecture specifically separates these concerns), "
        "or is it a real architectural gap that needs a fix?"
    )

    for block in gap_blocks:
        # Extract the title line as the claim
        title_match = re.search(r'\*\*\d+\.\s*(.+?)\*\*', block)
        claim = title_match.group(1).strip() if title_match else block[:120]

        evidence = retrieve_evidence(claim, conn, surfaces=["design_note"], top_n=5)
        if not evidence:
            # No relevant design notes — keep the gap (can't filter without evidence)
            real_gaps.append(block)
            continue

        try:
            judgment = evaluate(claim, evidence, question)
        except RuntimeError:
            # LLM unavailable mid-run — keep the gap, don't crash corpus_synthesis
            real_gaps.append(block)
            continue

        verdict = judgment.verdict
        if verdict in ("CONFIRMS", "EXPLAINS"):
            # Design intent says this absence is intentional
            noise.append(
                f"{block}\n"
                f"  [FILTERED: {verdict} ({int(judgment.confidence*100)}%) — "
                f"{judgment.reasoning}]"
            )
        else:
            # VIOLATES, UNRELATED, UNCERTAIN, MATCHES_PATTERN — keep as real gap
            annotation = (
                f"  [evaluate: {verdict} ({int(judgment.confidence*100)}%) — "
                f"{judgment.reasoning}]"
            )
            real_gaps.append(f"{block}\n{annotation}")

    real_text = ("\n\n---\n\n".join([preamble] + real_gaps)).strip() if preamble else \
                ("\n\n---\n\n".join(real_gaps)).strip()
    noise_text = ("\n\n---\n\n".join(noise)).strip()
    return real_text, noise_text


def corpus_synthesis(assessor: "Assessor", args: dict) -> str:
    """
    corpus_synthesis() - two-pass architectural gap analysis.
    Pass 1 (large context): reads all distilled one-liners and maps the
    codebase into named subsystems.
    Pass 2 (quality reasoning): given the subsystem map, identifies
    structural gaps, disconnections, and missing game features.
    """
    from determined.agent.llm_client import generate as fast_gen, chat_quality
    from determined.config import get_fast_ctx, get_quality_ctx

    conn = assessor.oracle.conn
    fast_ctx = get_fast_ctx()
    quality_ctx = get_quality_ctx()

    # --- Pass 1: Build subsystem map from distilled one-liners ---
    rows = conn.execute(
        "SELECT subject, distilled FROM semantic_summaries "
        "WHERE kind='file' AND distilled IS NOT NULL AND distilled != '' "
        "ORDER BY subject"
    ).fetchall()

    if not rows:
        # Fall back to truncated summaries if distill_corpus hasn't been run
        rows = conn.execute(
            "SELECT subject, SUBSTR(content, 1, 80) FROM semantic_summaries "
            "WHERE kind='file' ORDER BY subject"
        ).fetchall()
        if not rows:
            return ("No file summaries found. Run --summarize first:\n"
                    "  python -m determined.agent.local_agent --source <dir> --summarize")

    def _first_sentence(text: str) -> str:
        """Extract first sentence, cap at 100 chars to strip LLM noise."""
        text = (text or "").strip().strip('"').strip("'")
        for sep in (".", "!", "?", "\n"):
            idx = text.find(sep)
            if 10 < idx < 120:
                return text[:idx + 1]
        return text[:100]

    file_list = "\n".join(f"{r[0]}: {_first_sentence(r[1])}" for r in rows)
    estimated_tokens = len(file_list) // 4

    print(f"  Pass 1: {len(rows)} files, ~{estimated_tokens:,} tokens "
          f"(fast ctx: {fast_ctx:,})")

    if estimated_tokens > fast_ctx * 0.85:
        # Trim to fit: keep first fast_ctx*0.85*4 chars
        char_limit = int(fast_ctx * 0.85 * 4)
        file_list = file_list[:char_limit]
        print(f"  (trimmed to fit context)")

    pass1_prompt = (
        "You are analyzing a Python dungeon-master (DM) game codebase.\n"
        "Below is a one-line description of every source file.\n"
        "Group them into 6-10 named subsystems.\n"
        "For each subsystem write ONE paragraph: what it does today, "
        "which files belong to it, and how it connects to other subsystems.\n"
        "Be concrete. Do not mention documentation quality.\n\n"
        f"Files:\n{file_list}"
    )

    subsystem_map = fast_gen(pass1_prompt, timeout=120, max_tokens=1500)
    if not subsystem_map:
        return "ERROR: LLM (port 8081) did not respond for pass 1."

    print(f"  Pass 2: reasoning over subsystem map "
          f"(quality ctx: {quality_ctx:,})...")

    # --- Pass 2: 27B reasons over subsystem map for architectural gaps ---
    pass2_msgs = [
        {"role": "system", "content": (
            "You are analyzing an AI-driven dungeon-master game in Python. "
            "The game's core invariant: the LLM is the DM's voice and judgment "
            "but NEVER mutates state directly. All mutations flow through a chain: "
            "Intent -> Adjudication -> Action -> WorldState. "
            "Given a subsystem map of what currently exists, identify structural gaps: "
            "subsystems that are disconnected, flows that are broken, features that "
            "cannot work because a required bridge is missing. "
            "Be specific: name the gap, the files involved, the type of fix "
            "(extend / bridge / mirror / consolidate), and why it matters for gameplay. "
            "5-8 findings. Focus on game correctness and architecture, not documentation."
        )},
        {"role": "user", "content": (
            f"Subsystem map:\n{subsystem_map}\n\n"
            "What is structurally missing or disconnected in this game system?\n"
            "Which subsystems cannot talk to each other yet?\n"
            "What would break if someone tried to run a game session today?"
        )},
    ]

    analysis = chat_quality(pass2_msgs, timeout=600, max_tokens=1200)
    if not analysis:
        return (
            "ERROR: quality-tier LLM (27B, port 8081) did not respond for pass 2.\n"
            "Is the 27B server running?  Check: Invoke-RestMethod http://localhost:8081/health\n\n"
            "=== SUBSYSTEM MAP (pass 1 only) ===\n" + subsystem_map
        )

    # --- Pass 3: Filter gaps through design-intent evaluate kernel ---
    # Split the 27B output into individual gap blocks and evaluate each
    # against ingested design_notes. Gaps that CONFIRM or EXPLAIN a design
    # constraint are intentional and filtered as noise.
    filtered_analysis, noise_analysis = _filter_gaps_by_design_intent(
        assessor, analysis
    )

    # Store both passes as a backlog item
    full_result = "\n\n".join([
        "=== SUBSYSTEM MAP (pass 1) ===",
        subsystem_map,
        "=== ARCHITECTURAL GAPS (27B reasoning) — design-intent filtered ===",
        filtered_analysis or "(all gaps filtered as intentional by design)",
        "=== FILTERED AS INTENTIONAL (design-confirmed noise) ===",
        noise_analysis or "(none filtered)",
    ])
    from determined.intent.workflow_store import add_item
    k_conn = assessor._knowledge_conn
    if k_conn:
        add_item(k_conn, kind="backlog",
                 subject="corpus_synthesis::gaps",
                 content=full_result, provenance="llm-proposed")

    return "\n".join([
        "CORPUS SYNTHESIS — two-pass architectural analysis:",
        "",
        full_result,
        "",
        "Stored as backlog item. Use 'workflow_status kind=backlog' to review.",
    ])


def score_stub(assessor: "Assessor", args: dict) -> str:
    """
    score_stub(symbol) - evaluate how central a stub is to making the system runnable.
    Chains gather_context() -> build claim -> evaluate_claim() kernel.
    Returns verdict, confidence, and reasoning as a priority score.
    """
    symbol = args.get("symbol", "").strip()
    if not symbol:
        return "ERROR: symbol argument required"

    from determined.agent.stub_projector import gather_context
    from determined.agent.evaluator import evaluate, retrieve_evidence, collect_symbol_context

    oracle = assessor.oracle
    conn = oracle.conn

    # Structural rank: caller count
    caller_count_row = conn.execute(
        """
        SELECT COUNT(DISTINCT ge.caller)
        FROM graph_edges ge
        WHERE ge.callee = ? OR ge.callee LIKE '%.' || ?
        """,
        (symbol, symbol),
    ).fetchone()
    caller_count = caller_count_row[0] if caller_count_row else 0

    # Build claim from stub context
    ctx = gather_context(conn, symbol)
    if ctx is None:
        return f"'{symbol}' not found in corpus or is not a stub"

    stub = ctx["stub"]
    caller_names = [c["caller"] for c in ctx["callers"] if c["caller"]]
    claim = collect_symbol_context(conn, symbol)

    # Evidence from design notes
    evidence = retrieve_evidence(claim, conn, surfaces=["design_note"], top_n=4)
    if not evidence:
        # Fall back to structural score only
        return (
            f"score_stub: '{symbol}'\n"
            f"  Structural rank: {caller_count} callers\n"
            f"  Semantic score: N/A (no design_note evidence; run ingest_design_docs first)\n"
            f"  Called by: {', '.join(caller_names[:5]) or '(none)'}"
        )

    question = "how central is implementing this stub to making the system runnable and unblocking its callers?"
    judgment = evaluate(claim, evidence, question)

    # Auto-waypoint: pin high-value stubs so they surface in the Pins tab
    if judgment.verdict not in {"UNRELATED", "UNCERTAIN"}:
        try:
            import json as _json
            from determined.intent.knowledge_artifact import add_artifact as _add_artifact
            k_conn = assessor._knowledge_conn
            if k_conn is not None:
                _add_artifact(k_conn, subject=symbol, kind="waypoint", content=_json.dumps({
                    "name": symbol,
                    "view_origin": "score_stub",
                    "note": f"{judgment.verdict} ({int(judgment.confidence*100)}%) — {judgment.reasoning}",
                    "verdict": judgment.verdict,
                    "confidence": judgment.confidence,
                    "callers": caller_count,
                    "trail": [],
                }), provenance="ai-generated")
        except Exception:
            pass  # waypoint creation is best-effort

    return (
        f"score_stub: '{symbol}'\n"
        f"  Structural rank:  {caller_count} callers\n"
        f"  Semantic verdict: {judgment.verdict}  ({int(judgment.confidence * 100)}%)\n"
        f"  Reasoning:        {judgment.reasoning}\n"
        f"  Called by: {', '.join(caller_names[:5]) or '(none)'}\n"
        f"  File: {stub.get('file_path', '?')} line {stub.get('line_number', '?')}"
    )


def reason_about(assessor: "Assessor", args: dict) -> str:
    """
    reason_about(question, symbol?) - AI-assisted architectural decision pipeline.
    Decomposes the question into sub-questions, answers each (DB or evaluate()),
    then synthesizes a recommendation with confidence and provenance.
    Uses Qwen3-8B for decomposition, synthesis, and sub-evaluations.
    May take 60-120 seconds when the quality tier is cold.
    """
    question = args.get("question", "").strip()
    symbol = args.get("symbol", "").strip()
    if not question:
        return "ERROR: question argument required"

    from determined.agent.reasoning_engine import reason_about as _reason_about
    conn = assessor.oracle.conn
    k_conn = getattr(assessor, "_knowledge_conn", None)
    return _reason_about(question, symbol, conn, knowledge_conn=k_conn)


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

    # Re-distill ALL rows with content — overwrites stale cached values from old prompt
    pending = corpus_conn.execute(
        "SELECT id, subject, content FROM semantic_summaries "
        "WHERE content IS NOT NULL"
    ).fetchall()

    if not pending:
        return (
            "semantic_summaries table is empty. "
            "Re-ingest with --summarize to populate it, then run distill_corpus."
        )

    import pathlib
    project_root = pathlib.Path(assessor.oracle.get_project_root())

    stored = 0
    for row_id, subject, content in pending:
        # Prefer source skeleton from disk over stored (possibly stale) content
        src_path = project_root / subject.replace("/", "\\")
        if src_path.exists():
            try:
                source = src_path.read_text(encoding="utf-8", errors="replace")
                input_text = _source_skeleton(source)
            except Exception:
                input_text = content
        else:
            input_text = content
        sentence = _distill_to_one_sentence(input_text, subject, conn=None)
        if sentence is None:
            return f"ERROR: llama-server stopped responding mid-run after {stored} stored."
        corpus_conn.execute(
            "UPDATE semantic_summaries SET distilled = ? WHERE id = ?",
            (sentence, row_id),
        )
        corpus_conn.commit()
        stored += 1

    return f"distill_corpus: {stored} distilled (all refreshed)"


def search_web(assessor: "Assessor", args: dict) -> str:
    """
    Search the web via a local SearXNG instance.

    args:
      query  -- search query string (required)
      n      -- max results to return (default 5, max 10)

    Returns formatted text with titles, URLs, and snippets.
    Returns a "not configured" message if SEARXNG_URL is None or SearXNG is unreachable.
    """
    import determined.agent.llm_client as _llm_cfg
    import requests as _req

    base_url = _llm_cfg.SEARXNG_URL
    if not base_url:
        return "web search not configured (set SEARXNG_URL in llm_client.py)"

    query = (args.get("query") or "").strip()
    if not query:
        return "ERROR: search_web requires query"

    n = min(int(args.get("n", _llm_cfg.SEARXNG_MAX_RESULTS)), 10)

    try:
        resp = _req.get(
            f"{base_url.rstrip('/')}/search",
            params={"q": query, "format": "json", "categories": "general"},
            timeout=_llm_cfg.SEARXNG_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return f"web search unavailable: {exc}"

    results = data.get("results", [])[:n]
    if not results:
        return f"search_web: no results for '{query}'"

    lines = [f"WEB SEARCH: {query}\n"]
    for i, r in enumerate(results, 1):
        title   = r.get("title", "").strip()
        url     = r.get("url", "").strip()
        snippet = r.get("content", "").strip()
        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        if snippet:
            lines.append(f"   {snippet[:200]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def edit_file(assessor: "Assessor", args: dict) -> str:
    """
    Read, write, or patch a file within the project root.

    Operations (args["op"]):
      read_file       -- return file content as a string
      write_file      -- overwrite the file with args["content"]
      replace_in_file -- replace first occurrence of args["old"] with args["new"]

    All paths are validated against the project root to prevent writes outside
    the corpus. Relative paths are resolved from the project root.
    """
    import pathlib

    op = args.get("op", "").strip()
    file_path = (args.get("file_path") or "").strip()
    if not file_path:
        return "ERROR: edit_file requires file_path"
    if op not in ("read_file", "write_file", "replace_in_file"):
        return "ERROR: op must be read_file, write_file, or replace_in_file"

    root = pathlib.Path(assessor.oracle.get_project_root()).resolve()
    fp = pathlib.Path(file_path)
    if not fp.is_absolute():
        fp = root / fp
    try:
        fp.resolve().relative_to(root)
    except ValueError:
        return f"ERROR: path outside project root ({root})"

    if op == "read_file":
        if not fp.exists():
            return f"ERROR: file not found: {fp}"
        return fp.read_text(encoding="utf-8")

    if op == "write_file":
        content = args.get("content")
        if content is None:
            return "ERROR: write_file requires content"
        fp.write_text(content, encoding="utf-8")
        return f"write_file: wrote {len(content)} chars to {fp}"

    if op == "replace_in_file":
        old = args.get("old")
        new = args.get("new")
        if old is None or new is None:
            return "ERROR: replace_in_file requires old and new"
        if not fp.exists():
            return f"ERROR: file not found: {fp}"
        original = fp.read_text(encoding="utf-8")
        if old not in original:
            return f"ERROR: old string not found in {fp}"
        updated = original.replace(old, new, 1)
        fp.write_text(updated, encoding="utf-8")
        return f"replace_in_file: replaced 1 occurrence in {fp}"

    return "ERROR: unknown op"


# ------------------------------------------------------------------
# FEATURE SHAPE TOOLS (RM59)
# ------------------------------------------------------------------

def list_features(oracle: "DBOracle", args: dict) -> str:
    """
    list_features([depth=1][, scope]) - directory-first feature grouping.

    Groups functions by the first `depth` path segments of their file_path.
    Returns each feature directory with: symbol count, stub count, entry point
    count (symbols called from outside the directory), cross-feature edge count.
    Ranked by entry point count descending (most externally visible first).
    """
    depth = int(args.get("depth", 1))
    scope = args.get("scope", "").strip().replace("\\", "/").rstrip("/")
    conn = oracle.conn

    rows = conn.execute(
        "SELECT REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') as fp, "
        "name, is_stub FROM functions"
    ).fetchall()

    if not rows:
        return "No functions found in corpus."

    from collections import defaultdict

    def _dir_key(fp: str, d: int) -> str:
        parts = fp.split("/")
        return "/".join(parts[:d]) if len(parts) > 1 else parts[0]

    # Group symbols by feature directory
    feat_symbols: dict[str, set] = defaultdict(set)
    feat_stubs: dict[str, int] = defaultdict(int)
    for fp, name, is_stub in rows:
        key = _dir_key(fp, depth)
        if scope and not key.startswith(scope):
            continue
        feat_symbols[key].add(name)
        if is_stub:
            feat_stubs[key] += 1

    if not feat_symbols:
        return f"No features found (depth={depth}" + (f", scope={scope}" if scope else "") + ")."

    # Entry points: local symbols called by callers outside the directory.
    # Derive caller's directory from the functions table (graph_edges has no caller_file column).
    feat_entry_points: dict[str, int] = defaultdict(int)
    feat_cross_edges: dict[str, int] = defaultdict(int)

    caller_fp_map = {name: fp for fp, name, _ in rows}
    for caller, callee in conn.execute("SELECT caller, callee FROM graph_edges").fetchall():
        caller_fp = caller_fp_map.get(caller, "").replace("\\", "/")
        caller_key = _dir_key(caller_fp, depth) if caller_fp else ""
        for feat, syms in feat_symbols.items():
            if callee in syms and caller_key != feat:
                feat_entry_points[feat] += 1
                feat_cross_edges[feat] += 1

    # Build output ranked by entry points desc, then symbol count desc
    features = sorted(
        feat_symbols.keys(),
        key=lambda f: (-feat_entry_points[f], -len(feat_symbols[f]))
    )

    lines = [f"Features (depth={depth}" + (f", scope={scope}" if scope else "") + "):"]
    lines.append(f"{'Directory':<40} {'Syms':>5} {'Stubs':>5} {'EntryPts':>8} {'CrossEdges':>10}")
    lines.append("-" * 72)
    for feat in features:
        lines.append(
            f"{feat:<40} {len(feat_symbols[feat]):>5} {feat_stubs[feat]:>5} "
            f"{feat_entry_points[feat]:>8} {feat_cross_edges[feat]:>10}"
        )
    return "\n".join(lines)


def feature_shape(oracle: "DBOracle", args: dict) -> str:
    """
    feature_shape(feature_path) - trace the call path through a feature directory.

    Identifies entry points (local symbols with external callers), then traces
    forward through the call graph. Each node is annotated:
      - implemented: has a functions row and is_stub=0
      - stub: has a functions row and is_stub=1
      - missing: appears in graph_edges as callee but has no functions row (external)
    Cross-feature edges are flagged. Returns a structured path summary.
    """
    feature_path = args.get("feature_path", "").strip().replace("\\", "/").rstrip("/")
    if not feature_path:
        return "ERROR: feature_path is required."

    conn = oracle.conn
    norm_path = feature_path + "/"

    # All local symbols
    local_rows = conn.execute(
        "SELECT name, is_stub, REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') as fp "
        "FROM functions WHERE REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') LIKE ?",
        (norm_path + "%",),
    ).fetchall()

    if not local_rows:
        return f"No symbols found under '{feature_path}'."

    local_symbols: dict[str, dict] = {}
    for name, is_stub, fp in local_rows:
        local_symbols[name] = {"is_stub": bool(is_stub), "file": fp}

    # All symbol names in the entire corpus (for missing-node detection)
    all_known = {r[0] for r in conn.execute("SELECT name FROM functions").fetchall()}

    # Entry points: local symbols called by callers outside this directory
    entry_points: set[str] = set()
    caller_rows = conn.execute(
        "SELECT caller, callee FROM graph_edges WHERE callee IN ({})".format(
            ",".join("?" * len(local_symbols))
        ),
        list(local_symbols.keys()),
    ).fetchall()

    for caller, callee in caller_rows:
        # Determine if caller is outside the feature
        caller_row = conn.execute(
            "SELECT REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') FROM functions WHERE name = ?",
            (caller,),
        ).fetchone()
        if caller_row is None or not caller_row[0].startswith(norm_path):
            entry_points.add(callee)

    if not entry_points:
        # No external callers -- treat all local symbols as entry points
        entry_points = set(local_symbols.keys())
        ep_note = " (no external callers; showing all local symbols as roots)"
    else:
        ep_note = ""

    # Forward walk from entry points (BFS, stop at cross-feature boundary)
    from collections import deque

    visited_nodes: set[str] = set()
    node_status: dict[str, str] = {}
    cross_feature_edges: list[tuple] = []
    internal_edges: list[tuple] = []

    queue: deque = deque(entry_points)
    for ep in entry_points:
        visited_nodes.add(ep)
        node_status[ep] = "stub" if local_symbols[ep]["is_stub"] else "implemented"

    while queue:
        node = queue.popleft()
        callee_rows = conn.execute(
            "SELECT callee FROM graph_edges WHERE caller = ?", (node,)
        ).fetchall()
        for (callee,) in callee_rows:
            is_local = callee in local_symbols
            if is_local:
                internal_edges.append((node, callee))
                if callee not in visited_nodes:
                    visited_nodes.add(callee)
                    node_status[callee] = "stub" if local_symbols[callee]["is_stub"] else "implemented"
                    queue.append(callee)
            else:
                if callee in all_known:
                    cross_feature_edges.append((node, callee, "cross-feature"))
                else:
                    cross_feature_edges.append((node, callee, "external"))

    # Summary stats
    impl_count = sum(1 for s in node_status.values() if s == "implemented")
    stub_count = sum(1 for s in node_status.values() if s == "stub")
    total = len(node_status)
    completeness = f"{impl_count / total * 100:.0f}%" if total else "N/A"

    lines = [f"Feature shape: {feature_path}{ep_note}"]
    lines.append(f"  Symbols: {total} total, {impl_count} implemented, {stub_count} stub")
    lines.append(f"  Completeness: {completeness}  |  Entry points: {len(entry_points)}")
    lines.append("")

    lines.append("Entry points:")
    for ep in sorted(entry_points):
        status = node_status.get(ep, "?")
        lines.append(f"  [{status}] {ep}")

    if internal_edges:
        lines.append("")
        lines.append("Internal call edges:")
        for src, dst in sorted(internal_edges):
            dst_status = node_status.get(dst, "?")
            lines.append(f"  {src} -> [{dst_status}] {dst}")

    if cross_feature_edges:
        lines.append("")
        lines.append("Cross-feature / external edges:")
        for src, dst, kind in sorted(cross_feature_edges):
            lines.append(f"  {src} -> {dst}  ({kind})")

    stubs = [n for n, s in node_status.items() if s == "stub"]
    if stubs:
        lines.append("")
        lines.append(f"Blocking stubs ({len(stubs)}):")
        for s in sorted(stubs):
            lines.append(f"  {s}")

    return "\n".join(lines)


def development_priorities(oracle: "DBOracle", args: dict) -> str:
    """
    development_priorities([scope][, top_n=10][, depth=1]) — ranked feature priority table.

    For each feature directory:
      completeness = implemented / (implemented + stub + missing_local)
        where missing_local = callees of local symbols that have no functions row
                              (external/unresolved are excluded from the count)
      priority_score = (1 - completeness) * entry_point_caller_count
    Cross-feature blockers (local stubs called by other features) rank above
    self-contained gaps at the same priority score.
    Flags features that lack any design_note coverage in knowledge_artifacts.
    """
    from collections import defaultdict

    top_n = int(args.get("top_n", 10))
    depth = int(args.get("depth", 1))
    scope = args.get("scope", "").strip().replace("\\", "/").rstrip("/")
    conn = oracle.conn

    # --- 1. Load all symbols grouped by feature directory ---
    sym_rows = conn.execute(
        "SELECT name, is_stub, "
        "REPLACE(REPLACE(file_path, '\\', '/'), '\\\\', '/') as fp "
        "FROM functions"
    ).fetchall()

    if not sym_rows:
        return "No functions found in corpus."

    def _dir_key(fp: str) -> str:
        parts = fp.split("/")
        return "/".join(parts[:depth]) if len(parts) > 1 else parts[0]

    # sym_info: name -> {feat, is_stub}
    sym_info: dict[str, dict] = {}
    feat_impl: dict[str, int] = defaultdict(int)
    feat_stub: dict[str, int] = defaultdict(int)
    all_known: set[str] = set()

    for name, is_stub, fp in sym_rows:
        key = _dir_key(fp)
        if scope and not key.startswith(scope):
            continue
        sym_info[name] = {"feat": key, "is_stub": bool(is_stub)}
        all_known.add(name)
        if is_stub:
            feat_stub[key] += 1
        else:
            feat_impl[key] += 1

    if not sym_info:
        return "No features found" + (f" under scope '{scope}'" if scope else "") + "."

    all_features = set(feat_impl.keys()) | set(feat_stub.keys())

    # --- 2. Load all edges once ---
    edge_rows = conn.execute("SELECT caller, callee FROM graph_edges").fetchall()

    # --- 3. Compute per-feature metrics from edges ---
    # entry_point_callers: count of edges where callee is in feature AND caller is from different feature
    feat_ep_callers: dict[str, int] = defaultdict(int)
    # missing_callees: callees of local symbols that don't appear in functions table
    feat_missing: dict[str, set] = defaultdict(set)
    # stub_caller_count: for each stub, how many callers it has from OTHER features
    stub_cross_callers: dict[str, int] = defaultdict(int)

    for caller, callee in edge_rows:
        caller_info = sym_info.get(caller)
        callee_info = sym_info.get(callee)

        # Entry point: callee in a feature, caller from a different feature
        if callee_info and caller_info and caller_info["feat"] != callee_info["feat"]:
            feat_ep_callers[callee_info["feat"]] += 1

        # Missing: caller is local, callee not in functions table at all
        if caller_info and callee not in all_known:
            feat_missing[caller_info["feat"]].add(callee)

        # Cross-feature blocker: callee is a stub in a different feature than caller
        if (callee_info and callee_info["is_stub"]
                and caller_info and caller_info["feat"] != callee_info["feat"]):
            stub_cross_callers[callee] += 1

    # --- 4. Cross-feature blocker flag per feature ---
    # A feature is a cross-feature blocker if any of its stubs are called from outside
    feat_is_blocker: dict[str, bool] = defaultdict(bool)
    for stub_name, count in stub_cross_callers.items():
        if count > 0 and stub_name in sym_info:
            feat = sym_info[stub_name]["feat"]
            feat_is_blocker[feat] = True

    # --- 5. Compute scores ---
    # best blocking stub per feature = the local stub with most cross-feature callers
    feat_blocking_stub: dict[str, str] = {}
    for stub_name in stub_cross_callers:
        if stub_name in sym_info:
            feat = sym_info[stub_name]["feat"]
            prev = feat_blocking_stub.get(feat)
            if prev is None or stub_cross_callers[stub_name] > stub_cross_callers.get(prev, 0):
                feat_blocking_stub[feat] = stub_name
    # fallback: most-stubbed feature gets any stub as blocking node
    for feat in all_features:
        if feat not in feat_blocking_stub and feat_stub[feat] > 0:
            # pick alphabetically-first stub in this feature
            stubs_in_feat = [n for n, info in sym_info.items()
                             if info["feat"] == feat and info["is_stub"]]
            if stubs_in_feat:
                feat_blocking_stub[feat] = sorted(stubs_in_feat)[0]

    # --- 6. Design doc coverage ---
    design_feats: set[str] = set()
    try:
        da_rows = conn.execute(
            "SELECT content FROM knowledge_artifacts WHERE kind='design_note'"
        ).fetchall()
        for (content,) in da_rows:
            if content:
                for feat in all_features:
                    if feat.split("/")[-1] in content or feat in content:
                        design_feats.add(feat)
    except Exception:
        pass  # knowledge_artifacts may not exist in test DBs

    # --- 7. Rank features ---
    records = []
    for feat in all_features:
        impl = feat_impl[feat]
        stub = feat_stub[feat]
        missing = len(feat_missing[feat])
        total = impl + stub + missing
        completeness = impl / total if total > 0 else 1.0
        ep = feat_ep_callers[feat]
        priority = (1.0 - completeness) * ep
        records.append({
            "feat": feat,
            "impl": impl,
            "stub": stub,
            "missing": missing,
            "completeness": completeness,
            "ep": ep,
            "priority": priority,
            "is_blocker": feat_is_blocker[feat],
            "has_docs": feat in design_feats,
            "blocking_stub": feat_blocking_stub.get(feat, "-"),
        })

    # Sort: cross-feature blockers first at same priority, then by priority desc, completeness asc
    records.sort(key=lambda r: (-r["priority"], -r["is_blocker"], r["completeness"]))

    # Only features with stubs or missing nodes are worth surfacing in priority list
    actionable = [r for r in records if r["stub"] > 0 or r["missing"] > 0]
    top = actionable[:top_n]

    if not top:
        return "No incomplete features found" + (f" under scope '{scope}'" if scope else "") + "."

    lines = ["Development priorities" + (f" (scope={scope})" if scope else "")
             + f", depth={depth}, top {len(top)} of {len(actionable)} incomplete:"]
    lines.append("")
    hdr = f"{'Feature':<35} {'Done%':>5} {'Stubs':>5} {'Miss':>4} {'EP':>4} {'Score':>6}  {'Flags'}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for r in top:
        flags = []
        if r["is_blocker"]:
            flags.append("BLOCKER")
        if not r["has_docs"]:
            flags.append("no-docs")
        flag_str = " ".join(flags)
        lines.append(
            f"{r['feat']:<35} {r['completeness']*100:>4.0f}% {r['stub']:>5} {r['missing']:>4} "
            f"{r['ep']:>4} {r['priority']:>6.1f}  {flag_str}"
        )
        if r["blocking_stub"] != "-":
            lines.append(f"  -> blocking stub: {r['blocking_stub']}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# RECONCILIATION TOOLS (RM19)
# ------------------------------------------------------------------

def find_duplicates(assessor: "Assessor", args: dict) -> str:
    """
    find_duplicates([threshold][, clear]) - find near-duplicate functions by
    embedding similarity. Embeds "{name}: {docstring}" for every function that
    has a docstring, computes pairwise cosine similarity, and surfaces pairs
    above threshold (default 0.85). Stores each pair as a reconciliation_finding
    artifact. Idempotent: skips pairs already stored.

    Args:
        threshold  - float 0-1, similarity cutoff (default 0.85)
        clear      - bool, delete existing reconciliation_finding artifacts first
        limit      - max functions to embed (default 2000)
    """
    import json as _json
    from determined.intent.knowledge_artifact import add_artifact, list_artifacts

    oracle = assessor.oracle
    conn = oracle.conn

    threshold = float(args.get("threshold", 0.85))
    clear = args.get("clear", False)
    limit = int(args.get("limit", 2000))

    if clear:
        conn.execute("DELETE FROM knowledge_artifacts WHERE kind = 'reconciliation_finding'")
        conn.commit()

    # Load all functions with non-null, non-empty docstrings
    rows = conn.execute(
        """
        SELECT name, file_path, docstring
        FROM functions
        WHERE docstring IS NOT NULL AND trim(docstring) != ''
        ORDER BY file_path, name
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    if len(rows) < 2:
        return "find_duplicates: fewer than 2 functions with docstrings — nothing to compare"

    names = [r[0] for r in rows]
    files = [r[1] for r in rows]
    texts = [f"{r[0]}: {r[2][:400]}" for r in rows]   # cap docstring at 400 chars

    model = _get_embed_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    # normalized => cosine similarity = dot product
    sim_matrix = embeddings @ embeddings.T

    # Collect existing artifact subjects to skip duplicates
    existing_subjects: set[str] = set()
    for art in list_artifacts(conn, kind="reconciliation_finding"):
        existing_subjects.add(art["subject"])

    pairs: list[tuple[float, str, str, str, str]] = []   # (score, nameA, fileA, nameB, fileB)
    stored = 0
    skipped = 0
    n = len(rows)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim_matrix[i, j])
            if score < threshold:
                continue
            # Skip exact-same symbol in same file (a function compared to itself can't
            # happen since i != j, but two entries with identical name+file can exist
            # if the DB has duplicates -- guard anyway)
            if names[i] == names[j] and files[i] == files[j]:
                continue
            # Canonical subject: alphabetically sorted pair so A::B and B::A collapse
            key_a = f"{names[i]}@{files[i]}"
            key_b = f"{names[j]}@{files[j]}"
            if key_a > key_b:
                key_a, key_b = key_b, key_a
            subject = f"duplicate::{key_a}::{key_b}"
            if subject in existing_subjects:
                skipped += 1
                continue
            content = _json.dumps({
                "symbol_a": names[i],
                "file_a": files[i],
                "symbol_b": names[j],
                "file_b": files[j],
                "score": round(score, 4),
            })
            add_artifact(conn, subject, "reconciliation_finding", content,
                         provenance="ai-generated")
            existing_subjects.add(subject)
            stored += 1
            pairs.append((score, names[i], files[i], names[j], files[j]))

    if not pairs and skipped == 0:
        return (
            f"find_duplicates: no pairs above threshold {threshold:.2f} "
            f"({n} functions scanned)"
        )

    # Sort by descending similarity for display
    pairs.sort(key=lambda p: p[0], reverse=True)

    lines = [
        f"find_duplicates: {n} functions scanned, threshold={threshold:.2f}",
        f"  {stored} new pairs stored, {skipped} already recorded",
        "",
    ]
    if pairs:
        lines.append(f"New candidate pairs ({len(pairs)}):")
        for score, na, fa, nb, fb in pairs[:50]:   # cap display at 50
            fa_short = fa.replace("\\", "/").split("/")[-1]
            fb_short = fb.replace("\\", "/").split("/")[-1]
            lines.append(f"  [{score:.3f}] {na} ({fa_short})  ~  {nb} ({fb_short})")
        if len(pairs) > 50:
            lines.append(f"  ... and {len(pairs) - 50} more (all stored as artifacts)")
    elif skipped:
        lines.append(f"All {skipped} pairs were already recorded. Use clear=True to rescan.")

    return "\n".join(lines)


_DIVERGENCE_TAXONOMY = [
    "accidental copy",
    "historical evolution",
    "performance optimization",
    "platform-specific behavior",
    "security reason",
    "genuinely different abstraction",
]


def _build_classify_prompt(
    name_a: str, file_a: str, doc_a: str,
    callers_a: list[str], callees_a: list[str],
    name_b: str, file_b: str, doc_b: str,
    callers_b: list[str], callees_b: list[str],
    score: float,
) -> list[dict]:
    taxonomy_str = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(_DIVERGENCE_TAXONOMY))
    callers_a_str = ", ".join(callers_a[:8]) or "none"
    callees_a_str = ", ".join(callees_a[:8]) or "none"
    callers_b_str = ", ".join(callers_b[:8]) or "none"
    callees_b_str = ", ".join(callees_b[:8]) or "none"
    fa_short = file_a.replace("\\", "/").split("/")[-1]
    fb_short = file_b.replace("\\", "/").split("/")[-1]

    user_msg = f"""Two functions have a docstring similarity score of {score:.3f} (1.0 = identical).

Function A: {name_a}  (file: {fa_short})
Docstring: {doc_a[:600]}
Called by: {callers_a_str}
Calls:     {callees_a_str}

Function B: {name_b}  (file: {fb_short})
Docstring: {doc_b[:600]}
Called by: {callers_b_str}
Calls:     {callees_b_str}

Taxonomy of divergence reasons:
{taxonomy_str}

Choose the single best reason from the taxonomy above that explains why these two functions \
exist separately rather than being merged. Reply with ONLY a JSON object in this exact format:
{{"reason": "<taxonomy label>", "confidence": "<high|medium|low>", "explanation": "<one sentence>"}}"""

    return [
        {
            "role": "system",
            "content": (
                "You are a code analysis assistant. "
                "Your job is to classify why two similar functions diverged. "
                "Reply only with the requested JSON object, no other text."
            ),
        },
        {"role": "user", "content": user_msg},
    ]


def classify_duplicates(assessor: "Assessor", args: dict) -> str:
    """
    classify_duplicates([subject][, limit]) - for each stored reconciliation_finding
    pair (from find_duplicates), feed both docstrings and call-graph context to
    Qwen3-8B and classify the divergence reason from a fixed taxonomy:
      - accidental copy
      - historical evolution
      - performance optimization
      - platform-specific behavior
      - security reason
      - genuinely different abstraction
    Stores each classification as a new reconciliation_finding artifact with
    subject "classified::{key_a}::{key_b}". Skips pairs already classified.

    Args:
        subject - (optional) classify only this specific "duplicate::" subject
        limit   - max pairs to classify in one run (default 50)
    """
    import json as _json
    from determined.intent.knowledge_artifact import add_artifact, list_artifacts
    from determined.agent import llm_client

    oracle = assessor.oracle
    conn = oracle.conn
    subject_filter = args.get("subject")
    limit = int(args.get("limit", 50))

    # Collect all classified subjects so we can skip
    existing_classified: set[str] = set()
    for art in list_artifacts(conn, kind="reconciliation_finding"):
        if art["subject"].startswith("classified::"):
            existing_classified.add(art["subject"])

    # Load unclassified duplicate pairs
    pairs_rows = conn.execute(
        """
        SELECT subject, content FROM knowledge_artifacts
        WHERE kind = 'reconciliation_finding'
          AND subject LIKE 'duplicate::%'
        ORDER BY created_at DESC
        """
    ).fetchall()

    to_classify = []
    for (subj, content) in pairs_rows:
        if subject_filter and subj != subject_filter:
            continue
        classified_key = "classified::" + subj[len("duplicate::"):]
        if classified_key in existing_classified:
            continue
        try:
            d = _json.loads(content)
        except Exception:
            continue
        to_classify.append((subj, classified_key, d))
        if len(to_classify) >= limit:
            break

    if not to_classify:
        return "classify_duplicates: all pairs already classified (or no pairs found; run find_duplicates first)"

    # Fetch docstrings for fast lookup
    func_cache: dict[tuple[str, str], str] = {}

    def _get_docstring(name: str, file_path: str) -> str:
        key = (name, file_path)
        if key not in func_cache:
            row = conn.execute(
                "SELECT docstring FROM functions WHERE name = ? AND file_path = ? LIMIT 1",
                (name, file_path),
            ).fetchone()
            func_cache[key] = (row[0] or "") if row else ""
        return func_cache[key]

    classified = 0
    skipped_llm = 0
    results: list[str] = []

    for (orig_subject, classified_key, d) in to_classify:
        name_a, file_a = d["symbol_a"], d["file_a"]
        name_b, file_b = d["symbol_b"], d["file_b"]
        score = d.get("score", 0.0)

        doc_a = _get_docstring(name_a, file_a)
        doc_b = _get_docstring(name_b, file_b)

        callers_a = [r["caller"] for r in _list_callers_raw(oracle, name_a)]
        callees_a = [r["callee"] for r in _list_callees_raw(oracle, name_a)]
        callers_b = [r["caller"] for r in _list_callers_raw(oracle, name_b)]
        callees_b = [r["callee"] for r in _list_callees_raw(oracle, name_b)]

        messages = _build_classify_prompt(
            name_a, file_a, doc_a, callers_a, callees_a,
            name_b, file_b, doc_b, callers_b, callees_b,
            score,
        )

        raw = llm_client.chat(messages, max_tokens=200)
        if not raw:
            skipped_llm += 1
            continue

        # Parse LLM response — extract JSON even if surrounded by prose
        reason = "unknown"
        confidence = "low"
        explanation = raw.strip()
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            parsed = _json.loads(raw[start:end])
            reason = parsed.get("reason", "unknown")
            confidence = parsed.get("confidence", "low")
            explanation = parsed.get("explanation", raw.strip())
            # Canonicalize reason to taxonomy — also handle numeric responses like "6"
            reason_lower = reason.strip().lower()
            try:
                idx = int(reason_lower) - 1
                if 0 <= idx < len(_DIVERGENCE_TAXONOMY):
                    reason = _DIVERGENCE_TAXONOMY[idx]
            except (ValueError, TypeError):
                for t in _DIVERGENCE_TAXONOMY:
                    if t in reason_lower or reason_lower in t:
                        reason = t
                        break
        except (ValueError, _json.JSONDecodeError):
            pass

        content_out = _json.dumps({
            "symbol_a": name_a,
            "file_a": file_a,
            "symbol_b": name_b,
            "file_b": file_b,
            "score": score,
            "reason": reason,
            "confidence": confidence,
            "explanation": explanation,
        })
        add_artifact(conn, classified_key, "reconciliation_finding", content_out,
                     provenance="ai-generated")
        existing_classified.add(classified_key)
        classified += 1

        fa_short = file_a.replace("\\", "/").split("/")[-1]
        fb_short = file_b.replace("\\", "/").split("/")[-1]
        results.append(
            f"  [{score:.3f}] {name_a} ({fa_short})  ~  {name_b} ({fb_short})\n"
            f"    reason={reason}  confidence={confidence}\n"
            f"    {explanation}"
        )

    lines = [
        f"classify_duplicates: {classified} pairs classified, "
        f"{skipped_llm} skipped (LLM unavailable)",
        "",
    ]
    if results:
        lines.append("Classifications:")
        lines.extend(results)
    return "\n".join(lines)


def find_primitive_gaps(assessor: "Assessor", args: dict) -> str:
    """
    find_primitive_gaps([min_callers][, limit][, clear]) - mine the call graph for
    repeated callee co-occurrences: pairs of functions that are called together by
    multiple independent callers. A pair (A, B) appearing in N callers with no shared
    helper that wraps both is evidence of a missing primitive.

    Args:
        min_callers - minimum distinct callers sharing the pair (default 3)
        limit       - max pairs to surface (default 30)
        clear       - bool, delete existing primitive_gap artifacts first
    """
    import json as _json
    import builtins as _bi
    from determined.intent.knowledge_artifact import add_artifact, list_artifacts

    oracle = assessor.oracle
    conn = oracle.conn
    min_callers = int(args.get("min_callers", 3))
    limit = int(args.get("limit", 30))
    clear = args.get("clear", False)

    if clear:
        conn.execute("DELETE FROM knowledge_artifacts WHERE kind = 'primitive_gap'")
        conn.commit()

    builtin_names = set(dir(_bi))
    from determined.agent.graph_utils import _has_id_columns
    use_ids = _has_id_columns(conn)

    # For each caller, collect its unique project callees (exclude builtins/externals).
    # Use source_id/target_id (canonical bare names) so FQ callees like "module.fn"
    # are counted under their bare name rather than filtered out.
    if use_ids:
        rows = conn.execute(
            "SELECT DISTINCT source_id, target_id FROM graph_edges ORDER BY source_id"
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT DISTINCT caller, callee FROM graph_edges
            WHERE callee NOT LIKE '%.%'
            ORDER BY caller
            """
        ).fetchall()

    # Group callees by caller
    caller_to_callees: dict[str, list[str]] = {}
    for caller, callee in rows:
        if callee in builtin_names:
            continue
        caller_to_callees.setdefault(caller, []).append(callee)

    # Count how many distinct callers share each (callee_a, callee_b) pair
    pair_callers: dict[tuple[str, str], list[str]] = {}
    for caller, callees in caller_to_callees.items():
        uniq = sorted(set(callees))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                pair = (uniq[i], uniq[j])
                pair_callers.setdefault(pair, []).append(caller)

    # Filter to pairs meeting min_callers threshold
    candidates = [
        (len(callers), pair, callers)
        for pair, callers in pair_callers.items()
        if len(callers) >= min_callers
    ]
    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:limit]

    if not candidates:
        return (
            f"find_primitive_gaps: no callee pairs found with >= {min_callers} "
            f"shared callers. Try lowering min_callers."
        )

    # Load existing subjects to skip already-stored pairs
    existing: set[str] = set()
    for art in list_artifacts(conn, kind="primitive_gap"):
        existing.add(art["subject"])

    stored = 0
    skipped = 0
    lines = [
        f"find_primitive_gaps: {len(caller_to_callees)} callers scanned, "
        f"min_callers={min_callers}",
        f"  {len(candidates)} patterns surfaced",
        "",
        "Top callee co-occurrence patterns (potential missing primitives):",
    ]

    for count, (a, b), callers in candidates:
        subject = f"primitive_gap::{a}::{b}"
        caller_sample = callers[:5]
        content = _json.dumps({
            "callee_a": a,
            "callee_b": b,
            "caller_count": count,
            "callers_sample": caller_sample,
        })
        if subject not in existing:
            add_artifact(conn, subject, "primitive_gap", content, provenance="ai-generated")
            existing.add(subject)
            stored += 1
        else:
            skipped += 1

        sample_str = ", ".join(caller_sample)
        if len(callers) > 5:
            sample_str += f" (+{len(callers) - 5} more)"
        lines.append(f"  [{count} callers] {a}  +  {b}")
        lines.append(f"    called together by: {sample_str}")

    lines.append("")
    lines.append(f"  {stored} new patterns stored, {skipped} already recorded")
    return "\n".join(lines)


def list_reconciliation_findings(assessor: "Assessor", args: dict) -> str:
    """
    list_reconciliation_findings([min_score][, limit]) - show stored duplicate pairs.
    Args:
        min_score - only show pairs with score >= this (default 0.0 = all)
        limit     - max pairs to show (default 100)
    """
    import json as _json

    oracle = assessor.oracle
    conn = oracle.conn
    min_score = float(args.get("min_score", 0.0))
    limit = int(args.get("limit", 100))

    rows = conn.execute(
        """
        SELECT content FROM knowledge_artifacts
        WHERE kind = 'reconciliation_finding'
        ORDER BY created_at DESC
        """
    ).fetchall()

    pairs = []
    for (content,) in rows:
        try:
            d = _json.loads(content)
            if d.get("score", 0.0) >= min_score:
                pairs.append(d)
        except Exception:
            pass

    if not pairs:
        return "list_reconciliation_findings: no pairs recorded (run find_duplicates first)"

    pairs.sort(key=lambda d: d.get("score", 0.0), reverse=True)
    pairs = pairs[:limit]

    lines = [f"Reconciliation findings ({len(pairs)} pairs, min_score={min_score:.2f}):"]
    for d in pairs:
        fa_short = d["file_a"].replace("\\", "/").split("/")[-1]
        fb_short = d["file_b"].replace("\\", "/").split("/")[-1]
        lines.append(
            f"  [{d['score']:.3f}] {d['symbol_a']} ({fa_short})  ~  {d['symbol_b']} ({fb_short})"
        )
    return "\n".join(lines)


TOOLS = {
    "search_symbols":    (search_symbols,    "oracle"),
    "search_files":      (search_files,      "oracle"),
    "list_callers":      (list_callers,      "oracle"),
    "blast_radius":      (blast_radius,      "oracle"),
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
    "find_abc_gaps":        (find_abc_gaps,         "oracle"),
    "detect_topology":      (detect_topology,       "oracle"),
    "frontier_coverage":    (frontier_coverage,     "oracle"),
    "find_orphaned_impls":      (find_orphaned_impls,       "oracle"),
    "frontier_priority":        (frontier_priority,         "oracle"),
    "implementation_order":     (implementation_order,      "oracle"),
    "find_conditional_stubs":   (find_conditional_stubs,    "oracle"),
    "project_stub":         (project_stub,          "oracle"),
    "scaffold_from_pattern":    (scaffold_from_pattern,     "assessor"),
    "readiness_check":          (readiness_check,           "assessor"),
    "score_stub":           (score_stub,            "assessor"),
    # Doc tools
    "discover_docs":        (discover_docs_tool,    "oracle"),
    "ingest_design_docs":   (ingest_design_docs,    "assessor"),
    # Goal intake
    "goal_intake":          (goal_intake,           "assessor"),
    # Distillation
    "distill_corpus":       (distill_corpus,        "assessor"),
    # Design violation cross-reference and gap detection
    "check_design_violations": (check_design_violations, "assessor"),
    "design_gaps":             (design_gaps,             "assessor"),
    # Data flow edges (return-value argument tracking)
    "data_flow_edges":         (data_flow_edges,         "assessor"),
    # HTTP/HTMX chain tracing
    "trace_http_chain":        (trace_http_chain,        "assessor"),
    # Project-wide synthesis
    "project_status":          (project_status,          "assessor"),
    # Incremental re-ingest
    "reingest_file":           (reingest_file,           "assessor"),
    # Symbol context + concept search (items 21/22)
    "symbol_context":          (symbol_context,          "assessor"),
    "completion_contract":     (completion_contract,     "assessor"),
    "concept_search":          (concept_search,          "assessor"),
    # Docstring health + gap analysis (items 23/24)
    "docstring_health":        (docstring_health,        "assessor"),
    "annotate_function":       (annotate_function,       "assessor"),
    "run_annotation_pass":     (run_annotation_pass,     "assessor"),
    "gap_analysis":            (gap_analysis,            "assessor"),
    # Evaluate kernel + role inference
    "evaluate_claim":          (evaluate_claim,          "assessor"),
    "infer_behavior":          (infer_behavior,          "assessor"),
    "infer_behavior_batch":       (infer_behavior_batch,       "assessor"),
    "match_structural_pattern":   (match_structural_pattern,   "assessor"),
    "trace_data_flow":            (trace_data_flow,            "assessor"),
    # Two-pass architectural synthesis
    "corpus_synthesis":        (corpus_synthesis,        "assessor"),
    # Reasoning pipeline (ANALYSIS_MODEL.md)
    "reason_about":            (reason_about,            "assessor"),
    # Web search (RM12)
    "search_web":              (search_web,              "assessor"),
    # File editing (RM11)
    "edit_file":               (edit_file,               "assessor"),
    # Feature shape analysis (RM59)
    "list_features":                    (list_features,                    "oracle"),
    "feature_shape":                    (feature_shape,                    "oracle"),
    "development_priorities":           (development_priorities,           "oracle"),
    # Reconciliation / duplicate detection (RM19)
    "find_duplicates":                  (find_duplicates,                  "assessor"),
    "list_reconciliation_findings":     (list_reconciliation_findings,     "assessor"),
    "classify_duplicates":              (classify_duplicates,              "assessor"),
    "find_primitive_gaps":              (find_primitive_gaps,              "assessor"),
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
