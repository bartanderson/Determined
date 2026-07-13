# tests/regression/test_dynamic_edges.py
# Unit tests for dynamic/virtual edge detection.

from determined.ingestion.dynamic_edges import (
    extract_dispatch_dict_edges,
    extract_thread_target_edges,
    extract_decorator_entry_edges,
    extract_socketio_handler_map,
    extract_cross_language_edges,
    load_virtual_edge_annotations,
    extract_all_dynamic_edges,
    extract_flask_route_map,
    extract_htmx_edges,
    extract_js_event_bindings,
    extract_fetch_edges,
    _url_matches,
)


def test_dispatch_dict_edges():
    src = """
TOOLS = {"search": (search_fn, "oracle"), "list": (list_fn, "oracle")}

def dispatch(name, args):
    fn, layer = TOOLS[name]
    return fn(args)
"""
    edges = extract_dispatch_dict_edges(src)
    callees = {e[1] for e in edges}
    assert 'search_fn' in callees
    assert 'list_fn' in callees
    assert all(e[2] == 'dynamic' for e in edges)


def test_thread_target_edges():
    src = """
import threading

def handle_query(data):
    def _run():
        pass
    threading.Thread(target=_run, daemon=True).start()
"""
    edges = extract_thread_target_edges(src)
    assert ('handle_query', '_run', 'thread') in edges


def test_decorator_entry_edges_socketio():
    src = """
@socketio.on("query")
def handle_query(data):
    pass

@socketio.on("ingest")
def handle_ingest(data):
    pass
"""
    edges = extract_decorator_entry_edges(src)
    targets = {e[1] for e in edges}
    assert 'handle_query' in targets
    assert 'handle_ingest' in targets
    assert all(e[0] == '__js_client__' for e in edges)
    assert all(e[2] == 'decorator' for e in edges)


def test_decorator_entry_edges_flask():
    src = """
@app.route("/")
def index():
    pass
"""
    edges = extract_decorator_entry_edges(src)
    assert ('__http_client__', 'index', 'decorator') in edges


def test_socketio_handler_map():
    src = """
@socketio.on("query")
def handle_query(data): pass

@socketio.on("scan")
def handle_scan(data): pass
"""
    hmap = extract_socketio_handler_map(src)
    assert hmap.get('query') == 'handle_query'
    assert hmap.get('scan') == 'handle_scan'


def test_cross_language_edges():
    html = 'socket.emit("query", {q}); socket.emit("scan", {path});'
    handler_map = {'query': 'handle_query', 'scan': 'handle_scan'}
    edges = extract_cross_language_edges(html, handler_map)
    targets = {e[1] for e in edges}
    assert 'handle_query' in targets
    assert 'handle_scan' in targets
    assert all(e[0] == '__js_client__' for e in edges)
    assert all(e[2] == 'cross_language' for e in edges)


def test_cross_language_edges_no_match():
    html = 'socket.emit("unknown_event", {});'
    edges = extract_cross_language_edges(html, {'query': 'handle_query'})
    assert edges == []


def test_load_virtual_edge_annotations(tmp_path):
    annotation = tmp_path / 'virtual_edges.json'
    annotation.write_text('[{"source": "__abc_base__:Base.run", "target": "ConcreteImpl.run", "type": "polymorphic", "note": "abc dispatch"}]')
    edges = load_virtual_edge_annotations(annotation)
    assert len(edges) == 1
    assert edges[0] == ('__abc_base__:Base.run', 'ConcreteImpl.run', 'polymorphic')


def test_load_virtual_edge_annotations_missing(tmp_path):
    edges = load_virtual_edge_annotations(tmp_path / 'nonexistent.json')
    assert edges == []


def test_extract_all_dynamic_edges():
    src = """
import threading
TOOLS = {"fn": (my_fn, "oracle")}

@socketio.on("go")
def handle_go(data):
    fn, _ = TOOLS["fn"]
    threading.Thread(target=worker, daemon=True).start()

def dispatch(name):
    fn, _ = TOOLS[name]
    return fn()

def worker(): pass
"""
    edges = extract_all_dynamic_edges(src)
    etypes = {e[2] for e in edges}
    assert 'dynamic' in etypes
    assert 'thread' in etypes
    assert 'decorator' in etypes


