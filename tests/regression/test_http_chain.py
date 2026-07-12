"""Regression tests for RM38: HTTP/HTMX → Flask route chain extraction."""
import sqlite3
import textwrap
import pytest

from determined.ingestion.dynamic_edges import (
    extract_flask_route_map,
    extract_htmx_edges,
    extract_js_event_bindings,
    extract_fetch_edges,
    _normalize_url,
    _url_matches,
)
from determined.agent.agent_tools import trace_http_chain


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def test_normalize_plain_url():
    assert _normalize_url('/api/party/create') == '/api/party/create'

def test_normalize_jinja_var():
    assert _normalize_url('/character/{{ id }}/basic') == '/character/*/basic'

def test_normalize_flask_typed_param():
    assert _normalize_url('/character/<int:character_id>/basic') == '/character/*/basic'

def test_normalize_flask_untyped_param():
    assert _normalize_url('/item/<item_id>') == '/item/*'

def test_normalize_strips_trailing_slash():
    assert _normalize_url('/api/foo/') == '/api/foo'

def test_normalize_strips_query_string():
    assert _normalize_url('/api/foo?bar=1') == '/api/foo'


def test_url_matches_exact():
    assert _url_matches('/api/party/create', '/api/party/create')

def test_url_matches_jinja_vs_flask():
    assert _url_matches('/character/{{ id }}/basic', '/character/<int:character_id>/basic')

def test_url_matches_different_paths():
    assert not _url_matches('/api/party/create', '/api/party/join')

def test_url_matches_different_segment_count():
    assert not _url_matches('/api/party', '/api/party/create')


# ---------------------------------------------------------------------------
# extract_flask_route_map
# ---------------------------------------------------------------------------

def test_flask_route_map_simple():
    src = textwrap.dedent("""\
        @app.route('/api/party/create', methods=['POST'])
        def create_party():
            pass
    """)
    m = extract_flask_route_map(src)
    assert m == {'/api/party/create': 'create_party'}

def test_flask_route_map_multiple():
    src = textwrap.dedent("""\
        @app.route('/api/foo')
        def foo(): pass

        @app.route('/api/bar', methods=['POST'])
        def bar(): pass
    """)
    m = extract_flask_route_map(src)
    assert m['/api/foo'] == 'foo'
    assert m['/api/bar'] == 'bar'

def test_flask_route_map_parameterized():
    src = textwrap.dedent("""\
        @app.route('/character/<int:character_id>/basic')
        def character_basic(character_id):
            pass
    """)
    m = extract_flask_route_map(src)
    assert '/character/<int:character_id>/basic' in m
    assert m['/character/<int:character_id>/basic'] == 'character_basic'

def test_flask_route_map_empty():
    assert extract_flask_route_map("def foo(): pass") == {}


# ---------------------------------------------------------------------------
# extract_htmx_edges
# ---------------------------------------------------------------------------

def test_htmx_get_edge():
    html = '<div hx-get="/api/game/date" hx-trigger="load"></div>'
    route_map = {'/api/game/date': 'get_game_date'}
    edges = extract_htmx_edges(html, route_map)
    assert ('__htmx__', 'get_game_date', 'http_fetch') in edges

def test_htmx_post_edge():
    html = '<form hx-post="/character-creation/help" hx-target="#chat"></form>'
    route_map = {'/character-creation/help': 'creation_help'}
    edges = extract_htmx_edges(html, route_map)
    assert ('__htmx__', 'creation_help', 'http_fetch') in edges

def test_htmx_parameterized_url():
    html = '<div hx-get="/character/{{ active_character_id }}/basic"></div>'
    route_map = {'/character/<int:character_id>/basic': 'character_basic'}
    edges = extract_htmx_edges(html, route_map)
    assert ('__htmx__', 'character_basic', 'http_fetch') in edges

def test_htmx_no_match():
    html = '<div hx-get="/api/unknown"></div>'
    route_map = {'/api/game/date': 'get_game_date'}
    edges = extract_htmx_edges(html, route_map)
    assert edges == []

def test_htmx_deduplicates():
    html = '<div hx-get="/api/foo"></div><div hx-get="/api/foo"></div>'
    route_map = {'/api/foo': 'foo_handler'}
    edges = extract_htmx_edges(html, route_map)
    assert edges.count(('__htmx__', 'foo_handler', 'http_fetch')) == 1


# ---------------------------------------------------------------------------
# extract_js_event_bindings
# ---------------------------------------------------------------------------

def test_onclick_binding():
    html = '<button id="enter-dungeon" onclick="enterDungeon()">Enter</button>'
    edges = extract_js_event_bindings(html)
    assert any(e[1] == 'enterDungeon' and e[2] == 'js_event_binding' for e in edges)

