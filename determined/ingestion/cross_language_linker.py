"""
Cross-language data flow linking pass (RM57).

After JS/TS files are ingested (RM54 call edges, RM55 data flow edges),
this pass joins:
  1. http_fetch edges  (JS fn -> Python Flask handler)
  2. response_shape artifacts  (Python handler -> JSON keys it returns)
  3. response_consumers  (JS fn -> JSON keys it reads from responses)

And emits cross_language data_flow edges into graph_edges:
  caller=js_fn, callee=flask_handler, edge_type='data_flow'

Plus response_mismatch knowledge_artifacts when consumed keys are not
in the response shape (surfaced by design_gaps / check_design_violations).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from determined.ingestion.language_walker import LanguageWalker
from determined.ingestion.dynamic_edges import (
    extract_js_socketio_edges,
    extract_socketio_handler_map,
)


def run_cross_language_link(conn: sqlite3.Connection, corpus_root: Path) -> int:
    """
    Run the cross-language linking pass over all JS/TS files in the corpus.
    Returns the number of cross_language edges emitted (http_fetch + socketio).
    """
    cur = conn.cursor()

    # 1. Collect http_fetch edges: (js_fn_caller, flask_handler_callee)
    cur.execute(
        "SELECT caller, callee FROM graph_edges WHERE edge_type = 'http_fetch'"
    )
    fetch_edges: list[tuple[str, str]] = cur.fetchall()

    # 2. Load response_shape artifacts: handler_fn_name -> [keys]
    cur.execute(
        "SELECT subject, content FROM knowledge_artifacts WHERE kind = 'response_shape'"
    )
    response_shapes: dict[str, list[str]] = {}
    for subject, content in cur.fetchall():
        try:
            keys = json.loads(content)
            if isinstance(keys, list):
                response_shapes[subject] = keys
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Build socketio handler map from Python files in corpus
    socketio_handlers: dict[str, str] = {}
    cur.execute("SELECT DISTINCT file_path FROM files WHERE file_path LIKE '%.py'")
    for (py_fp,) in cur.fetchall():
        p = Path(py_fp)
        if not p.exists():
            continue
        try:
            socketio_handlers.update(
                extract_socketio_handler_map(p.read_text(encoding="utf-8", errors="ignore"))
            )
        except Exception:
            continue

    # 4. Load JS/TS files for consumer map and socket.emit extraction
    cur.execute(
        "SELECT DISTINCT file_path FROM files WHERE "
        "file_path LIKE '%.js' OR file_path LIKE '%.ts' "
        "OR file_path LIKE '%.jsx' OR file_path LIKE '%.tsx'"
    )
    js_files = [row[0] for row in cur.fetchall()]

    consumer_map: dict[str, set[str]] = {}
    socketio_emit_edges: list[tuple[str, str, str]] = []

    for file_path in js_files:
        p = Path(file_path)
        if not p.exists():
            continue
        try:
            source = p.read_text(encoding="utf-8", errors="ignore")
            lang = _lang_from_path(file_path)
            walker = LanguageWalker(source, file_path, lang)
            if response_shapes:
                for fn_fqdn, keys in walker.response_consumers():
                    consumer_map.setdefault(fn_fqdn, set()).update(keys)
            if socketio_handlers:
                socketio_emit_edges.extend(
                    extract_js_socketio_edges(source, socketio_handlers, file_path)
                )
        except Exception:
            continue

    # 5. Delete stale cross_language edges before re-emitting
    cur.execute("DELETE FROM graph_edges WHERE edge_type = 'cross_language'")

    count = 0
    created_at = datetime.now(timezone.utc).isoformat()

    from determined.identity.edge_identity import edge_identity

    def _insert_edge(caller: str, callee: str) -> None:
        nonlocal count
        src_id, tgt_id = edge_identity(caller, callee)
        cur.execute(
            "INSERT OR IGNORE INTO graph_edges "
            "(source_id, target_id, caller, callee, edge_type, resolved) "
            "VALUES (?, ?, ?, ?, 'cross_language', 1)",
            (src_id, tgt_id, caller, callee),
        )
        count += 1

    # 6. Emit cross_language edges for every http_fetch edge unconditionally
    for js_fn, handler in fetch_edges:
        _insert_edge(js_fn, handler)

        # Optional: emit response_mismatch artifact when shape data is available
        shape_keys = _lookup_response_shape(handler, response_shapes)
        consumed = consumer_map.get(js_fn, set())
        if shape_keys and consumed:
            missing = consumed - set(shape_keys)
            if missing:
                cur.execute(
                    "INSERT INTO knowledge_artifacts "
                    "(subject, kind, content, provenance, created_at, file_hash, needs_review, corpus) "
                    "VALUES (?, 'response_mismatch', ?, 'cross_language_linker', ?, NULL, 1, NULL)",
                    (
                        js_fn,
                        json.dumps({
                            "handler": handler,
                            "shape_keys": shape_keys,
                            "consumed_keys": sorted(consumed),
                            "missing_keys": sorted(missing),
                        }),
                        created_at,
                    ),
                )

    # 7. Emit cross_language edges for socket.emit → @socketio.on handler
    for caller, callee, _ in socketio_emit_edges:
        _insert_edge(caller, callee)

    if fetch_edges or socketio_emit_edges:
        conn.commit()
    return count


def _lang_from_path(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "typescript",
        ".tsx": "tsx",
    }.get(ext, "javascript")


def _lookup_response_shape(
    handler: str, response_shapes: dict[str, list[str]]
) -> list[str] | None:
    """Match handler name against response_shape keys (bare or fqdn suffix)."""
    if handler in response_shapes:
        return response_shapes[handler]
    bare = handler.split(".")[-1]
    if bare in response_shapes:
        return response_shapes[bare]
    for key, shape in response_shapes.items():
        if handler.endswith(f".{key}") or key.endswith(f".{handler}"):
            return shape
    return None
