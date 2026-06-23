# tools/analysis/engine/db_resolver.py

import os
import re


def resolve_analysis_db_path(root_path: str) -> str:
    """
    Deterministic DB naming derived from analysis target path.

    Converts a corpus/root path into a stable sqlite DB filename.

    Examples:
        tools.old → tools_old.db
        tools/old → tools_old.db
        tools.old/agent → tools_old_agent.db
    """

    if not root_path:
        return "analysis.db"

    # normalize path separators
    normalized = root_path.replace("\\", "/").strip("/")

    # replace path structure with underscore hierarchy
    flattened = normalized.replace("/", "_")

    # sanitize to filesystem-safe token
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", flattened)

    # collapse repeated underscores
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    # edge fallback
    if not cleaned:
        cleaned = "analysis"

    return f"{cleaned}.db"