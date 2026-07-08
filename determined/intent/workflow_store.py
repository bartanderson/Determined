# tools/analysis/intent/workflow_store.py
#
# Mutable ranked workflow state stored in knowledge.db alongside
# knowledge_artifacts. Separate table because workflow items have
# different semantics: they change status, get reranked, and are
# intentionally short-lived compared to durable findings.
#
# Kinds: next_up | backlog | future_plan | session_decision
# Status: active | done | deferred

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

VALID_KINDS = {"next_up", "backlog", "future_plan", "session_decision", "artifact"}
VALID_STATUSES = {"active", "done", "deferred"}
VALID_ARTIFACT_STATUSES = {"fresh", "stale", "superseded"}


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

def ensure_artifact_columns(cursor: sqlite3.Cursor) -> None:
    """
    Idempotent migration: add artifact-related columns to workflow_items
    and ingested_at to files (same corpus DB).
    """
    wi_cols = {row[1] for row in cursor.execute("PRAGMA table_info(workflow_items)").fetchall()}
    if "tool_name" not in wi_cols:
        cursor.execute("ALTER TABLE workflow_items ADD COLUMN tool_name TEXT")
    if "artifact_status" not in wi_cols:
        cursor.execute("ALTER TABLE workflow_items ADD COLUMN artifact_status TEXT DEFAULT 'fresh'")
    if "feeds_into" not in wi_cols:
        cursor.execute("ALTER TABLE workflow_items ADD COLUMN feeds_into TEXT")

    f_cols = {row[1] for row in cursor.execute("PRAGMA table_info(files)").fetchall()}
    if "ingested_at" not in f_cols:
        cursor.execute("ALTER TABLE files ADD COLUMN ingested_at TEXT")


def ensure_workflow_items_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workflow_items (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        kind     TEXT NOT NULL,
        subject  TEXT NOT NULL,
        content  TEXT NOT NULL,
        rank     INTEGER,
        status   TEXT NOT NULL DEFAULT 'active',
        provenance TEXT NOT NULL DEFAULT 'human',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wi_kind_status "
        "ON workflow_items(kind, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wi_rank "
        "ON workflow_items(rank)"
    )


# ------------------------------------------------------------------
# Write API
# ------------------------------------------------------------------