def test_onclick_binding_caller_is_element_id():
    html = '<button id="enter-dungeon" onclick="enterDungeon()">Enter</button>'
    edges = extract_js_event_bindings(html)
    match = [e for e in edges if e[1] == 'enterDungeon']
    assert match[0][0] == 'enter-dungeon'

def test_onclick_no_id_uses_placeholder():
    html = '<button onclick="doSomething()">Click</button>'
    edges = extract_js_event_bindings(html)
    match = [e for e in edges if e[1] == 'doSomething']
    assert match[0][0] == '__html_element__'


# ---------------------------------------------------------------------------
# extract_fetch_edges
# ---------------------------------------------------------------------------

def test_fetch_simple():
    js = textwrap.dedent("""\
        function createParty() {
            fetch('/api/party/create', { method: 'POST' });
        }
    """)
    route_map = {'/api/party/create': 'create_party'}
    edges = extract_fetch_edges(js, route_map)
    assert ('createParty', 'create_party', 'http_fetch') in edges

def test_fetch_with_session_helper():
    js = textwrap.dedent("""\
        function joinParty() {
            fetch(withSession('/api/party/join'), { method: 'POST' });
        }
    """)
    route_map = {'/api/party/join': 'join_party'}
    edges = extract_fetch_edges(js, route_map)
    assert ('joinParty', 'join_party', 'http_fetch') in edges

def test_fetch_no_match():
    js = "function foo() { fetch('/api/unknown'); }"
    route_map = {'/api/party/create': 'create_party'}
    edges = extract_fetch_edges(js, route_map)
    assert edges == []

def test_fetch_multiple_in_one_function():
    js = textwrap.dedent("""\
        function doStuff() {
            fetch('/api/foo');
            fetch('/api/bar');
        }
    """)
    route_map = {'/api/foo': 'foo_handler', '/api/bar': 'bar_handler'}
    edges = extract_fetch_edges(js, route_map)
    assert ('doStuff', 'foo_handler', 'http_fetch') in edges
    assert ('doStuff', 'bar_handler', 'http_fetch') in edges


# ---------------------------------------------------------------------------
# trace_http_chain tool
# ---------------------------------------------------------------------------

def _make_db(edges=None, functions=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT, target_id TEXT,
            caller TEXT, callee TEXT,
            line_number INTEGER, caller_file TEXT,
            resolved INTEGER DEFAULT 0,
            edge_type TEXT DEFAULT 'static'
        )
    """)
    conn.execute("""
        CREATE TABLE functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, file_path TEXT,
            decorators_json TEXT,
            is_stub INTEGER DEFAULT 0
        )
    """)
    for e in (edges or []):
        conn.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, edge_type) VALUES (?,?,?,?,?)",
            e,
        )
    for f in (functions or []):
        conn.execute(
            "INSERT INTO functions (name, file_path, decorators_json) VALUES (?,?,?)",
            f,
        )
    conn.commit()
    return conn


class _Oracle:
    def __init__(self, conn):
        self.conn = conn

class _Assessor:
    def __init__(self, conn):
        self.oracle = _Oracle(conn)


def test_trace_http_chain_no_url():
    result = trace_http_chain(_Assessor(_make_db()), {"url": ""})
    assert "url" in result.lower()

def test_trace_http_chain_no_handler():
    conn = _make_db()
    result = trace_http_chain(_Assessor(conn), {"url": "/api/unknown"})
    assert "No Flask handler found" in result

def test_trace_http_chain_shows_htmx_caller():
    conn = _make_db(
        edges=[
            ("__htmx__", "get_game_date", "__htmx__", "get_game_date", "http_fetch"),
            ("get_game_date", "some_service", "get_game_date", "some_service", "static"),
        ],
        functions=[
            ("get_game_date", "world_app.py", '["/api/game/date route"]'),
        ],
    )
    result = trace_http_chain(_Assessor(conn), {"url": "/api/game/date"})
    assert "get_game_date" in result
    assert "HTMX" in result

def test_trace_http_chain_shows_js_caller():
    conn = _make_db(
        edges=[
            ("createParty", "create_party", "createParty", "create_party", "http_fetch"),
            ("enter-dungeon", "createParty", "enter-dungeon", "createParty", "js_event_binding"),
            ("create_party", "party_service", "create_party", "party_service", "static"),
        ],
        functions=[
            ("create_party", "world_app.py", '["/api/party/create route"]'),
        ],
    )
    result = trace_http_chain(_Assessor(conn), {"url": "/api/party/create"})
    assert "create_party" in result
    assert "createParty" in result
    assert "enter-dungeon" in result
