"""Regression tests for RM57: cross-language data flow linking."""
import ast
import json
import sqlite3
import textwrap
import pytest

from determined.ingestion.parse_ast import _extract_functions
from determined.ingestion.language_walker import LanguageWalker
from determined.ingestion.cross_language_linker import (
    run_cross_language_link,
    _lookup_response_shape,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_functions(source: str):
    tree = ast.parse(textwrap.dedent(source))
    return _extract_functions(tree)


def _make_db(fetch_edges=None, response_shapes=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            target_id TEXT,
            caller TEXT,
            callee TEXT,
            line_number INTEGER,
            caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            edge_type TEXT DEFAULT 'static'
        )
    """)
    conn.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE knowledge_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            kind TEXT,
            content TEXT,
            provenance TEXT,
            created_at TEXT,
            file_hash TEXT,
            needs_review INTEGER DEFAULT 0,
            corpus TEXT
        )
    """)
    for caller, callee in (fetch_edges or []):
        conn.execute(
            "INSERT INTO graph_edges (caller, callee, edge_type, resolved) VALUES (?, ?, 'http_fetch', 1)",
            (caller, callee),
        )
    for subject, keys in (response_shapes or {}).items():
        conn.execute(
            "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at, needs_review) "
            "VALUES (?, 'response_shape', ?, 'ast', '2026-01-01', 0)",
            (subject, json.dumps(keys)),
        )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Python: response_shape extraction from parse_ast
# ---------------------------------------------------------------------------

def test_response_shape_jsonify_dict():
    source = """
    @app.route('/api/foo')
    def get_foo():
        return jsonify({"name": x, "count": y})
    """
    fns = _parse_functions(source)
    assert len(fns) == 1
    assert set(fns[0].response_shape) == {"name", "count"}


def test_response_shape_jsonify_kwargs():
    source = """
    @app.route('/api/bar')
    def get_bar():
        return jsonify(status="ok", value=42)
    """
    fns = _parse_functions(source)
    assert fns[0].response_shape == ["status", "value"]


def test_response_shape_return_dict():
    source = """
    @app.route('/api/baz')
    def get_baz():
        return {"result": data, "error": None}
    """
    fns = _parse_functions(source)
    assert set(fns[0].response_shape) == {"result", "error"}


def test_response_shape_no_route():
    source = """
    def helper():
        return {"key": val}
    """
    fns = _parse_functions(source)
    assert fns[0].response_shape == []


def test_response_shape_empty_when_no_return():
    source = """
    @app.route('/api/noop')
    def noop():
        pass
    """
    fns = _parse_functions(source)
    assert fns[0].response_shape == []


# ---------------------------------------------------------------------------
# JS: response_consumers extraction
# ---------------------------------------------------------------------------

def test_response_consumers_destructuring():
    source = """
    async function loadData() {
        const {name, count} = await resp.json();
        console.log(name);
    }
    """
    w = LanguageWalker(source, "app.js", "javascript")
    consumers = dict(w.response_consumers())
    assert "app.loadData" in consumers
    keys = consumers["app.loadData"]
    assert "name" in keys
    assert "count" in keys


def test_response_consumers_property_access():
    source = """
    async function showUser() {
        const data = await resp.json();
        console.log(data.username);
    }
    """
    w = LanguageWalker(source, "app.js", "javascript")
    consumers = dict(w.response_consumers())
    # property access on json() result should surface "username"
    assert "app.showUser" in consumers
    assert "username" in consumers["app.showUser"]


def test_response_consumers_no_json_call():
    source = """
    function plain() {
        const x = {name: "foo"};
        console.log(x.name);
    }
    """
    w = LanguageWalker(source, "app.js", "javascript")
    consumers = dict(w.response_consumers())
    # No .json() call — should not surface
    assert "app.plain" not in consumers


# ---------------------------------------------------------------------------
# _lookup_response_shape
# ---------------------------------------------------------------------------

