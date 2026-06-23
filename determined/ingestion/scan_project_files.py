# tools/analysis/ingestion/scan_project_files.py

from __future__ import annotations

import ast
from pathlib import Path
from typing import Generator, Iterable, List
from collections import defaultdict

from determined.ingestion.extract_symbols import extract_symbols
from determined.ingestion.parse_ast import parse_ast
from determined.shared.types import FileAnalysis
from determined.audit.symbol_audit import SymbolAudit
from determined.core.pathing import (
    normalize_file_path,
    module_name_from_file_path,
    is_within_project_boundary,
)

# -------------------------
# DEBUG / METRICS
# -------------------------
symbol_counts = defaultdict(int)

# -------------------------
# IGNORED DIRECTORIES
# -------------------------
DEFAULT_IGNORED_DIRECTORIES = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "archive",
    "tools_old",
}


# =========================================================
# FILE DISCOVERY
# =========================================================
def should_ignore_path(path: Path, ignored_directory_names: Iterable[str]) -> bool:
    ignored = set(ignored_directory_names)
    return any(part in ignored for part in path.parts)


def discover_python_files(
    project_root: str | Path,
    ignored_directory_names: Iterable[str] | None = None,
) -> List[Path]:

    root = Path(project_root).resolve()

    ignored = (
        set(ignored_directory_names)
        if ignored_directory_names is not None
        else DEFAULT_IGNORED_DIRECTORIES
    )

    discovered_files: List[Path] = []

    for path in root.rglob("*.py"):
        path = path.resolve()

        if not str(path).startswith(str(root)):
            continue

        if any(part in {"site-packages", "__pycache__", ".venv", "Lib"} for part in path.parts):
            continue

        if should_ignore_path(path, ignored):
            continue

        discovered_files.append(path)

    return sorted(discovered_files)


# =========================================================
# PASS 1 — GLOBAL SYMBOL COLLECTION
# =========================================================
def build_global_symbols(
    python_files: List[Path],
    repo_root: Path,
) -> set[str]:

    global_symbols: set[str] = set()

    for file_path in python_files:

        if "__pycache__" in str(file_path):
            continue

        source = Path(file_path).read_text(
            encoding="utf-8",
            errors="ignore",
        )

        try:
            import warnings as _warnings
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore", DeprecationWarning)
                tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue

        module_prefix = module_name_from_file_path(
            file_path=file_path,
            project_root=repo_root,
        )

        if not module_prefix:
            continue

        symbols = extract_symbols(tree, module_prefix)

        if isinstance(symbols, dict):
            sym_set = symbols.get("all", set())
        else:
            sym_set = symbols

        sym_set = {s for s in sym_set if s}

        global_symbols.update(sym_set)

    return global_symbols


# =========================================================
# PASS 2 — FULL FILE ANALYSIS
# =========================================================
def analyze_files(
    python_files: List[Path],
    GLOBAL_SYMBOLS: set[str],
    runtime_bindings: dict,
    project_root: Path,
) -> Generator[FileAnalysis, None, None]:

    for file_path in python_files:

        normalized_path = normalize_file_path(file_path)

        analysis = parse_ast(
            normalized_path,
            global_known_symbols=GLOBAL_SYMBOLS,
            runtime_bindings=runtime_bindings,
        )

        if analysis is None:
            continue

        # attach global symbol universe
        analysis.project_symbols = GLOBAL_SYMBOLS

        yield analysis


# =========================================================
# MAIN PIPELINE
# =========================================================
def scan_project_files(
    project_root: str | Path,
    project_prefixes: list[str],
    repo_root: str | Path,
    ignored_directory_names: Iterable[str] | None = None,
) -> Generator[FileAnalysis, None, None]:

    project_root = Path(project_root).resolve(strict=True)
    repo_root = Path(repo_root).resolve()

    audit = SymbolAudit()

    # -------------------------
    # DISCOVERY
    # -------------------------
    python_files = discover_python_files(
        project_root=project_root,
        ignored_directory_names=ignored_directory_names,
    )

    python_files = [Path(p).resolve() for p in python_files]

    # -------------------------
    # HARD BOUNDARY FILTER
    # -------------------------
    python_files = [
        p for p in python_files
        if is_within_project_boundary(p, project_root)
    ]

    runtime_bindings = {}  # still placeholder for now

    # -------------------------
    # PASS 1 — GLOBAL SYMBOLS
    # -------------------------
    GLOBAL_SYMBOLS = build_global_symbols(python_files, repo_root)

    # -------------------------
    # PASS 2 — ANALYSIS
    # -------------------------
    yield from analyze_files(
        python_files=python_files,
        GLOBAL_SYMBOLS=GLOBAL_SYMBOLS,
        runtime_bindings=runtime_bindings,
        project_root=project_root,
    )