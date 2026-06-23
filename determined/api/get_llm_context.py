# tools/analysis/api/get_llm_context.py

from __future__ import annotations

import sqlite3
from pathlib import Path

from determined.context.build_context_bundle import (
    build_context_bundle,
)
from determined.context.render_context_for_llm import (
    render_context_bundle_for_llm,
)


def get_llm_context_for_file(
    connection: sqlite3.Connection,
    file_path: str | Path,
    include_dependents: bool = True,
    max_dependency_files: int = 10,
) -> str:
    """
    High-level API entrypoint for AI consumption.

    This is the ONLY function external systems should call
    to retrieve analysis context.

    It enforces:
    - structured retrieval
    - bounded context size
    - deterministic rendering
    """

    bundle = build_context_bundle(
        connection=connection,
        entry_file_path=str(file_path),
        include_dependents=include_dependents,
        max_dependency_files=max_dependency_files,
    )

    return render_context_bundle_for_llm(bundle)