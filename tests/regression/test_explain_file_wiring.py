# tools/analysis/tests/regression/test_explain_file_wiring.py
#
# Locks in the 2026-06-19 wiring of inspection/explain_file.py into
# Assessor.explain_file(). The function existed and was complete but had
# zero callers anywhere (confirmed by whole-tree grep). This test is the
# permanent proof that:
#   1. Assessor.explain_file() exists and calls through to the real DB.
#   2. The output shape is correct (all top-level keys present).
#   3. Real DB data is returned - not a stub or empty dict.
#   4. A missing file returns a graceful result (not a crash).
#
# Same fixture pattern as other regression tests - real temp sqlite DB,
# real schema, seeded with minimal rows sufficient to exercise each
# output section.

import os
import sqlite3
import tempfile

os.environ.setdefault("PYTHONPATH", ".")


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.executescript("""
        CREATE TABLE files (
            file_path TEXT PRIMARY KEY,
            role TEXT,
            is_hot INTEGER,
            line_count INTEGER
        );
        CREATE TABLE imports (
            file_path TEXT,
            module TEXT,
            import_type TEXT
        );
        CREATE TABLE symbols (
            file_path TEXT,
            symbol_type TEXT,
            name TEXT
        );
        CREATE TABLE symbol_references (
            file_path TEXT,
            caller TEXT,
            callee TEXT,
            bucket TEXT,
            edge_role TEXT
        );
        CREATE TABLE contract_violations (
            file_path TEXT,
            message TEXT,
            severity TEXT,
            contract_name TEXT
        );
    """)
    from pathlib import Path
    fp = str(Path("tools/analysis/oracle/db_oracle.py"))
    conn.execute("INSERT INTO files VALUES (?, ?, ?, ?)", (fp, "persistence", 1, 120))
    conn.execute("INSERT INTO imports VALUES (?, ?, ?)", (fp, "sqlite3", "stdlib"))
    conn.execute("INSERT INTO imports VALUES (?, ?, ?)", (fp, "determined.graph.graph_bundle", "internal"))
    conn.execute("INSERT INTO symbols VALUES (?, ?, ?)", (fp, "class", "DBOracle"))
    conn.execute("INSERT INTO symbols VALUES (?, ?, ?)", (fp, "function", "find_symbols"))
    conn.execute("INSERT INTO symbol_references VALUES (?, ?, ?, ?, ?)", (fp, "DBOracle.find_symbols", "sqlite3.connect", "stdlib", "call"))
    conn.commit()
    return conn


def test_explain_file_output_shape():
    from determined.inspection.explain_file import explain_file
    conn = _make_db()
    result = explain_file(conn, "tools/analysis/oracle/db_oracle.py")

    assert isinstance(result, dict), "explain_file must return a dict"
    for key in ("file_path", "identity", "imports", "symbols",
                "symbol_references", "contracts", "dependencies", "semantic_summary"):
        assert key in result, f"missing top-level key: {key}"


def test_explain_file_real_data():
    from determined.inspection.explain_file import explain_file
    conn = _make_db()
    result = explain_file(conn, "tools/analysis/oracle/db_oracle.py")

    assert result["identity"]["role"] == "persistence"
    assert result["identity"]["is_hot"] is True
    assert result["symbols"]["total"] == 2
    assert result["symbols"]["functions"] == 1
    assert result["symbols"]["classes"] == 1
    assert result["imports"]["raw_count"] == 2
    assert result["symbol_references"]["total"] == 1
    assert isinstance(result["semantic_summary"], str)
    assert len(result["semantic_summary"]) > 0


def test_explain_file_missing_file():
    from determined.inspection.explain_file import explain_file
    conn = _make_db()
    result = explain_file(conn, "does/not/exist.py")

    assert isinstance(result, dict), "must return dict even for missing file"
    assert result["identity"]["role"] == "unknown"
    assert result["symbols"]["total"] == 0


def test_assessor_explain_file_wired():
    from determined.assessor.assessor import Assessor
    from determined.oracle.db_oracle import DBOracle

    conn = _make_db()
    oracle = DBOracle.__new__(DBOracle)
    oracle.conn = conn

    assessor = Assessor.__new__(Assessor)
    assessor.oracle = oracle

    result = assessor.explain_file("tools/analysis/oracle/db_oracle.py")

    assert isinstance(result, dict)
    assert result["identity"]["role"] == "persistence"
    assert "semantic_summary" in result


if __name__ == "__main__":
    test_explain_file_output_shape()
    test_explain_file_real_data()
    test_explain_file_missing_file()
    test_assessor_explain_file_wired()
    print("All tests passed.")
