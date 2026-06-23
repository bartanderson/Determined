# tools/analysis/context/build_context_bundle.py

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Set

from determined.query.query_file_analysis import (
    fetch_complete_file_analysis,
)

from pathlib import Path
# 🔒 PIPELINE GUARDS (runtime invariants only)

FORBIDDEN_TRACE_SYMBOLS = {
    "add_file",
}

def _assert_no_forbidden_trace(symbol_name: str):
    if symbol_name in FORBIDDEN_TRACE_SYMBOLS:
        raise RuntimeError(f"[PIPELINE VIOLATION] forbidden symbol: {symbol_name}")

def _derive_module_name(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")

    if normalized.endswith(".py"):
        normalized = normalized[:-3]

    return normalized.replace("/", ".")


def build_context_bundle(
    connection: sqlite3.Connection,
    entry_file_path: str,
    include_dependents: bool = True,
    max_dependency_files: int = 10,
) -> Dict[str, Any]:
    """
    Context layer responsibility:
    - fetch file analyses
    - package deterministic context
    - NO symbol resolution
    - NO graph logic
    - NO dependency inference
    """

    entry_file_path = str(Path(entry_file_path).resolve()).replace("\\", "/")

    entry_analysis = fetch_complete_file_analysis(
        connection,
        entry_file_path,
    )

    if entry_analysis is None:
        return {
            "entry_file": None,
            "related_files": [],
        }

    # --------------------------------------------------
    # ENTRY FILE (NO TRANSFORMATION)
    # --------------------------------------------------

    entry_analysis["symbol_references"] = entry_analysis.get("symbol_references", [])

    bundle: Dict[str, Any] = {
        "entry_file": entry_analysis,
        "related_files": [],
    }

    if not include_dependents:
        return bundle

    # --------------------------------------------------
    # RELATED FILES (DIRECT FETCH ONLY)
    # --------------------------------------------------

    imports = entry_analysis.get("imports", [])
    dependent_files: Set[str] = set()

    for imp in imports:
        module = imp.get("module")
        if not module:
            continue

        # NOTE: dependency resolution is intentionally deferred
        # so we only include entry-level context for now
        continue

    visited: Set[str] = {entry_file_path}

    for dependent_path in list(dependent_files)[:max_dependency_files]:
        if dependent_path in visited:
            continue

        related_analysis = fetch_complete_file_analysis(
            connection,
            dependent_path,
        )

        if related_analysis is None:
            continue

        visited.add(dependent_path)
        bundle["related_files"].append(related_analysis)

    return bundle