def add_item(
    conn: sqlite3.Connection,
    kind: str,
    subject: str,
    content: str,
    rank: Optional[int] = None,
    provenance: str = "human",
) -> int:
    """Add a workflow item. Returns new row id."""
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO workflow_items (kind, subject, content, rank, status, provenance, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'active', ?, ?, ?)",
        (kind, subject, content, rank, provenance, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_item(
    conn: sqlite3.Connection,
    item_id: int,
    *,
    status: Optional[str] = None,
    rank: Optional[int] = None,
    content: Optional[str] = None,
) -> bool:
    """Update status, rank, or content of an item. Returns True if found."""
    if status and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    sets, params = [], []
    if status is not None:
        sets.append("status = ?"); params.append(status)
    if rank is not None:
        sets.append("rank = ?"); params.append(rank)
    if content is not None:
        sets.append("content = ?"); params.append(content)
    if not sets:
        return False
    now = datetime.now(timezone.utc).isoformat()
    sets.append("updated_at = ?"); params.append(now)
    params.append(item_id)
    conn.execute(f"UPDATE workflow_items SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return conn.execute("SELECT changes()").fetchone()[0] > 0


def rerank_items(conn: sqlite3.Connection, ordered_ids: list[int]) -> int:
    """
    Assign sequential ranks (1, 2, 3...) to items in the given id order.
    Items not in the list keep their existing rank.
    Returns count of items updated.
    """
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for rank, item_id in enumerate(ordered_ids, start=1):
        conn.execute(
            "UPDATE workflow_items SET rank = ?, updated_at = ? WHERE id = ?",
            (rank, now, item_id),
        )
        count += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    return count


def mark_done(conn: sqlite3.Connection, item_id: int) -> bool:
    """Shorthand for update_item(status='done')."""
    return update_item(conn, item_id, status="done")


# ------------------------------------------------------------------
# Read API
# ------------------------------------------------------------------

def list_items(
    conn: sqlite3.Connection,
    *,
    kind: Optional[str] = None,
    status: str = "active",
    limit: int = 20,
) -> list[dict]:
    """
    List workflow items. Default: active items only.
    Sorted: ranked items first (by rank asc), then unranked by created_at desc.
    """
    clauses, params = [], []
    if kind:
        clauses.append("kind = ?"); params.append(kind)
    if status != "all":
        clauses.append("status = ?"); params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT id, kind, subject, content, rank, status, provenance, created_at, updated_at "
        f"FROM workflow_items {where} "
        f"ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END, rank ASC, created_at DESC "
        f"LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_item(conn: sqlite3.Connection, item_id: int) -> Optional[dict]:
    """Fetch a single item by id."""
    row = conn.execute(
        "SELECT id, kind, subject, content, rank, status, provenance, created_at, updated_at "
        "FROM workflow_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def store_artifact(
    conn: sqlite3.Connection,
    name: str,
    tool_name: str,
    content: str,
    feeds_into: Optional[list] = None,
) -> int:
    """
    Store a named tool artifact. Supersedes any prior artifact with the same name.
    Returns the new row id.
    """
    import json as _json
    now = datetime.now(timezone.utc).isoformat()
    # Supersede any existing fresh/stale artifact with the same name
    conn.execute(
        "UPDATE workflow_items SET artifact_status='superseded', updated_at=? "
        "WHERE kind='artifact' AND subject=? AND artifact_status IN ('fresh','stale')",
        (now, name),
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO workflow_items "
        "(kind, subject, content, rank, status, provenance, created_at, updated_at, "
        "tool_name, artifact_status, feeds_into) "
        "VALUES ('artifact', ?, ?, NULL, 'active', 'tool', ?, ?, ?, 'fresh', ?)",
        (name, content, now, now, tool_name, _json.dumps(feeds_into or [])),
    )
    conn.commit()
    return cursor.lastrowid


def get_artifact_by_name(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    """Return the most recent non-superseded artifact with the given name."""
    row = conn.execute(
        "SELECT id, subject, content, tool_name, artifact_status, feeds_into, created_at, updated_at "
        "FROM workflow_items "
        "WHERE kind='artifact' AND subject=? AND artifact_status != 'superseded' "
        "ORDER BY created_at DESC LIMIT 1",
        (name,),
    ).fetchone()
    return _artifact_row_to_dict(row) if row else None


def list_artifacts(
    conn: sqlite3.Connection,
    artifact_status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """List artifacts, optionally filtered by artifact_status."""
    if artifact_status:
        rows = conn.execute(
            "SELECT id, subject, content, tool_name, artifact_status, feeds_into, created_at, updated_at "
            "FROM workflow_items WHERE kind='artifact' AND artifact_status=? "
            "ORDER BY created_at DESC LIMIT ?",
            (artifact_status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, subject, content, tool_name, artifact_status, feeds_into, created_at, updated_at "
            "FROM workflow_items WHERE kind='artifact' AND artifact_status != 'superseded' "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_artifact_row_to_dict(r) for r in rows]


def mark_stale_by_files(
    conn: sqlite3.Connection,
    file_paths: Optional[list] = None,
) -> int:
    """
    Mark fresh artifacts stale when any relevant file was reingested after the artifact
    was created. file_paths=None checks all files.

    Returns count of artifacts newly marked stale (including cascade).
    """
    import json as _json

    if file_paths:
        placeholders = ",".join("?" * len(file_paths))
        row = conn.execute(
            f"SELECT MAX(ingested_at) FROM files WHERE file_path IN ({placeholders}) "
            f"AND ingested_at IS NOT NULL",
            file_paths,
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(ingested_at) FROM files WHERE ingested_at IS NOT NULL"
        ).fetchone()

    max_ingested = row[0] if row else None
    if not max_ingested:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE workflow_items SET artifact_status='stale', updated_at=? "
        "WHERE kind='artifact' AND artifact_status='fresh' AND created_at < ?",
        (now, max_ingested),
    )
    count = conn.execute("SELECT changes()").fetchone()[0]
    count += _cascade_staleness(conn, now)
    conn.commit()
    return count


def _cascade_staleness(conn: sqlite3.Connection, now: str) -> int:
    """
    Transitively mark fresh artifacts stale when their feeds_into list
    references an artifact that is already stale.
    Returns total count of additionally stale artifacts.
    """
    import json as _json
    total = 0
    while True:
        stale_names = {
            row[0] for row in conn.execute(
                "SELECT subject FROM workflow_items WHERE kind='artifact' AND artifact_status='stale'"
            ).fetchall()
        }
        if not stale_names:
            break
        fresh = conn.execute(
            "SELECT id, subject, feeds_into FROM workflow_items "
            "WHERE kind='artifact' AND artifact_status='fresh' AND feeds_into IS NOT NULL"
        ).fetchall()
        to_stale = []
        for row_id, subject, feeds_into_json in fresh:
            try:
                deps = _json.loads(feeds_into_json or "[]")
            except Exception:
                deps = []
            if any(dep in stale_names for dep in deps):
                to_stale.append(row_id)
        if not to_stale:
            break
        placeholders = ",".join("?" * len(to_stale))
        conn.execute(
            f"UPDATE workflow_items SET artifact_status='stale', updated_at=? "
            f"WHERE id IN ({placeholders})",
            [now] + to_stale,
        )
        total += len(to_stale)
    return total


def format_workflow_status(conn: sqlite3.Connection) -> str:
    """
    Return a human-readable summary of current workflow state:
    next_up items, then top backlog, then any session_decisions.
    """
    lines = []

    next_up = list_items(conn, kind="next_up", status="active")
    if next_up:
        lines.append("NOW (next_up):")
        for item in next_up:
            rank_str = f"[#{item['rank']}] " if item["rank"] else ""
            lines.append(f"  {rank_str}{item['id']}. {item['subject']}: {item['content']}")

    backlog = list_items(conn, kind="backlog", status="active", limit=10)
    if backlog:
        lines.append("BACKLOG:")
        for item in backlog:
            rank_str = f"[#{item['rank']}] " if item["rank"] else ""
            lines.append(f"  {rank_str}{item['id']}. {item['subject']}: {item['content']}")

    future = list_items(conn, kind="future_plan", status="active", limit=5)
    if future:
        lines.append("FUTURE:")
        for item in future:
            lines.append(f"  {item['id']}. {item['subject']}: {item['content']}")

    decisions = list_items(conn, kind="session_decision", status="active", limit=3)
    if decisions:
        lines.append("RECENT DECISIONS:")
        for item in decisions:
            lines.append(f"  {item['id']}. {item['subject']}: {item['content']}")

    return "\n".join(lines) if lines else "No active workflow items."


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------

def _artifact_row_to_dict(row) -> dict:
    import json as _json
    return {
        "id": row[0], "name": row[1], "content": row[2],
        "tool_name": row[3], "artifact_status": row[4],
        "feeds_into": _json.loads(row[5] or "[]"),
        "created_at": row[6], "updated_at": row[7],
    }


def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "kind": row[1], "subject": row[2], "content": row[3],
        "rank": row[4], "status": row[5], "provenance": row[6],
        "created_at": row[7], "updated_at": row[8],
    }
