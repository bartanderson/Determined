# tools/analysis/graph/project_context.py

from __future__ import annotations

from pathlib import Path


def build_project_prefixes(
    project_root: str | Path,
) -> list[str]:
    """
    Temporary Iteration 2→3 bridge.

    Centralizes project namespace inference so callers
    no longer need to manually construct prefixes.
    """

    root = str(project_root).replace("\\", ".")

    return [
        root,
        f"{root}.analysis",
        f"{root}.graph",
        f"{root}.persistence",
        f"{root}.shared",
        f"{root}.tests",
    ]