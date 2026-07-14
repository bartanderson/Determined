"""
ingest_lang_corpus.py -- ingest a non-Python corpus (Go, Rust, JS/TS) into a corpus DB.

The normal EngineRunner requires at least one Python file and crashes on pure Go/Rust
corpora. This script creates the DB schema and then calls persist_all with an empty
Python layer so the LanguageWalker step (step 5c) runs and handles the actual files.

Usage:
    python tools/ingest_lang_corpus.py <corpus_root>

The output DB path follows the same naming convention as the UI server:
    C_Users_bartl_dev_corpora_end_of_eden.db
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from determined.persistence.persistence_engine import persist_all, create_database
from determined.engine.db_resolver import resolve_analysis_db_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/ingest_lang_corpus.py <corpus_root>")
        sys.exit(1)

    src = Path(sys.argv[1]).resolve()
    if not src.is_dir():
        print(f"Error: not a directory: {src}")
        sys.exit(1)

    db_path = resolve_analysis_db_path(str(src))
    print(f"Ingesting {src}")
    print(f"DB: {db_path}")

    if Path(db_path).exists():
        # Clear in place to match UI server behaviour
        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        for t in tables:
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        print("Cleared existing DB.")

    conn = sqlite3.connect(db_path)

    # Empty Python layer — persist_all still runs the LanguageWalker step (5c)
    # which handles Go/Rust/JS/TS files discovered under project_root.
    persist_all(
        connection=conn,
        file_analyses=[],
        graph=None,
        project_prefixes=[],
        project_root=str(src),
    )
    conn.close()

    # Count what we got
    conn = sqlite3.connect(db_path)
    fn_count = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    conn.close()

    print(f"Done. {fn_count} symbols, {edge_count} edges.")


if __name__ == "__main__":
    main()