def test_lookup_exact_match():
    shapes = {"get_foo": ["name", "count"]}
    assert _lookup_response_shape("get_foo", shapes) == ["name", "count"]


def test_lookup_bare_name():
    shapes = {"get_foo": ["name", "count"]}
    assert _lookup_response_shape("routes.get_foo", shapes) == ["name", "count"]


def test_lookup_no_match():
    shapes = {"get_foo": ["name", "count"]}
    assert _lookup_response_shape("get_bar", shapes) is None


# ---------------------------------------------------------------------------
# run_cross_language_link integration
# ---------------------------------------------------------------------------

def test_link_emits_cross_language_edge(tmp_path):
    conn = _make_db(
        fetch_edges=[("app.fetchUser", "get_user")],
        response_shapes={"get_user": ["id", "name"]},
    )
    count = run_cross_language_link(conn, tmp_path)
    assert count == 1
    row = conn.execute(
        "SELECT * FROM graph_edges WHERE edge_type = 'cross_language'"
    ).fetchone()
    assert row is not None
    assert row["caller"] == "app.fetchUser"
    assert row["callee"] == "get_user"


def test_link_no_fetch_edges(tmp_path):
    conn = _make_db(
        fetch_edges=[],
        response_shapes={"get_user": ["id", "name"]},
    )
    count = run_cross_language_link(conn, tmp_path)
    assert count == 0


def test_link_no_response_shapes(tmp_path):
    """cross_language edge is emitted even when no response_shape artifacts exist."""
    conn = _make_db(
        fetch_edges=[("app.fetchUser", "get_user")],
        response_shapes={},
    )
    count = run_cross_language_link(conn, tmp_path)
    assert count == 1
    row = conn.execute(
        "SELECT * FROM graph_edges WHERE edge_type = 'cross_language'"
    ).fetchone()
    assert row is not None
    assert row["caller"] == "app.fetchUser"
    assert row["callee"] == "get_user"


def test_link_mismatch_stored_as_artifact(tmp_path):
    """When consumed keys are not in response shape, a response_mismatch artifact is stored."""
    # Create a real JS file for the consumer map
    js_file = tmp_path / "app.js"
    js_file.write_text("""
    async function fetchUser() {
        const {id, name, email} = await resp.json();
        console.log(id);
    }
    """)
    conn = _make_db(
        fetch_edges=[("app.fetchUser", "get_user")],
        response_shapes={"get_user": ["id", "name"]},
    )
    conn.execute("INSERT INTO files (file_path) VALUES (?)", (str(js_file),))
    conn.commit()

    count = run_cross_language_link(conn, tmp_path)
    assert count == 1

    row = conn.execute(
        "SELECT * FROM knowledge_artifacts WHERE kind = 'response_mismatch'"
    ).fetchone()
    assert row is not None
    data = json.loads(row["content"])
    assert "email" in data["missing_keys"]


def test_link_socketio_emit_to_handler(tmp_path):
    """socket.emit in JS wires to @socketio.on Python handler as cross_language edge."""
    py_file = tmp_path / "server.py"
    py_file.write_text(textwrap.dedent("""\
        @socketio.on("join_room")
        def handle_join(data):
            pass
    """))
    js_file = tmp_path / "client.js"
    js_file.write_text(textwrap.dedent("""\
        function joinRoom() {
            socket.emit("join_room", { id: roomId });
        }
    """))

    conn = _make_db(fetch_edges=[], response_shapes={})
    conn.execute("INSERT INTO files (file_path) VALUES (?)", (str(py_file),))
    conn.execute("INSERT INTO files (file_path) VALUES (?)", (str(js_file),))
    conn.commit()

    count = run_cross_language_link(conn, tmp_path)
    assert count == 1

    row = conn.execute(
        "SELECT * FROM graph_edges WHERE edge_type = 'cross_language'"
    ).fetchone()
    assert row is not None
    assert row["callee"] == "handle_join"
    assert "joinRoom" in row["caller"]
