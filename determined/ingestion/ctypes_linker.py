"""
ctypes_linker.py — cross-language edge detection for Python → C via ctypes.

Scans Python files in a corpus for ctypes library loads:
    lib = ctypes.CDLL("libfoo.so")
    lib = CDLL("./libfoo.so")
    lib = ctypes.cdll.LoadLibrary("libfoo.so")

Then finds attribute-call sites on those variables:
    lib.function_name(args)

Emits ctypes_call edges: (python_caller_fqdn, c_function_name, 'ctypes_call', 1)
into graph_edges.  Resolved=1 because we matched a known ctypes-loaded library variable.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from determined.identity.edge_identity import edge_identity
from determined.identity.symbol_identity import all_name_forms

# Detect: varname = ctypes.CDLL(...) / CDLL(...) / ctypes.cdll.LoadLibrary(...)
_CDLL_ASSIGN_RE = re.compile(
    r'^[ \t]*(\w+)\s*=\s*(?:ctypes\.)?(?:CDLL|cdll\.LoadLibrary)\s*\(',
    re.MULTILINE,
)

# Detect: varname.method(  — only match simple identifiers, not chained calls
_ATTR_CALL_RE = re.compile(r'\b(\w+)\.(\w+)\s*\(')

# Detect function definitions in Python source (very rough — for caller attribution)
_PY_FUNC_DEF_RE = re.compile(r'^[ \t]*(?:async\s+)?def\s+(\w+)\s*\(', re.MULTILINE)


def _find_enclosing_function(src: str, pos: int, module: str) -> str:
    """Return the qualified function name enclosing character position pos in src."""
    last_fn = module
    for m in _PY_FUNC_DEF_RE.finditer(src):
        if m.start() > pos:
            break
        last_fn = f"{module}.{m.group(1)}"
    return last_fn


def run_ctypes_link(conn: sqlite3.Connection, corpus_root: Path) -> int:
    """
    Scan Python files in corpus for ctypes patterns and emit ctypes_call edges.
    Returns the number of edges emitted.
    """
    cur = conn.cursor()

    # Find Python files that were ingested
    cur.execute("SELECT DISTINCT file_path FROM files WHERE file_path LIKE '%.py'")
    py_files = [row[0] for row in cur.fetchall()]
    if not py_files:
        return 0

    # Delete stale ctypes_call edges
    cur.execute("DELETE FROM graph_edges WHERE edge_type = 'ctypes_call'")

    count = 0

    for file_path in py_files:
        p = Path(file_path)
        if not p.exists():
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # Find all CDLL variable assignments in this file
        cdll_vars: set[str] = set()
        for m in _CDLL_ASSIGN_RE.finditer(src):
            cdll_vars.add(m.group(1))

        if not cdll_vars:
            continue

        # Derive module name from file path (basename without .py)
        module = p.stem

        # Find all attribute calls on cdll variables
        for m in _ATTR_CALL_RE.finditer(src):
            var_name = m.group(1)
            method_name = m.group(2)
            if var_name not in cdll_vars:
                continue
            # Skip dunder methods and obvious Python attributes
            if method_name.startswith("_") or method_name in (
                "restype", "argtypes", "errcheck"
            ):
                continue

            caller = _find_enclosing_function(src, m.start(), module)
            callee = method_name

            src_id, tgt_id = edge_identity(caller, callee)
            cur.execute(
                "INSERT OR IGNORE INTO graph_edges "
                "(source_id, target_id, caller, callee, caller_file, edge_type, resolved) "
                "VALUES (?, ?, ?, ?, ?, 'ctypes_call', 1)",
                (src_id, tgt_id, caller, callee, file_path),
            )
            for name, ntype in all_name_forms(caller):
                cur.execute(
                    "INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) "
                    "VALUES (?, ?, ?)",
                    (src_id, name, ntype),
                )
            for name, ntype in all_name_forms(callee):
                cur.execute(
                    "INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) "
                    "VALUES (?, ?, ?)",
                    (tgt_id, name, ntype),
                )
            count += 1

    if count:
        conn.commit()
    return count
