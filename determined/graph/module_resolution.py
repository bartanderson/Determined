# tools/analysis/graph/module_resolution.py

from __future__ import annotations

from pathlib import Path
from typing import Optional
from determined.core.pathing import normalize_file_path

def module_name_from_file_path(
    file_path: str | Path,
    project_root: str | Path,
) -> str:
    """
    Convert a Python file path into a canonical module name.

    Example:
        C:/proj/tools/analysis/query/query_file_analysis.py
            ->
        determined.query.query_file_analysis

    Handles:
    - normal .py files
    - __init__.py package roots
    """

    normalized_file = Path(normalize_file_path(file_path))
    normalized_root = Path(normalize_file_path(project_root))

    relative_path = normalized_file.relative_to(normalized_root)

    parts = list(relative_path.parts)

    if not parts:
        raise ValueError(
            f"Unable to derive module name from path: {file_path}"
        )

    # Remove .py suffix from final component
    parts[-1] = Path(parts[-1]).stem

    # Collapse __init__ package markers
    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def file_path_from_module_name(
    module_name: str,
    project_root: str | Path,
) -> Optional[str]:
    """
    Resolve a canonical module name back into a filesystem path.

    Attempts:
    1. module.py
    2. module/__init__.py

    Returns normalized absolute path if found.
    """

    normalized_root = Path(normalize_file_path(project_root))

    module_parts = module_name.split(".")

    direct_module_path = (
        normalized_root.joinpath(*module_parts)
        .with_suffix(".py")
    )

    if direct_module_path.exists():
        return normalize_file_path(direct_module_path)

    package_init_path = (
        normalized_root.joinpath(*module_parts)
        / "__init__.py"
    )

    if package_init_path.exists():
        return normalize_file_path(package_init_path)

    return None