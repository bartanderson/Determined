# tests/regression/test_reingest_file.py
#
# Tests for incremental per-file re-ingestion (item 6).

import os
import sqlite3
import tempfile
import textwrap
from pathlib import Path

import pytest

from determined.ingestion.reingest_file import (
    FileDelta,
    compute_file_delta,
    reingest_file,
    _load_old_symbols,
)
from determined.persistence.persistence_engine import create_database, persist_all
from determined.ingestion.scan_project_files import scan_project_files


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_project(root: Path, files: dict[str, str]) -> None:
    """Write source files into a temp project directory."""
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(src), encoding="utf-8")


def _full_ingest(root: Path, db_path: str) -> None:
    """Full ingest of a project directory into a fresh DB."""
    conn = create_database(db_path)
    file_analyses = list(scan_project_files(str(root), [], str(root)))
    from determined.classification.classify_references import classify_references
    file_analyses = [classify_references(a, []) for a in file_analyses]
    from determined.graph.graph_builder import GraphBuilder
    builder = GraphBuilder()
    for analysis in file_analyses:
        for ref in analysis.symbol_references:
            builder.add_reference(
                caller=ref.caller,
                callee=ref.callee,
                line_number=ref.line_number,
                bucket=getattr(ref, "bucket", "unknown"),
                caller_file=analysis.file_path,
            )
    graph = builder.build()
    persist_all(
        connection=conn,
        file_analyses=file_analyses,
        graph=graph,
        project_prefixes=[],
        project_root=str(root),
    )
    conn.close()


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_reingest_adds_new_function(tmp_path):
    """After adding a function to a file, reingest_file adds it to the DB."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            def helper():
                pass
        """,
    })

    db_path = str(tmp_path / "corpus.db")
    _full_ingest(tmp_path, db_path)

    # Verify helper is present
    conn = sqlite3.connect(db_path)
    before = {r[0] for r in conn.execute("SELECT name FROM functions WHERE file_path LIKE '%foo.py'").fetchall()}
    conn.close()
    assert "helper" in before

    # Update foo.py: add util()
    (tmp_path / "pkg" / "foo.py").write_text(textwrap.dedent("""
        def helper():
            pass

        def util():
            pass
    """), encoding="utf-8")

    # Re-ingest just foo.py
    foo_path = str(tmp_path / "pkg" / "foo.py")
    result = reingest_file(db_path=db_path, file_path=foo_path)
    assert "ERROR" not in result

    conn = sqlite3.connect(db_path)
    after = {r[0] for r in conn.execute("SELECT name FROM functions WHERE file_path LIKE '%foo.py'").fetchall()}
    conn.close()
    assert "helper" in after
    assert "util" in after


def test_reingest_removes_deleted_function(tmp_path):
    """After removing a function, reingest_file removes it from the DB."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            def helper():
                pass

            def old_fn():
                pass
        """,
    })

    db_path = str(tmp_path / "corpus.db")
    _full_ingest(tmp_path, db_path)

    # Remove old_fn
    (tmp_path / "pkg" / "foo.py").write_text(textwrap.dedent("""
        def helper():
            pass
    """), encoding="utf-8")

    foo_path = str(tmp_path / "pkg" / "foo.py")
    result = reingest_file(db_path=db_path, file_path=foo_path)
    assert "ERROR" not in result

    conn = sqlite3.connect(db_path)
    after = {r[0] for r in conn.execute("SELECT name FROM functions WHERE file_path LIKE '%foo.py'").fetchall()}
    conn.close()
    assert "helper" in after
    assert "old_fn" not in after


def test_reingest_idempotent(tmp_path):
    """Running reingest_file twice produces the same result."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            def helper():
                pass
        """,
    })

    db_path = str(tmp_path / "corpus.db")
    _full_ingest(tmp_path, db_path)

    (tmp_path / "pkg" / "foo.py").write_text(textwrap.dedent("""
        def helper():
            pass

        def util():
            pass
    """), encoding="utf-8")

    foo_path = str(tmp_path / "pkg" / "foo.py")
    reingest_file(db_path=db_path, file_path=foo_path)
    reingest_file(db_path=db_path, file_path=foo_path)  # second run

    conn = sqlite3.connect(db_path)
    fns = [r[0] for r in conn.execute("SELECT name FROM functions WHERE file_path LIKE '%foo.py'").fetchall()]
    syms = [r[0] for r in conn.execute("SELECT name FROM symbols WHERE file_path LIKE '%foo.py'").fetchall()]
    conn.close()

    assert fns.count("helper") == 1, "helper should appear exactly once"
    assert fns.count("util") == 1, "util should appear exactly once"
    assert syms.count("helper") == 1
    assert syms.count("util") == 1


def test_reingest_delta_content(tmp_path):
    """compute_file_delta correctly classifies added, removed, unchanged symbols."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": """
            def keep():
                pass

            def remove_me():
                pass
        """,
    })

    db_path = str(tmp_path / "corpus.db")
    _full_ingest(tmp_path, db_path)

    # Update: keep stays, remove_me gone, new_fn added
    (tmp_path / "pkg" / "foo.py").write_text(textwrap.dedent("""
        def keep():
            pass

        def new_fn():
            pass
    """), encoding="utf-8")

    from determined.ingestion.parse_ast import parse_ast
    from determined.classification.classify_references import classify_references
    from determined.core.pathing import normalize_file_path

    foo_path = str(tmp_path / "pkg" / "foo.py")
    normalized = normalize_file_path(foo_path)

    conn = sqlite3.connect(db_path)
    new_analysis = parse_ast(normalized, global_known_symbols=set())
    classify_references(new_analysis, project_prefixes=[], logger=None)
    delta = compute_file_delta(conn, normalized, new_analysis)
    conn.close()

    assert "new_fn" in delta.to_add
    assert "remove_me" in delta.to_remove
    assert "keep" in delta.unchanged


def test_reingest_error_missing_file(tmp_path):
    """reingest_file raises FileNotFoundError for a missing source file."""
    _make_project(tmp_path, {"pkg/__init__.py": ""})
    db_path = str(tmp_path / "corpus.db")
    _full_ingest(tmp_path, db_path)

    with pytest.raises(FileNotFoundError):
        reingest_file(db_path=db_path, file_path=str(tmp_path / "nonexistent.py"))


def test_reingest_error_missing_db(tmp_path):
    """reingest_file raises FileNotFoundError for a missing corpus DB."""
    _make_project(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/foo.py": "def f(): pass",
    })
    with pytest.raises(FileNotFoundError):
        reingest_file(db_path=str(tmp_path / "nope.db"), file_path=str(tmp_path / "pkg" / "foo.py"))
