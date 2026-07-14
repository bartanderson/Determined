"""
Regression tests for external interface dispatch:
  - load_external_interfaces() reads external_interfaces.json
  - _external_interface_dispatch_pass() inserts interface_dispatch edges
  - persist_all wires both together for Go and Rust corpora
"""

import json
import sqlite3
import textwrap
from pathlib import Path

import pytest

from determined.ingestion.dynamic_edges import load_external_interfaces
from determined.persistence.persistence_engine import (
    _external_interface_dispatch_pass,
    ensure_schema,
    persist_all,
)


# ---------------------------------------------------------------------------
# load_external_interfaces tests
# ---------------------------------------------------------------------------

def test_load_external_interfaces_basic(tmp_path):
    data = [
        {"interface": "tea.Model", "methods": ["Init", "Update", "View"], "language": "go"},
        {"interface": "io.Reader", "methods": ["Read"], "language": "go"},
    ]
    (tmp_path / "external_interfaces.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    result = load_external_interfaces(tmp_path)
    assert "go" in result
    assert set(result["go"]["tea.Model"]) == {"Init", "Update", "View"}
    assert result["go"]["io.Reader"] == ["Read"]


def test_load_external_interfaces_missing_file(tmp_path):
    assert load_external_interfaces(tmp_path) == {}


def test_load_external_interfaces_malformed_json(tmp_path):
    (tmp_path / "external_interfaces.json").write_text("not json", encoding="utf-8")
    assert load_external_interfaces(tmp_path) == {}


def test_load_external_interfaces_rust(tmp_path):
    data = [
        {"interface": "std::io::Write", "methods": ["write", "flush"], "language": "rust"},
    ]
    (tmp_path / "external_interfaces.json").write_text(json.dumps(data), encoding="utf-8")
    result = load_external_interfaces(tmp_path)
    assert "rust" in result
    assert set(result["rust"]["std::io::Write"]) == {"write", "flush"}


def test_load_external_interfaces_mixed_languages(tmp_path):
    data = [
        {"interface": "tea.Model", "methods": ["Init"], "language": "go"},
        {"interface": "Display", "methods": ["fmt"], "language": "rust"},
    ]
    (tmp_path / "external_interfaces.json").write_text(json.dumps(data), encoding="utf-8")
    result = load_external_interfaces(tmp_path)
    assert "go" in result and "rust" in result
    assert "tea.Model" in result["go"]
    assert "Display" in result["rust"]


def test_load_external_interfaces_skips_empty_entries(tmp_path):
    data = [
        {"interface": "", "methods": ["Init"], "language": "go"},
        {"interface": "tea.Model", "methods": [], "language": "go"},
        {"interface": "io.Reader", "methods": ["Read"], "language": "go"},
    ]
    (tmp_path / "external_interfaces.json").write_text(json.dumps(data), encoding="utf-8")
    result = load_external_interfaces(tmp_path)
    assert list(result.get("go", {}).keys()) == ["io.Reader"]


# ---------------------------------------------------------------------------
# _external_interface_dispatch_pass tests (Go)
# ---------------------------------------------------------------------------

def _db_with_go_functions(functions: list[tuple[str, str]]) -> sqlite3.Connection:
    """Create an in-memory DB with just enough schema for the dispatch pass."""
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    cur = conn.cursor()
    for name, fp in functions:
        cur.execute(
            "INSERT INTO functions (name, file_path) VALUES (?, ?)", (name, fp)
        )
    conn.commit()
    return conn


def test_external_dispatch_go_full_implementor():
    conn = _db_with_go_functions([
        ("ChoicesModel.Init", "/f/model.go"),
        ("ChoicesModel.Update", "/f/model.go"),
        ("ChoicesModel.View", "/f/model.go"),
    ])
    cur = conn.cursor()
    ext_ifaces = {"tea.Model": ["Init", "Update", "View"]}
    count = _external_interface_dispatch_pass(cur, ext_ifaces, "go", [], logger=None)
    assert count == 3
    rows = cur.execute(
        "SELECT caller, callee, edge_type FROM graph_edges WHERE edge_type='interface_dispatch'"
    ).fetchall()
    assert len(rows) == 3
    callers = {r[0] for r in rows}
    assert "tea.Model.Init" in callers
    assert "tea.Model.Update" in callers
    assert "tea.Model.View" in callers
    callees = {r[1] for r in rows}
    assert "ChoicesModel.Init" in callees


def test_external_dispatch_go_partial_implementor_skipped():
    conn = _db_with_go_functions([
        ("ChoicesModel.Init", "/f/model.go"),
        ("ChoicesModel.Update", "/f/model.go"),
        # missing View — should NOT get edges
    ])
    cur = conn.cursor()
    ext_ifaces = {"tea.Model": ["Init", "Update", "View"]}
    count = _external_interface_dispatch_pass(cur, ext_ifaces, "go", [], logger=None)
    assert count == 0


def test_external_dispatch_go_multiple_implementors():
    conn = _db_with_go_functions([
        ("ChoicesModel.Init", "/f/a.go"),
        ("ChoicesModel.Update", "/f/a.go"),
        ("ChoicesModel.View", "/f/a.go"),
        ("DamageModel.Init", "/f/b.go"),
        ("DamageModel.Update", "/f/b.go"),
        ("DamageModel.View", "/f/b.go"),
    ])
    cur = conn.cursor()
    ext_ifaces = {"tea.Model": ["Init", "Update", "View"]}
    count = _external_interface_dispatch_pass(cur, ext_ifaces, "go", [], logger=None)
    assert count == 6  # 3 methods × 2 implementors
    callees = {
        r[0]
        for r in cur.execute(
            "SELECT callee FROM graph_edges WHERE edge_type='interface_dispatch'"
        ).fetchall()
    }
    assert "ChoicesModel.Init" in callees
    assert "DamageModel.View" in callees


def test_external_dispatch_go_scoped_by_file_paths():
    conn = _db_with_go_functions([
        ("ChoicesModel.Init", "/a/model.go"),
        ("ChoicesModel.Update", "/a/model.go"),
        ("ChoicesModel.View", "/a/model.go"),
    ])
    cur = conn.cursor()
    ext_ifaces = {"tea.Model": ["Init", "Update", "View"]}
    # Only look at /b/ — no matching functions
    count = _external_interface_dispatch_pass(
        cur, ext_ifaces, "go", ["/b/other.go"], logger=None
    )
    assert count == 0


# ---------------------------------------------------------------------------
# _external_interface_dispatch_pass tests (Rust)
# ---------------------------------------------------------------------------

def test_external_dispatch_rust_uses_double_colon():
    conn = _db_with_go_functions([
        ("MyWriter::write", "/f/lib.rs"),
        ("MyWriter::flush", "/f/lib.rs"),
    ])
    cur = conn.cursor()
    ext_ifaces = {"io::Write": ["write", "flush"]}
    count = _external_interface_dispatch_pass(cur, ext_ifaces, "rust", [], logger=None)
    assert count == 2
    rows = cur.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type='interface_dispatch'"
    ).fetchall()
    callers = {r[0] for r in rows}
    assert "io::Write::write" in callers
    assert "io::Write::flush" in callers
    callees = {r[1] for r in rows}
    assert "MyWriter::write" in callees


