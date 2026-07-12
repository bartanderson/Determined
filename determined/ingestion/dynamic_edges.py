"""
Virtual and dynamic edge detection.

All functions return (caller, callee, edge_type) triples.
Callers that live outside the Python AST use synthetic source symbols:
  __js_client__   - JavaScript browser caller (socket.emit)
  __http_client__ - HTTP caller (@app.route)
  __htmx__        - HTMX attribute on an HTML element (hx-get/hx-post)
  __abc_base__    - abstract base class polymorphic dispatch
  __annotation__  - manually declared in virtual_edges.json

edge_type values:
  'static'          - normal AST call (handled by parse_ast.py)
  'dynamic'         - dict-of-callables dispatch (TOOLS, TASK_PATTERNS, etc.)
  'thread'          - threading.Thread(target=fn) implicit call
  'decorator'       - @framework.on/route registration (socketio, Flask)
  'cross_language'  - JS browser → Python socket handler
  'polymorphic'     - ABC base → concrete subclass (manual or Item-20 derived)
  'annotation'      - manually declared in virtual_edges.json
  'js_event_binding'- DOM element → JS function (onclick / addEventListener)
  'http_fetch'      - JS fetch() or HTMX hx-get/hx-post → Flask route handler
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Gap 2 — dict-of-callables dispatch  (TOOLS, TASK_PATTERNS, …)
# ---------------------------------------------------------------------------

def extract_dispatch_dict_edges(source: str) -> list[tuple[str, str, str]]:
    """
    Detect NAME = {"key": (fn, ...), ...} + function that does NAME[key].
    Returns (dispatcher_fn, callee_fn, 'dynamic') triples.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    dispatch_dicts: dict[str, set[str]] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            callables: set[str] = set()
            for val in node.value.values:
                if val is None:
                    continue
                if isinstance(val, ast.Tuple) and val.elts:
                    first = val.elts[0]
                    if isinstance(first, ast.Name):
                        callables.add(first.id)
                elif isinstance(val, ast.Name):
                    callables.add(val.id)
            if callables:
                dispatch_dicts[target.id] = callables

    if not dispatch_dicts:
        return []

    edges: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fn_name = node.name
        for child in ast.walk(node):
            if not isinstance(child, ast.Subscript):
                continue
            if not isinstance(child.value, ast.Name):
                continue
            dict_name = child.value.id
            if dict_name in dispatch_dicts:
                for callee in dispatch_dicts[dict_name]:
                    edges.append((fn_name, callee, 'dynamic'))

    return list(dict.fromkeys(edges))


# ---------------------------------------------------------------------------
# Gap 3 — threading.Thread(target=fn) implicit calls
# ---------------------------------------------------------------------------

