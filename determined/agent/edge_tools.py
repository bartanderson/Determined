"""
Level-4 (Edge) tools for the Determined analysis agent.

Edges are the atomic unit of the analysis graph. Everything else
(symbols, files, subsystems, systems) is composed from edges.

Tools in this module:
  edges_of(name, direction?, type?)    - all edges touching a symbol or file
  edge_detail(src, dst, type?)         - richest view of one specific connection
  list_import_deps(file_path?)         - resolved project-internal import graph
  add_edge(src, dst, type?, note?)     - manually assert a connection

Module resolution: converts Python module names ("determined.oracle")
to corpus file paths ("determined/oracle/__init__.py") by checking
the corpus files table. Import edges to stdlib/external packages are
flagged as is_internal=False and still shown but clearly labeled.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from determined.agent.edge_types import EdgeRef

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.assessor.knowledge_artifact import KnowledgeArtifact


# ---------------------------------------------------------------------------
# Module resolution
# ---------------------------------------------------------------------------

def _resolve_module_to_file(oracle: "DBOracle", module_name: str) -> Optional[str]:
    """
    Convert a dotted Python module name to a corpus file path.
    Returns the file path if found in the corpus, None if external/stdlib.
    """
    parts = module_name.split(".")
    candidates = [
        "/".join(parts) + ".py",
        "/".join(parts) + "/__init__.py",
    ]
    if len(parts) > 1:
        candidates.append("/".join(parts[:-1]) + ".py")
        candidates.append("/".join(parts[:-1]) + "/__init__.py")

    for candidate in candidates:
        # LIKE match handles Windows vs Unix path separator differences
        rows = oracle.conn.execute(
            "SELECT file_path FROM files WHERE replace(file_path, '\\', '/') LIKE ?",
            (f"%{candidate}",)
        ).fetchall()
        if rows:
            return min(rows, key=lambda r: len(r[0]))[0]
    return None


def _rel(oracle: "DBOracle", path: str) -> str:
    """Return path relative to project root, forward slashes."""
    root = oracle.get_project_root().replace("\\", "/").rstrip("/") + "/"
    return path.replace("\\", "/").replace(root, "")


def _find_file_for_symbol(oracle: "DBOracle", name: str) -> Optional[str]:
    """Look up which file a symbol (function or class) lives in."""
    row = oracle.conn.execute(
        "SELECT file_path FROM functions WHERE name = ? "
        "UNION SELECT file_path FROM classes WHERE name = ? LIMIT 1",
        (name, name)
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Tool: edges_of
# ---------------------------------------------------------------------------

def edges_of(oracle: "DBOracle", args: dict) -> tuple[str, list]:
    """
    All edges touching a named symbol or file.

    Args:
      name      - symbol name OR file path (relative or basename)
      direction - "in" | "out" | "both" (default "both")
      type      - "call" | "import" | "all" (default "all")

    Returns (text, [EdgeRef]) - text for display, EdgeRef list for the system bag.
    """
    name = args.get("name", "").strip()
    if not name:
        return "ERROR: name is required", []
    direction = args.get("direction", "both").strip()
    etype = args.get("type", "all").strip()

    is_file = name.endswith(".py") or "/" in name or "\\" in name
    lines = [f"Edges of '{name}'  (direction={direction}, type={etype}):"]
    found = False
    collected: list[EdgeRef] = []

    # ---- call edges ----
    if etype in ("call", "all"):
        if direction in ("out", "both"):
            rows = oracle.conn.execute(
                "SELECT DISTINCT callee, line_number FROM graph_edges WHERE caller = ? ORDER BY line_number",
                (name,)
            ).fetchall()
            if rows:
                found = True
                lines.append(f"\n  calls out ({len(rows)}):")
                for callee, ln in rows[:20]:
                    lines.append(f"    → {callee}  [line {ln}]")
                    collected.append(EdgeRef(src=name, src_type="symbol",
                                            dst=callee, dst_type="symbol",
                                            edge_type="call", line=ln))
                if len(rows) > 20:
                    lines.append(f"    ... +{len(rows)-20} more")

        if direction in ("in", "both"):
            rows = oracle.conn.execute(
                "SELECT DISTINCT caller, line_number FROM graph_edges "
                "WHERE callee = ? OR callee LIKE ? ORDER BY caller",
                (name, f"%.{name}")
            ).fetchall()
            if rows:
                found = True
                lines.append(f"\n  called by ({len(rows)}):")
                for caller, ln in rows[:20]:
                    lines.append(f"    ← {caller}  [line {ln}]")
                    collected.append(EdgeRef(src=caller, src_type="symbol",
                                            dst=name, dst_type="symbol",
                                            edge_type="call", line=ln))
                if len(rows) > 20:
                    lines.append(f"    ... +{len(rows)-20} more")

    # ---- import edges ----
    if etype in ("import", "all"):
        file_path = name if is_file else (_find_file_for_symbol(oracle, name) or name)
        norm = file_path.replace("\\", "/")

        if direction in ("out", "both"):
            rows = oracle.conn.execute(
                "SELECT DISTINCT module, import_type FROM imports "
                "WHERE replace(file_path, '\\', '/') LIKE ? ORDER BY module",
                (f"%{norm}%",)
            ).fetchall()
            if rows:
                found = True
                internal = [(m, t) for m, t in rows if _resolve_module_to_file(oracle, m)]
                external = [(m, t) for m, t in rows if not _resolve_module_to_file(oracle, m)]
                if internal:
                    lines.append(f"\n  imports from project ({len(internal)}):")
                    for mod, itype in internal[:15]:
                        resolved = _resolve_module_to_file(oracle, mod)
                        rel = _rel(oracle, resolved) if resolved else mod
                        lines.append(f"    → {mod}  ({rel})")
                        collected.append(EdgeRef(src=norm, src_type="file",
                                                 dst=rel, dst_type="file",
                                                 edge_type="import", is_internal=True))
                if external:
                    lines.append(f"\n  imports stdlib/external ({len(external)}):")
                    for mod, _ in sorted(external)[:8]:
                        lines.append(f"    → {mod}")
                        collected.append(EdgeRef(src=norm, src_type="file",
                                                 dst=mod, dst_type="module",
                                                 edge_type="import", is_internal=False))
                    if len(external) > 8:
                        lines.append(f"    ... +{len(external)-8} more")

        if direction in ("in", "both"):
            module_guess = norm.replace(".py", "").replace("/__init__", "").replace("/", ".")
            parts = module_guess.split(".")
            candidates = [".".join(parts[i:]) for i in range(len(parts))]
            reverse_rows = []
            for cand in candidates:
                rows = oracle.conn.execute(
                    "SELECT DISTINCT file_path FROM imports WHERE module = ? OR module LIKE ?",
                    (cand, f"{cand}.%")
                ).fetchall()
                reverse_rows.extend(rows)
            if reverse_rows:
                found = True
                seen = set()
                lines.append(f"\n  imported by ({len(reverse_rows)}):")
                for (fp,) in reverse_rows[:15]:
                    rel = _rel(oracle, fp)
                    if rel not in seen:
                        seen.add(rel)
                        lines.append(f"    ← {rel}")
                        collected.append(EdgeRef(src=rel, src_type="file",
                                                 dst=norm, dst_type="file",
                                                 edge_type="import", is_internal=True))
                if len(reverse_rows) > 15:
                    lines.append(f"    ... +{len(reverse_rows)-15} more")

    if not found:
        lines.append("  no edges found")
        lines.append("  (check spelling; for files use relative path or basename)")

    return "\n".join(lines), collected


# ---------------------------------------------------------------------------
# Tool: edge_detail
# ---------------------------------------------------------------------------

def edge_detail(oracle: "DBOracle", args: dict) -> str:
    """
    Richest view of one specific connection.

    Args:
      src   - source symbol name or file path
      dst   - destination symbol name or file path
      type  - "call" | "import" | "all" (default "all")

    Shows: edge count, call sites, risk of each endpoint, import metadata.
    """
    src = args.get("src", "").strip()
    dst = args.get("dst", "").strip()
    if not src or not dst:
        return "ERROR: src and dst are required"
    etype = args.get("type", "all").strip()

    lines = [f"Edge detail: {src}  →  {dst}"]
    found = False

    if etype in ("call", "all"):
        rows = oracle.conn.execute(
            "SELECT caller, callee, line_number FROM graph_edges "
            "WHERE caller = ? AND (callee = ? OR callee LIKE ?) "
            "ORDER BY line_number",
            (src, dst, f"%.{dst}")
        ).fetchall()
        if not rows:
            # Try reverse
            rows = oracle.conn.execute(
                "SELECT caller, callee, line_number FROM graph_edges "
                "WHERE caller = ? AND (callee = ? OR callee LIKE ?) "
                "ORDER BY line_number",
                (dst, src, f"%.{src}")
            ).fetchall()
            if rows:
                lines.append(f"  NOTE: found reverse direction ({dst} → {src})")
        if rows:
            found = True
            lines.append(f"\n  [call] {len(rows)} call site(s):")
            for caller, callee, ln in rows[:10]:
                lines.append(f"    {caller} → {callee}  line {ln}")
            try:
                from determined.agent.risk_annotator import score_risk, risk_badge
                src_r = score_risk(oracle, src)
                dst_r = score_risk(oracle, dst)
                lines.append(f"\n  src risk: {risk_badge(src_r['level'])} "
                              f"(in={src_r['in_degree']}, out={src_r['out_degree']})")
                lines.append(f"  dst risk: {risk_badge(dst_r['level'])} "
                              f"(in={dst_r['in_degree']}, out={dst_r['out_degree']})")
            except Exception:
                pass

    if etype in ("import", "all"):
        # src imports dst?
        src_file = src if src.endswith(".py") else (_find_file_for_symbol(oracle, src) or src)
        rows = oracle.conn.execute(
            "SELECT module, import_type, line_number FROM imports "
            "WHERE replace(file_path, '\\', '/') LIKE ? ORDER BY line_number",
            (f"%{src_file.replace(chr(92), '/')}%",)
        ).fetchall()
        matching = [(m, t, ln) for m, t, ln in rows if dst in m or m in dst]
        if matching:
            found = True
            lines.append(f"\n  [import] {src_file} imports {dst}:")
            for mod, itype, ln in matching:
                lines.append(f"    {itype} {mod}  line {ln}")

    if not found:
        lines.append("\n  no direct edge found between these two")
        lines.append("  (try swapping src/dst, or check spelling)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: list_import_deps
# ---------------------------------------------------------------------------

def list_import_deps(oracle: "DBOracle", args: dict) -> tuple[str, list]:
    """
    Show project-internal import dependencies.

    Args:
      file_path - (optional) relative path or basename to scope to one file.
                  Without this, shows all file-to-file import edges in the corpus.

    Returns (text, [EdgeRef]) - text for display, EdgeRef list for the system bag.
    """
    file_path = args.get("file_path", "").strip()
    collected: list[EdgeRef] = []

    if file_path:
        rows = oracle.conn.execute(
            "SELECT DISTINCT module, import_type FROM imports "
            "WHERE replace(file_path, '\\', '/') LIKE ? ORDER BY module",
            (f"%{file_path.replace(chr(92), '/')}%",)
        ).fetchall()
        if not rows:
            return f"No imports found for '{file_path}'", []

        lines = [f"Imports in '{file_path}':"]
        internal, external = [], []
        for mod, itype in rows:
            resolved = _resolve_module_to_file(oracle, mod)
            if resolved:
                rel = _rel(oracle, resolved)
                internal.append((mod, rel))
                collected.append(EdgeRef(src=file_path, src_type="file",
                                         dst=rel, dst_type="file",
                                         edge_type="import", is_internal=True))
            else:
                external.append(mod)
                collected.append(EdgeRef(src=file_path, src_type="file",
                                         dst=mod, dst_type="module",
                                         edge_type="import", is_internal=False))

        if internal:
            lines.append(f"\n  project deps ({len(internal)}):")
            for mod, rel in sorted(internal):
                lines.append(f"    {mod}  →  {rel}")
        if external:
            lines.append(f"\n  stdlib/external ({len(external)}):")
            for mod in sorted(external)[:12]:
                lines.append(f"    {mod}")
            if len(external) > 12:
                lines.append(f"    ... +{len(external)-12} more")
        return "\n".join(lines), collected

    else:
        rows = oracle.conn.execute(
            "SELECT DISTINCT from_file, to_module FROM file_edges"
        ).fetchall()
        if not rows:
            return "file_edges table is empty - re-ingest corpus to populate", []

        internal_edges: list[tuple[str, str]] = []
        for from_file, to_module in rows:
            resolved = _resolve_module_to_file(oracle, to_module)
            if resolved:
                from_rel = _rel(oracle, from_file)
                to_rel = _rel(oracle, resolved)
                internal_edges.append((from_rel, to_rel))
                collected.append(EdgeRef(src=from_rel, src_type="file",
                                         dst=to_rel, dst_type="file",
                                         edge_type="import", is_internal=True))

        if not internal_edges:
            return ("No project-internal import edges found.\n"
                    f"Total file_edges rows: {len(rows)} (all imports are stdlib/external)"), []

        deduped = sorted(set(internal_edges))
        lines = [f"Project-internal import edges ({len(deduped)}):"]
        for src, dst in deduped[:40]:
            lines.append(f"  {src}  →  {dst}")
        if len(deduped) > 40:
            lines.append(f"  ... +{len(deduped)-40} more (use file_path arg to scope)")
        return "\n".join(lines), collected


# ---------------------------------------------------------------------------
# Tool: add_edge
# ---------------------------------------------------------------------------

def add_edge(assessor: "KnowledgeArtifact", args: dict) -> str:
    """
    Manually assert a connection and store it in knowledge.db.

    Args:
      src   - source symbol or file name
      dst   - destination symbol or file name
      type  - edge type label (default "manual"; use "data_flow", "co_change", etc.)
      note  - why this connection matters (optional but encouraged)

    Stored as a knowledge artifact (kind="edge") so it shows up in
    list_findings_by_kind(kind="edge") queries.
    """
    src = args.get("src", "").strip()
    dst = args.get("dst", "").strip()
    if not src or not dst:
        return "ERROR: src and dst are required"
    edge_type = args.get("type", "manual").strip() or "manual"
    note = args.get("note", "").strip()

    import json
    content = json.dumps({
        "src": src, "dst": dst,
        "edge_type": edge_type,
        "note": note,
    })
    subject = f"{src}→{dst}"

    try:
        assessor.add_artifact(subject, "edge", content, "manual")
    except Exception as e:
        return f"ERROR storing edge: {e}"

    result = f"Stored {edge_type} edge: {src} → {dst}"
    if note:
        result += f"\n  note: {note}"
    return result
