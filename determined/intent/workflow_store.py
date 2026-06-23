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

VALID_KINDS = {"next_up", "backlog", "future_plan", "session_decision"}
VALID_STATUSES = {"active", "done", "deferred"}


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

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

def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "kind": row[1], "subject": row[2], "content": row[3],
        "rank": row[4], "status": row[5], "provenance": row[6],
        "created_at": row[7], "updated_at": row[8],
    }
