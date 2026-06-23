# tools/analysis/oracle/persist_query_session.py
#
# Persists QuerySessionResult to the query_sessions table.
#
# Follows the same shape as contracts/persist_contract_violations.py:
# a small, dependency-free function that takes a live sqlite3 connection
# and an in-memory result object, and writes one row. Never raises past
# its own boundary in normal operation — callers (QuerySession.run_query)
# treat persistence as best-effort logging, not part of the query
# contract. A query must always succeed and return a result even if the
# DB write fails (disk full, locked file, read-only mount, etc.).

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass


def _to_json(value) -> str:
    if is_dataclass(value):
        value = asdict(value)
    try:
        return json.dumps(value)
    except TypeError:
        return json.dumps(str(value))


def persist_query_session(connection: sqlite3.Connection, result) -> None:
    """
    result: a QuerySessionResult (assessor/query_session.py).
    Duck-typed rather than imported to avoid a persistence -> assessor
    import cycle (assessor already imports persistence-adjacent helpers).
    """
    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO query_sessions (
        session_id,
        raw_query,
        intent,
        queried_at,
        seeds,
        expanded,
        primitives,
        snapshot_edge_count,
        reasoning,
        self_model
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result.session_id,
        result.raw_query,
        result.intent,
        result.queried_at,
        _to_json(result.seeds),
        _to_json(result.expanded),
        _to_json(result.primitives),
        result.snapshot_edge_count,
        _to_json(result.reasoning),
        _to_json(result.self_model),
    ))

    connection.commit()
