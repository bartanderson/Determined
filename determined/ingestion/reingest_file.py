# determined/ingestion/reingest_file.py
#
# Incremental per-file re-ingestion. Re-parses one changed file and updates
# the corpus DB without touching unrelated files.
#
# Design notes:
# - FileDelta is a pure in-memory scratchpad; discarded on completion.
# - Apply order: insert new symbol rows -> run persist_file_analysis
#   (DELETE-then-INSERT for all other tables) -> delete stale old symbol rows
#   -> _persist_graph_edges (scoped delete+insert for outbound edges).
#   New rows coexist with old inside the transaction; old rows are removed
#   only after new ones are committed.
# - Inbound graph_edges from other files that called a removed symbol become
#   dangling references. This is the honest representation -- those callers
#   still reference the old name and will be resolved when they are next
#   re-ingested.

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from determined.core.pathing import normalize_file_path
from determined.identity.edge_identity import edge_identity


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class SymbolRecord:
    name: str
    symbol_type: str      # 'function' or 'class'
    line_number: int
    canonical_id: str


@dataclass
class FileDelta:
    file_path: str
    old_symbols: dict[str, SymbolRecord]   # name -> record (from DB)
    new_symbols: dict[str, SymbolRecord]   # name -> record (from fresh parse)
    to_add: set[str]      # in new, not in old
    to_update: set[str]   # in both, something changed (line, type)
    to_remove: set[str]   # in old, not in new (callees pointing here will dangle)
    unchanged: set[str]   # in both, identical

    def summary(self) -> str:
        parts = []
        if self.to_add:
            parts.append(f"+{len(self.to_add)} added")
        if self.to_update:
            parts.append(f"~{len(self.to_update)} updated")
        if self.to_remove:
            parts.append(f"-{len(self.to_remove)} removed")
        if self.unchanged:
            parts.append(f"={len(self.unchanged)} unchanged")
        return ", ".join(parts) if parts else "no symbol changes"


# ------------------------------------------------------------------
# Step 1: load old symbol state from DB
# ------------------------------------------------------------------

def _load_old_symbols(conn: sqlite3.Connection, file_path: str) -> dict[str, SymbolRecord]:
    rows = conn.execute(
        "SELECT name, symbol_type, line_number, canonical_id FROM symbols WHERE file_path = ?",
        (file_path,),
    ).fetchall()
    return {
        row[0]: SymbolRecord(
            name=row[0],
            symbol_type=row[1],
            line_number=row[2],
            canonical_id=row[3],
        )
        for row in rows
    }


# ------------------------------------------------------------------
# Step 2: derive global symbol universe from DB (minus this file)
#         plus the target file's own new declarations
# ------------------------------------------------------------------

def _derive_global_symbols(conn: sqlite3.Connection, file_path: str) -> set[str]:
    """
    Re-create the global symbol set used during full ingest, but reading
    from the DB instead of re-scanning all files.  Other files' symbols
    come from the DB; the target file's new symbols come from a quick
    AST scan of just that file.
    """
    import ast as _ast
    from determined.ingestion.extract_symbols import extract_symbols
    from determined.core.pathing import module_name_from_file_path

    # All symbols from other files
    rows = conn.execute(
        "SELECT name FROM symbols WHERE file_path != ?",
        (file_path,),
    ).fetchall()
    global_syms: set[str] = {row[0] for row in rows if row[0]}

    # Target file's own new declarations
    src_path = Path(file_path)
    if src_path.exists():
        try:
            source = src_path.read_text(encoding="utf-8", errors="ignore")
            tree = _ast.parse(source, filename=str(src_path))
            # module_name_from_file_path needs a repo_root; use file's parent as fallback
            project_root = conn.execute(
                "SELECT value FROM project_meta WHERE key = 'project_root'"
            ).fetchone()
            repo_root = Path(project_root[0]) if project_root else src_path.parent
            prefix = module_name_from_file_path(src_path, repo_root)
            if prefix:
                syms = extract_symbols(tree, prefix)
                sym_set = syms.get("all", set()) if isinstance(syms, dict) else syms
                global_syms.update(s for s in sym_set if s)
        except Exception:
            pass  # parse error: fall back to DB-only symbol set

    return global_syms


# ------------------------------------------------------------------
# Step 3: compute the delta
# ------------------------------------------------------------------

def compute_file_delta(
    conn: sqlite3.Connection,
    file_path: str,
    new_analysis,
) -> FileDelta:
    """
    Compare old symbols in DB to new symbols from the fresh parse.
    Returns a FileDelta describing what changed.
    """
    old = _load_old_symbols(conn, file_path)

    # Build new symbol map from new_analysis functions + classes
    new: dict[str, SymbolRecord] = {}
    for fn in getattr(new_analysis, "functions", []):
        cid = f"{file_path}:function:{fn.name}:{fn.line_number}"
        new[fn.name] = SymbolRecord(fn.name, "function", fn.line_number, cid)
    for cls in getattr(new_analysis, "classes", []):
        cid = f"{file_path}:class:{cls.name}:{cls.line_number}"
        new[cls.name] = SymbolRecord(cls.name, "class", cls.line_number, cid)

    old_names = set(old.keys())
    new_names = set(new.keys())

    to_add = new_names - old_names
    to_remove = old_names - new_names
    shared = old_names & new_names
    to_update = {
        name for name in shared
        if old[name].canonical_id != new[name].canonical_id
        or old[name].symbol_type != new[name].symbol_type
    }
    unchanged = shared - to_update

    return FileDelta(
        file_path=file_path,
        old_symbols=old,
        new_symbols=new,
        to_add=to_add,
        to_update=to_update,
        to_remove=to_remove,
        unchanged=unchanged,
    )


