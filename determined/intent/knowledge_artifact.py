# tools/analysis/intent/knowledge_artifact.py
#
# Sub-layer B of the Intent Layer (DESIGN.md section 3).
#
# Durable, explicitly-stored findings, strategy decisions, and confirmed
# facts produced during sessions. These answer questions the structural
# layer cannot answer at all ("what is this for", "what did we decide").
#
# Storage is deliberate: artifacts are only written via an explicit
# "keep this" call, never auto-captured after every query.
#
# Provenance is load-bearing: human-confirmed outranks ai-generated.
# The query layer surfaces the provenance label so callers can decide
# how much weight to give a finding.

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

VALID_KINDS = {
    "file_purpose",
    "strategy_decision",
    "query_finding",
    "design_note",
    "known_issue",
    # structural facts written by extract_design_facts
    "entry",
    "dead",
    "hot",
    "stub",
}

VALID_PROVENANCES = {
    "human-confirmed",
    "ai-confirmed-by-human",
    "ai-generated",
}

_PROVENANCE_RANK = {
    "human-confirmed": 3,
    "ai-confirmed-by-human": 2,
    "ai-generated": 1,
}


# ------------------------------------------------------------------
# Schema helpers (called from persistence_engine.ensure_schema)
# ------------------------------------------------------------------

def ensure_knowledge_artifacts_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        provenance TEXT NOT NULL,
        created_at TEXT NOT NULL,
        file_hash TEXT,
        needs_review INTEGER NOT NULL DEFAULT 0,
        corpus TEXT
    )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ka_subject "
        "ON knowledge_artifacts(subject)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ka_kind "
        "ON knowledge_artifacts(kind)"
    )
    # Migrate existing DBs: add columns if absent (idempotent)
    # Must run before any index that references these columns.
    for col, definition in [
        ("file_hash", "TEXT"),
        ("needs_review", "INTEGER NOT NULL DEFAULT 0"),
        ("corpus", "TEXT"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE knowledge_artifacts ADD COLUMN {col} {definition}")
        except Exception:
            pass  # column already exists
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ka_corpus "
        "ON knowledge_artifacts(corpus)"
    )


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def add_artifact(
    connection: sqlite3.Connection,
    subject: str,
    kind: str,
    content: str,
    provenance: str = "ai-generated",
    file_hash: Optional[str] = None,
    corpus: Optional[str] = None,
) -> int:
    """
    Store a knowledge artifact. Returns the new row id.

    subject    - file path, symbol, subsystem label, or free-form topic.
    kind       - one of VALID_KINDS.
    content    - the finding or decision text.
    provenance - one of VALID_PROVENANCES; defaults to 'ai-generated'.
    file_hash  - SHA-256 of the subject file at creation time (optional).
    corpus     - basename of the corpus DB this artifact belongs to (optional).
                 When set, queries scoped to this corpus will filter by it.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")
    if provenance not in VALID_PROVENANCES:
        raise ValueError(f"provenance must be one of {VALID_PROVENANCES}, got {provenance!r}")

    created_at = datetime.now(timezone.utc).isoformat()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO knowledge_artifacts
            (subject, kind, content, provenance, created_at, file_hash, needs_review, corpus)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (subject, kind, content, provenance, created_at, file_hash, corpus),
    )
    connection.commit()
    return cursor.lastrowid


def flag_stale_artifacts(
    connection: sqlite3.Connection,
    file_path: str,
    current_hash: str,
) -> int:
    """
    Called by the ingestion pipeline after re-ingesting a file. Sets
    needs_review=1 on any artifact whose subject contains file_path and
    whose stored file_hash differs from current_hash. Returns count flagged.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE knowledge_artifacts
        SET needs_review = 1
        WHERE subject LIKE ?
          AND file_hash IS NOT NULL
          AND file_hash != ?
          AND needs_review = 0
        """,
        (f"%{file_path}%", current_hash),
    )
    connection.commit()
    return cursor.rowcount


def get_artifacts(
    connection: sqlite3.Connection,
    subject: str,
    *,
    kind: Optional[str] = None,
    corpus: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve all artifacts for `subject`, sorted by provenance rank
    (highest first) then recency. Optionally filter by kind and/or corpus.
    When corpus is set, returns artifacts for that corpus OR unscoped (NULL) artifacts.
    """
    cursor = connection.cursor()
    clauses = ["subject = ?"]
    params: list = [subject]
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if corpus:
        clauses.append("(corpus = ? OR corpus IS NULL)")
        params.append(corpus)
    where = "WHERE " + " AND ".join(clauses)
    cursor.execute(
        f"SELECT id, subject, kind, content, provenance, created_at, file_hash, needs_review "
        f"FROM knowledge_artifacts {where} ORDER BY created_at DESC",
        params,
    )
    rows = cursor.fetchall()
    results = [_row_to_dict(r) for r in rows]
    results.sort(key=lambda r: _PROVENANCE_RANK.get(r["provenance"], 0), reverse=True)
    return results


def list_artifacts(
    connection: sqlite3.Connection,
    *,
    kind: Optional[str] = None,
    provenance: Optional[str] = None,
    corpus: Optional[str] = None,
) -> list[dict]:
    """
    List all stored artifacts, optionally filtered by kind, provenance, and/or corpus.
    When corpus is set, returns artifacts for that corpus OR unscoped (NULL) artifacts.
    Sorted by provenance rank desc, then created_at desc.
    """
    cursor = connection.cursor()
    clauses = []
    params: list = []
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if provenance:
        clauses.append("provenance = ?")
        params.append(provenance)
    if corpus:
        clauses.append("(corpus = ? OR corpus IS NULL)")
        params.append(corpus)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    cursor.execute(
        f"SELECT id, subject, kind, content, provenance, created_at, file_hash, needs_review "
        f"FROM knowledge_artifacts {where} ORDER BY created_at DESC",
        params,
    )
    rows = cursor.fetchall()
    results = [_row_to_dict(r) for r in rows]
    results.sort(key=lambda r: _PROVENANCE_RANK.get(r["provenance"], 0), reverse=True)
    return results


def delete_artifact(connection: sqlite3.Connection, artifact_id: int) -> bool:
    """Delete a single artifact by id. Returns True if a row was removed."""
    cursor = connection.cursor()
    cursor.execute("DELETE FROM knowledge_artifacts WHERE id = ?", (artifact_id,))
    connection.commit()
    return cursor.rowcount > 0


def highest_provenance(artifacts: list[dict]) -> Optional[dict]:
    """
    Given a list of artifact dicts (as returned by get_artifacts),
    return the one with the highest provenance rank, or None if empty.
    When provenance is tied, the most recently created artifact wins.
    """
    if not artifacts:
        return None
    return max(
        artifacts,
        key=lambda r: (_PROVENANCE_RANK.get(r["provenance"], 0), r["created_at"]),
    )


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "subject": row[1],
        "kind": row[2],
        "content": row[3],
        "provenance": row[4],
        "created_at": row[5],
        "file_hash": row[6] if len(row) > 6 else None,
        "needs_review": bool(row[7]) if len(row) > 7 else False,
    }