def test_polymorphic_edges_auto_generated():
    """
    _persist_polymorphic_edges should emit AbstractBase.method → ConcreteSubclass.method
    for every abstract method that has a concrete override in a subclass.
    """
    import sqlite3, json
    from determined.persistence.persistence_engine import _persist_polymorphic_edges
    from determined.identity.symbol_identity import normalize_symbol, all_name_forms

    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE classes (
            name TEXT, methods_json TEXT, base_classes_json TEXT, file_path TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE functions (
            name TEXT, file_path TEXT, decorators_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE graph_edges (
            id INTEGER PRIMARY KEY, source_id TEXT, target_id TEXT,
            caller TEXT, callee TEXT, edge_type TEXT DEFAULT 'static'
        )
    """)
    conn.execute("""
        CREATE TABLE symbol_names (
            id INTEGER PRIMARY KEY, canonical_id TEXT, name TEXT, name_type TEXT
        )
    """)

    # ABC base class with two abstract methods
    conn.execute("INSERT INTO classes VALUES (?,?,?,?)", (
        "BaseProcessor", json.dumps(["process", "validate"]), json.dumps(["ABC"]), "base.py"
    ))
    conn.execute("INSERT INTO functions VALUES (?,?,?)",
                 ("process", "base.py", json.dumps(["abstractmethod"])))
    conn.execute("INSERT INTO functions VALUES (?,?,?)",
                 ("validate", "base.py", json.dumps(["abstractmethod"])))

    # Concrete subclass that overrides both
    conn.execute("INSERT INTO classes VALUES (?,?,?,?)", (
        "ConcreteProcessor", json.dumps(["process", "validate", "helper"]),
        json.dumps(["BaseProcessor"]), "concrete.py"
    ))

    conn.commit()

    seen: set = set()
    inserted: list[tuple[str, str, str]] = []

    def _capture(src, tgt, etype):
        inserted.append((src, tgt, etype))
        src_id = normalize_symbol(src)
        tgt_id = normalize_symbol(tgt)
        conn.execute(
            "INSERT INTO graph_edges (source_id, target_id, caller, callee, edge_type) VALUES (?,?,?,?,?)",
            (src_id, tgt_id, src, tgt, etype)
        )
        for name, ntype in all_name_forms(src):
            k = (src_id, name)
            if k not in seen:
                seen.add(k)
                conn.execute("INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)", (src_id, name, ntype))
        for name, ntype in all_name_forms(tgt):
            k = (tgt_id, name)
            if k not in seen:
                seen.add(k)
                conn.execute("INSERT OR IGNORE INTO symbol_names (canonical_id, name, name_type) VALUES (?,?,?)", (tgt_id, name, ntype))
        conn.commit()

    cursor = conn.cursor()
    _persist_polymorphic_edges(conn, cursor, _capture)

    srcs = {e[0] for e in inserted}
    tgts = {e[1] for e in inserted}
    assert "BaseProcessor.process" in srcs
    assert "BaseProcessor.validate" in srcs
    assert "ConcreteProcessor.process" in tgts
    assert "ConcreteProcessor.validate" in tgts
    assert all(e[2] == 'polymorphic' for e in inserted)


# ---------------------------------------------------------------------------
# RM41 — HTTP fetch / HTMX → Flask route chain
# ---------------------------------------------------------------------------

def test_flask_route_map_basic():
    src = """
@app.route('/api/users')
def list_users():
    pass

@app.route('/api/users/<int:id>', methods=['GET', 'POST'])
def get_user(id):
    pass
"""
    routes = extract_flask_route_map(src)
    assert routes.get('/api/users') == 'list_users'
    assert routes.get('/api/users/<int:id>') == 'get_user'


def test_flask_route_map_blueprint():
    src = """
@bp.route('/items')
def list_items():
    pass
"""
    routes = extract_flask_route_map(src)
    assert routes.get('/items') == 'list_items'


def test_flask_route_map_no_routes():
    src = "def plain(): pass"
    assert extract_flask_route_map(src) == {}


def test_url_matches_exact():
    assert _url_matches('/api/users', '/api/users')


def test_url_matches_flask_param():
    assert _url_matches('/api/users/42', '/api/users/<int:id>')


def test_url_matches_jinja_var():
    assert _url_matches('/api/users/{{ user_id }}', '/api/users/<int:id>')


def test_url_matches_different_lengths():
    assert not _url_matches('/api/users', '/api/users/extra')


def test_htmx_edges_hx_get():
    html = '<div hx-get="/api/status" hx-trigger="load"></div>'
    route_map = {'/api/status': 'get_status'}
    edges = extract_htmx_edges(html, route_map)
    assert ('__htmx__', 'get_status', 'http_fetch') in edges


def test_htmx_edges_hx_post():
    html = '<form hx-post="/api/submit">...</form>'
    route_map = {'/api/submit': 'handle_submit'}
    edges = extract_htmx_edges(html, route_map)
    assert ('__htmx__', 'handle_submit', 'http_fetch') in edges


def test_htmx_edges_no_match():
    html = '<div hx-get="/api/unknown"></div>'
    route_map = {'/api/status': 'get_status'}
    assert extract_htmx_edges(html, route_map) == []


def test_htmx_edges_flask_param_match():
    html = '<div hx-get="/api/users/{{ user_id }}"></div>'
    route_map = {'/api/users/<int:id>': 'get_user'}
    edges = extract_htmx_edges(html, route_map)
    assert ('__htmx__', 'get_user', 'http_fetch') in edges


def test_js_event_bindings_onclick():
    html = '<button id="save-btn" onclick="saveData()">Save</button>'
    edges = extract_js_event_bindings(html)
    targets = {e[1] for e in edges}
    assert 'saveData' in targets
    assert all(e[2] == 'js_event_binding' for e in edges)


def test_js_event_bindings_no_id():
    html = '<button onclick="doThing()">Click</button>'
    edges = extract_js_event_bindings(html)
    assert any(e[1] == 'doThing' for e in edges)
    # caller falls back to __html_element__ when no id
    callers = {e[0] for e in edges}
    assert '__html_element__' in callers


def test_fetch_edges_named_function():
    js = """
async function loadUser() {
    const r = await fetch('/api/users');
    return r.json();
}
"""
    route_map = {'/api/users': 'list_users'}
    edges = extract_fetch_edges(js, route_map)
    assert ('loadUser', 'list_users', 'http_fetch') in edges


def test_fetch_edges_no_match():
    js = "async function foo() { fetch('/api/unknown'); }"
    route_map = {'/api/users': 'list_users'}
    assert extract_fetch_edges(js, route_map) == []


def test_fetch_edges_module_level():
    js = "fetch('/api/ping');"
    route_map = {'/api/ping': 'ping'}
    edges = extract_fetch_edges(js, route_map)
    assert any(e[1] == 'ping' and e[2] == 'http_fetch' for e in edges)
