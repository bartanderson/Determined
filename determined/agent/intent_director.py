"""
Intent-directed analysis pass.

Given a user phrase ("investigate the persistence layer"), this module:
  1. Extracts search terms from the phrase
  2. Finds matching files and symbols in the corpus
  3. Runs a targeted analysis pass on each match
     (risk score, import edges, call edges for HOT symbols)
  4. Fills the system bag with typed, labeled artifacts
  5. Returns a structured summary for display

The system bag becomes the work context for that intent. The user can
then save it as a named bag ("user:persistence-refactor") to bookmark
this investigation thread.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.oracle.db_oracle import DBOracle
    from determined.agent.bag_store import BagStore

_STOPWORDS = {
    "the","a","an","i","in","on","at","to","for","of","and","or","is","are",
    "was","want","need","understand","investigate","look","find","show","get",
    "what","how","why","which","where","does","do","can","will","should","all",
    "this","that","these","those","with","from","into","about","through",
}

_SYSTEM_BAG = "system"


def _tokens(text: str) -> list[str]:
    words = re.split(r"\W+", text.lower())
    return [w for w in words if w and w not in _STOPWORDS and len(w) > 2]


def _rel(oracle: "DBOracle", path: str) -> str:
    root = oracle.get_project_root().replace("\\", "/").rstrip("/") + "/"
    return path.replace("\\", "/").replace(root, "")


def _resolve_module(oracle: "DBOracle", module: str):
    parts = module.split(".")
    candidates = [
        "/".join(parts) + ".py",
        "/".join(parts) + "/__init__.py",
    ]
    if len(parts) > 1:
        candidates += ["/".join(parts[:-1]) + ".py",
                       "/".join(parts[:-1]) + "/__init__.py"]
    for cand in candidates:
        rows = oracle.conn.execute(
            "SELECT file_path FROM files WHERE replace(file_path,'\\','/') LIKE ?",
            (f"%{cand}",)
        ).fetchall()
        if rows:
            return min(rows, key=lambda r: len(r[0]))[0]
    return None


def direct_from_intent(
    oracle: "DBOracle",
    bags: "BagStore",
    intent_text: str,
    max_files: int = 20,
    max_symbols: int = 30,
) -> dict:
    """
    Run a directed analysis pass and fill the system bag.

    Returns a summary dict with counts and the list of what was found.
    """
    from determined.agent.edge_types import EdgeRef
    from determined.agent.risk_annotator import score_risk

    terms = _tokens(intent_text)
    if not terms:
        return {"error": "no search terms found in intent", "intent": intent_text}

    # -- find matching files and symbols --
    found_files: dict[str, str] = {}   # file_path → rel_path
    found_symbols: list[dict] = []

    for term in terms:
        pattern = f"%{term}%"
        for (fp,) in oracle.conn.execute(
            "SELECT file_path FROM files WHERE replace(file_path,'\\','/') LIKE ?",
            (pattern,)
        ).fetchall():
            if fp not in found_files:
                found_files[fp] = _rel(oracle, fp)

        for name, fp, stype in oracle.conn.execute(
            "SELECT name, file_path, 'function' FROM functions WHERE name LIKE ? "
            "UNION "
            "SELECT name, file_path, 'class' FROM classes WHERE name LIKE ?",
            (pattern, pattern)
        ).fetchall():
            if fp not in found_files:
                found_files[fp] = _rel(oracle, fp)
            found_symbols.append({"name": name, "file": fp, "type": stype})

    # de-dup symbols (name is enough key)
    seen_syms: set[str] = set()
    unique_syms = []
    for s in found_symbols:
        if s["name"] not in seen_syms:
            seen_syms.add(s["name"])
            unique_syms.append(s)

    # cap
    file_items = list(found_files.items())[:max_files]
    sym_items  = unique_syms[:max_symbols]

    files_added = symbols_added = edges_added = 0
    note_prefix = f"intent: {intent_text[:50]}"

    # -- fill bag: files --
    for fp, rel in file_items:
        if bags.add_file(_SYSTEM_BAG, rel, note=note_prefix):
            files_added += 1

        # import edges for this file
        for (mod,) in oracle.conn.execute(
            "SELECT DISTINCT module FROM imports "
            "WHERE replace(file_path,'\\','/') LIKE ?",
            (f"%{fp.replace(chr(92), '/')}%",)
        ).fetchall():
            resolved = _resolve_module(oracle, mod)
            if resolved:
                edge = EdgeRef(
                    src=rel, src_type="file",
                    dst=_rel(oracle, resolved), dst_type="file",
                    edge_type="import", is_internal=True,
                    note=note_prefix,
                )
                if bags.add_edge(_SYSTEM_BAG, edge):
                    edges_added += 1

    # -- fill bag: symbols with risk --
    for sym in sym_items:
        risk = score_risk(oracle, sym["name"])
        fp_rel = _rel(oracle, sym["file"])
        note = f"[{risk['level']}] {note_prefix}"
        if bags.add_symbol(_SYSTEM_BAG, sym["name"], fp_rel, note=note):
            symbols_added += 1

        # call edges for HOT/WARM symbols (who calls them)
        if risk["level"] in ("HOT", "WARM"):
            for (caller,) in oracle.conn.execute(
                "SELECT DISTINCT caller FROM graph_edges "
                "WHERE callee = ? OR callee LIKE ? ORDER BY caller LIMIT 10",
                (sym["name"], f"%.{sym['name']}")
            ).fetchall():
                edge = EdgeRef(
                    src=caller, src_type="symbol",
                    dst=sym["name"], dst_type="symbol",
                    edge_type="call", note=note_prefix,
                )
                if bags.add_edge(_SYSTEM_BAG, edge):
                    edges_added += 1

    return {
        "intent": intent_text,
        "terms": terms,
        "files_found": [rel for _, rel in file_items],
        "symbols_found": [s["name"] for s in sym_items],
        "files_added": files_added,
        "symbols_added": symbols_added,
        "edges_added": edges_added,
        "total_added": files_added + symbols_added + edges_added,
    }


def summary_text(result: dict) -> str:
    """Format the result dict as a short chat-ready summary."""
    if "error" in result:
        return f"Intent pass failed: {result['error']}"
    r = result
    lines = [
        f"Intent: \"{r['intent']}\"",
        f"Terms searched: {', '.join(r['terms'])}",
        "",
        f"Added to system bag:",
        f"  {r['files_added']} files",
        f"  {r['symbols_added']} symbols",
        f"  {r['edges_added']} edges",
        f"  ({r['total_added']} total)",
    ]
    if r["files_found"]:
        lines += ["", "Files in scope:"] + [f"  {f}" for f in r["files_found"][:10]]
        if len(r["files_found"]) > 10:
            lines.append(f"  ... +{len(r['files_found'])-10} more")
    if r["symbols_found"]:
        lines += ["", "Symbols found:"] + [f"  {s}" for s in r["symbols_found"][:10]]
        if len(r["symbols_found"]) > 10:
            lines.append(f"  ... +{len(r['symbols_found'])-10} more")
    lines += ["", "Open the Bag tab to see everything collected."]
    return "\n".join(lines)