def extract_thread_target_edges(source: str) -> list[tuple[str, str, str]]:
    """
    Detect threading.Thread(target=fn) calls inside a function body.
    Returns (enclosing_fn, target_fn, 'thread') triples.
    The thread start is an implicit call to target; no static edge exists.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    edges: list[tuple[str, str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fn_name = node.name
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            # Match Thread(...) or threading.Thread(...)
            func = child.func
            is_thread = (
                (isinstance(func, ast.Name) and func.id == 'Thread') or
                (isinstance(func, ast.Attribute) and func.attr == 'Thread')
            )
            if not is_thread:
                continue
            for kw in child.keywords:
                if kw.arg == 'target' and isinstance(kw.value, ast.Name):
                    edges.append((fn_name, kw.value.id, 'thread'))

    return list(dict.fromkeys(edges))


# ---------------------------------------------------------------------------
# Gap 4 — decorator-registered entry points (@socketio.on, @app.route)
# ---------------------------------------------------------------------------

def extract_decorator_entry_edges(source: str) -> list[tuple[str, str, str]]:
    """
    Detect @obj.on("event") and @obj.route("/path") decorators.
    Returns (__js_client__, handler_fn, 'decorator') for socketio.on
    and    (__http_client__, handler_fn, 'decorator') for app.route.
    The synthetic caller nodes mark these as framework-registered entry points.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    edges: list[tuple[str, str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not isinstance(func, ast.Attribute):
                continue
            attr = func.attr
            if attr == 'on':
                edges.append(('__js_client__', node.name, 'decorator'))
            elif attr == 'route':
                edges.append(('__http_client__', node.name, 'decorator'))

    return list(dict.fromkeys(edges))


# ---------------------------------------------------------------------------
# Gap 7 — JS → Python cross-language socket edges
# Scan an HTML/JS source for socket.emit("event") and match to known handlers.
# ---------------------------------------------------------------------------

_EMIT_RE = re.compile(r'socket\.emit\(\s*["\'](\w+)["\']')


def extract_cross_language_edges(
    html_source: str,
    socketio_handlers: dict[str, str],
) -> list[tuple[str, str, str]]:
    """
    Match JS socket.emit("event") calls to Python @socketio.on("event") handlers.

    socketio_handlers: {event_name: handler_fn_name} — built from the Python source
    by extract_socketio_handler_map().

    Returns (__js_client__, handler_fn, 'cross_language') triples for every
    emit that has a matching Python handler.
    """
    event_names = _EMIT_RE.findall(html_source)
    edges: list[tuple[str, str, str]] = []
    for event in event_names:
        handler = socketio_handlers.get(event)
        if handler:
            edges.append(('__js_client__', handler, 'cross_language'))
    return list(dict.fromkeys(edges))


def extract_socketio_handler_map(source: str) -> dict[str, str]:
    """
    Parse Python source and return {event_name: handler_fn_name} for every
    @socketio.on("event") decorated function.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    handlers: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not (isinstance(func, ast.Attribute) and func.attr == 'on'):
                continue
            if dec.args and isinstance(dec.args[0], ast.Constant):
                handlers[dec.args[0].value] = node.name

    return handlers


# ---------------------------------------------------------------------------
# RM38 — HTTP/HTMX → Flask route chain
#
# Three extractors + one normalizer:
#   extract_flask_route_map(py_src)           -> {pattern: handler_fn}
#   extract_htmx_edges(html_src, route_map)   -> [(caller, handler, 'http_fetch')]
#   extract_js_event_bindings(html_src)        -> [(element_id, js_fn, 'js_event_binding')]
#   extract_fetch_edges(js_src, route_map)     -> [(js_fn, handler, 'http_fetch')]
#
# URL normalization: Jinja2 {{var}} and Flask <type:var> both become the same
# wildcard so "/character/{{ id }}/basic" matches "/character/<int:id>/basic".
# ---------------------------------------------------------------------------

_JINJA_VAR_RE = re.compile(r'\{\{[^}]+\}\}')
_FLASK_PARAM_RE = re.compile(r'<(?:[^:>]+:)?([^>]+)>')


def _normalize_url(url: str) -> str:
    """Normalize a URL to a matchable pattern.

    Replaces Jinja2 {{ var }} and Flask <type:var> / <var> with '*'.
    Strips trailing slashes and query strings.
    """
    url = url.split('?')[0].rstrip('/')
    url = _JINJA_VAR_RE.sub('*', url)
    url = _FLASK_PARAM_RE.sub('*', url)
    return url


def _url_matches(client_url: str, flask_pattern: str) -> bool:
    """Return True if a client URL (possibly with Jinja vars) matches a Flask route pattern."""
    norm_client = _normalize_url(client_url)
    norm_flask = _normalize_url(flask_pattern)
    if norm_client == norm_flask:
        return True
    # Segment-by-segment wildcard match
    c_parts = norm_client.split('/')
    f_parts = norm_flask.split('/')
    if len(c_parts) != len(f_parts):
        return False
    return all(f == '*' or c == '*' or c == f for c, f in zip(c_parts, f_parts))


def extract_flask_route_map(source: str) -> dict[str, str]:
    """
    Parse Python source and return {url_pattern: handler_fn_name} for every
    @app.route("/path") or @blueprint.route("/path") decorated function.
    Patterns are stored as-is (with Flask <type:var> syntax); normalization
    happens at match time via _url_matches().
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    routes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not (isinstance(func, ast.Attribute) and func.attr == 'route'):
                continue
            if dec.args and isinstance(dec.args[0], ast.Constant):
                routes[dec.args[0].value] = node.name
    return routes


def _match_route(url: str, route_map: dict[str, str]) -> str | None:
    """Return the handler function name for url, or None if no match."""
    for pattern, handler in route_map.items():
        if _url_matches(url, pattern):
            return handler
    return None


# HTMX attribute patterns: hx-get="url" hx-post="url"
_HTMX_RE = re.compile(
    r'hx-(?:get|post|put|patch|delete)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# HTML element id preceding an HTMX attribute (best-effort: id="name" ... hx-*)
_ELEM_ID_RE = re.compile(r'id\s*=\s*["\']([^"\']+)["\']')


def extract_htmx_edges(
    html_src: str,
    route_map: dict[str, str],
) -> list[tuple[str, str, str]]:
    """
    Scan HTML for hx-get/hx-post/hx-put/hx-patch/hx-delete attributes.
    Match each URL to a Flask handler via route_map.
    Caller is '__htmx__' (no JS function intermediary for HTMX).
    Returns (__htmx__, handler_fn, 'http_fetch') triples.
    """
    edges: list[tuple[str, str, str]] = []
    for m in _HTMX_RE.finditer(html_src):
        url = m.group(1)
        handler = _match_route(url, route_map)
        if handler:
            edges.append(('__htmx__', handler, 'http_fetch'))
    return list(dict.fromkeys(edges))


# onclick="fn()" or onclick='fn(args)'
_ONCLICK_RE = re.compile(r'onclick\s*=\s*["\'](\w+)\s*\(', re.IGNORECASE)
# onsubmit="fn()" etc.
_ONSUBMIT_RE = re.compile(r'on\w+\s*=\s*["\'](\w+)\s*\(', re.IGNORECASE)


def extract_js_event_bindings(html_src: str) -> list[tuple[str, str, str]]:
    """
    Scan HTML for inline event handlers: onclick="fn()", onsubmit="fn()", etc.
    Returns (element_ref, js_fn_name, 'js_event_binding') triples.
    element_ref is the element's id if detectable, otherwise '__html_element__'.

    Note: addEventListener() bindings in .js files are NOT captured here
    because they require correlating a selector string to an element at runtime.
    Inline handlers are static and always capturable.
    """
    edges: list[tuple[str, str, str]] = []
    # Split into rough tag blocks and look for id + on* handler together
    # Simple approach: find all on* handlers; use nearby id= as caller if present
    for m in _ONSUBMIT_RE.finditer(html_src):
        fn_name = m.group(1)
        # Look back up to 300 chars for an id= attribute
        start = max(0, m.start() - 300)
        preceding = html_src[start:m.start()]
        id_match = list(_ELEM_ID_RE.finditer(preceding))
        caller = id_match[-1].group(1) if id_match else '__html_element__'
        edges.append((caller, fn_name, 'js_event_binding'))
    return list(dict.fromkeys(edges))


# fetch('/url', ...) or fetch("/url", ...) or fetch(withSession('/url'), ...)
_FETCH_URL_RE = re.compile(
    r'\bfetch\s*\(\s*(?:\w+\s*\(\s*)?["\']([^"\']+)["\']',
)
# JS function declaration: function fnName( or async function fnName(
_JS_FN_RE = re.compile(r'(?:async\s+)?function\s+(\w+)\s*\(')


def extract_fetch_edges(
    js_src: str,
    route_map: dict[str, str],
) -> list[tuple[str, str, str]]:
    """
    Scan JS source for fetch('/url') calls inside named functions.
    Match URL to Flask handler via route_map.
    Returns (js_fn_name, handler_fn, 'http_fetch') triples.
    Caller is the enclosing JS function name, or '__js_fetch__' if at module level.
    """
    edges: list[tuple[str, str, str]] = []

    # Build list of (fn_name, start_pos) sorted by position
    fn_positions = [(m.group(1), m.start()) for m in _JS_FN_RE.finditer(js_src)]

    def _enclosing_fn(pos: int) -> str:
        """Return the name of the JS function that contains pos."""
        caller = '__js_fetch__'
        for fn_name, fn_start in fn_positions:
            if fn_start <= pos:
                caller = fn_name
        return caller

    for m in _FETCH_URL_RE.finditer(js_src):
        url = m.group(1)
        handler = _match_route(url, route_map)
        if handler:
            caller = _enclosing_fn(m.start())
            edges.append((caller, handler, 'http_fetch'))

    return list(dict.fromkeys(edges))


# ---------------------------------------------------------------------------
# Gap 8 / general — manually declared virtual edges (virtual_edges.json)
#
# Format:
# [
#   {"source": "__abc_base__:DBOracle.query", "target": "ConcreteOracle.query",
#    "type": "polymorphic", "note": "why this edge exists"},
#   {"source": "__annotation__:external_scheduler", "target": "run_job",
#    "type": "annotation", "note": "cron invokes this daily"}
# ]
# ---------------------------------------------------------------------------

def load_virtual_edge_annotations(
    annotation_file: str | Path,
) -> list[tuple[str, str, str]]:
    """
    Load manually declared virtual edges from virtual_edges.json.
    Returns (source, target, edge_type) triples.
    Missing or malformed file returns [].
    """
    path = Path(annotation_file)
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []

    edges: list[tuple[str, str, str]] = []
    for entry in entries:
        src = entry.get('source', '').strip()
        tgt = entry.get('target', '').strip()
        etype = entry.get('type', 'annotation').strip()
        if src and tgt:
            edges.append((src, tgt, etype))
    return edges


# ---------------------------------------------------------------------------
# Convenience: run all Python-side detectors on one source file
# ---------------------------------------------------------------------------

def extract_all_dynamic_edges(source: str) -> list[tuple[str, str, str]]:
    """
    Run every Python-source detector and return combined (caller, callee, edge_type).
    Does not include cross_language or annotation edges — those need extra inputs.
    """
    results: list[tuple[str, str, str]] = []
    results.extend(extract_dispatch_dict_edges(source))
    results.extend(extract_thread_target_edges(source))
    results.extend(extract_decorator_entry_edges(source))
    return list(dict.fromkeys(results))