# ------------------------------------------------------------------
# Step 4: apply the delta
# ------------------------------------------------------------------

def _insert_new_symbols(conn: sqlite3.Connection, delta: FileDelta) -> None:
    """Insert new symbol rows before touching old ones."""
    cursor = conn.cursor()
    targets = delta.to_add | delta.to_update
    for name in targets:
        rec = delta.new_symbols[name]
        cursor.execute(
            """
            INSERT OR IGNORE INTO symbols
                (file_path, symbol_type, name, line_number, signature, canonical_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (delta.file_path, rec.symbol_type, rec.name, rec.line_number, "", rec.canonical_id),
        )


def _delete_stale_symbols(conn: sqlite3.Connection, delta: FileDelta) -> None:
    """Remove old symbol rows that are no longer present or have been superseded."""
    stale_ids = []
    # Removed symbols
    for name in delta.to_remove:
        stale_ids.append(delta.old_symbols[name].canonical_id)
    # Updated symbols: old canonical_id is now superseded by new one
    for name in delta.to_update:
        old_cid = delta.old_symbols[name].canonical_id
        new_cid = delta.new_symbols[name].canonical_id
        if old_cid != new_cid:
            stale_ids.append(old_cid)

    if stale_ids:
        placeholders = ",".join("?" * len(stale_ids))
        conn.execute(
            f"DELETE FROM symbols WHERE canonical_id IN ({placeholders})",
            stale_ids,
        )


def apply_file_delta(
    conn: sqlite3.Connection,
    delta: FileDelta,
    new_analysis,
    repo_root: str,
) -> None:
    """
    Apply a FileDelta to the corpus DB.

    Order:
    1. Insert new symbol rows (new and updated).
    2. Run persist_file_analysis -- DELETE-then-INSERT for files/functions/
       classes/imports/behavioral_contracts/mutations/symbol_references.
    3. Delete stale old symbol rows.
    4. Rebuild outbound graph edges via _persist_graph_edges (scoped delete).
    """
    from determined.persistence.persistence_engine import (
        persist_file_analysis,
        _persist_graph_edges,
    )
    from determined.graph.graph_builder import GraphBuilder

    # 1. New symbol rows coexist with old (within this transaction)
    _insert_new_symbols(conn, delta)

    # 2. Refresh all file-scoped tables
    persist_file_analysis(conn, new_analysis, project_prefixes=[])

    # 3. Now safe to remove superseded symbol rows
    _delete_stale_symbols(conn, delta)

    # 4. Rebuild outbound graph edges for this file
    builder = GraphBuilder()
    for ref in getattr(new_analysis, "symbol_references", []):
        builder.add_reference(
            caller=ref.caller,
            callee=ref.callee,
            line_number=ref.line_number,
            bucket=getattr(ref, "bucket", "unknown"),
            caller_file=delta.file_path,
        )
    graph = builder.build()
    _persist_graph_edges(conn, graph)

    conn.commit()


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def reingest_file(
    db_path: str,
    file_path: str,
    repo_root: Optional[str] = None,
) -> str:
    """
    Re-ingest a single changed file into an existing corpus DB.

    Returns a human-readable summary of what changed.
    Raises FileNotFoundError if the file or DB does not exist.
    """
    from determined.ingestion.parse_ast import parse_ast
    from determined.classification.classify_references import classify_references

    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Corpus DB not found: {db_path}")

    fp = Path(file_path)
    if not fp.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    normalized = normalize_file_path(file_path)

    conn = sqlite3.connect(str(db))
    try:
        # Derive global symbols: DB (other files) + fresh scan of this file
        global_symbols = _derive_global_symbols(conn, normalized)

        # Parse the changed file
        new_analysis = parse_ast(normalized, global_known_symbols=global_symbols)
        if new_analysis is None:
            return f"ERROR: parse_ast returned None for {file_path}"

        classify_references(new_analysis, project_prefixes=[], logger=None)

        # Compute delta (in memory)
        delta = compute_file_delta(conn, normalized, new_analysis)

        # Apply
        apply_file_delta(conn, delta, new_analysis, repo_root or str(fp.parent))

        return (
            f"Re-ingested {normalized}\n"
            f"Symbols: {delta.summary()}\n"
            f"Stale inbound edges (if any) remain as dangling references "
            f"until callers are re-ingested."
        )
    finally:
        conn.close()