def test_external_dispatch_rust_partial_skipped():
    conn = _db_with_go_functions([
        ("MyWriter::write", "/f/lib.rs"),
        # missing flush
    ])
    cur = conn.cursor()
    ext_ifaces = {"io::Write": ["write", "flush"]}
    count = _external_interface_dispatch_pass(cur, ext_ifaces, "rust", [], logger=None)
    assert count == 0


# ---------------------------------------------------------------------------
# persist_all integration test
# ---------------------------------------------------------------------------

GO_MODEL_A = textwrap.dedent("""\
    package models

    type ChoicesModel struct{}

    func (m ChoicesModel) Init() {}
    func (m ChoicesModel) Update(msg string) {}
    func (m ChoicesModel) View() string { return "" }
""")


def test_persist_all_external_interface_go(tmp_path):
    """persist_all picks up external_interfaces.json and creates interface_dispatch edges."""
    src_file = tmp_path / "model.go"
    src_file.write_text(GO_MODEL_A, encoding="utf-8")

    ext_file = tmp_path / "external_interfaces.json"
    ext_file.write_text(
        json.dumps([
            {"interface": "tea.Model", "methods": ["Init", "Update", "View"], "language": "go"}
        ]),
        encoding="utf-8",
    )

    conn = sqlite3.connect(":memory:")
    persist_all(
        conn,
        file_analyses=[],
        graph=[],
        project_prefixes=[str(tmp_path)],
        project_root=str(tmp_path),
    )

    rows = conn.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type='interface_dispatch'"
    ).fetchall()
    callers = {r[0] for r in rows}
    callees = {r[1] for r in rows}
    assert "tea.Model.Init" in callers
    assert "ChoicesModel.Init" in callees
    assert "ChoicesModel.Update" in callees
    assert "ChoicesModel.View" in callees
