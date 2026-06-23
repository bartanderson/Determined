# tools/analysis/core/pathing.py

from __future__ import annotations

import os
from pathlib import Path


def normalize_file_path(path: str | Path) -> str:
    """
    Convert paths into stable forward-slash canonical form.
    """

    return str(Path(path).resolve()).replace("\\", "/")


def resolve_project_root(path: str | Path) -> Path:
    """
    Resolve analysis root from:
    - explicit path
    - env variable token
    - cwd fallback
    """

    path = str(path)

    if path == ".":
        return Path.cwd().resolve()

    if path.startswith("${") and path.endswith("}"):
        env_key = path[2:-1]
        return Path(
            os.environ.get(env_key, Path.cwd())
        ).resolve()

    return Path(path).resolve()


def resolve_repo_root(path: str | Path) -> Path:
    """
    Walk upward until repository boundary is found.
    """

    p = Path(path).resolve()

    for parent in [p, *p.parents]:

        if (parent / ".git").exists():
            return parent

        if (parent / "pyproject.toml").exists():
            return parent

    return p


def module_name_from_file_path(
    file_path: str | Path,
    project_root: str | Path,
) -> str:
    """
    Convert filesystem path into canonical Python module identity.

    Example:
        root:
            C:/repo/tools.old

        file:
            C:/repo/tools.old/ai_assistant/cli/router.py

        result:
            ai_assistant.cli.router
    """

    normalized_file = Path(
        normalize_file_path(file_path)
    )

    normalized_root = Path(
        normalize_file_path(project_root)
    )

    relative_path = normalized_file.relative_to(
        normalized_root
    )

    parts = list(relative_path.parts)

    if not parts:
        raise ValueError(
            f"Unable to derive module name from path: {file_path}"
        )

    parts[-1] = Path(parts[-1]).stem

    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def is_within_project_boundary(
    file_path: str | Path,
    project_root: str | Path,
) -> bool:

    file_path = Path(file_path).resolve()
    project_root = Path(project_root).resolve()

    return str(file_path).startswith(str(project_root))

def normalize_file_identity(path: str | Path) -> str:
    """
    Canonical identity for a file across ALL system layers.

    This is the ONLY function allowed to define file identity semantics
    for ingestion, graph, persistence, and inspection layers.
    """
    return normalize_file_path(path)