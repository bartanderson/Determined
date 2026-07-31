"""
decisions_ledger.py — Load <target>/.determined/decisions.toml into knowledge_artifacts.

The file is the source of truth; the DB is always a derived view.
Re-loading is idempotent: existing rows with provenance='human-confirmed' and
kind in ('decision', 'name_resolution') are deleted and re-inserted on every call
so that edits to the toml file are reflected after a corpus reload.

Called from ui_server.init() so decisions survive corpus rebuilds.
"""

from __future__ import annotations

import json
import sqlite3
import tomllib
from pathlib import Path
from typing import Optional


_LEDGER_KINDS = ("decision", "name_resolution")


def load_decisions(source_path: Optional[str], conn: sqlite3.Connection) -> dict:
    """
    Read <source_path>/.determined/decisions.toml and materialize rows into
    knowledge_artifacts.  Returns {"decisions": N, "name_resolutions": N}.
    No-ops gracefully if the file does not exist.
    """
    if not source_path:
        return {"decisions": 0, "name_resolutions": 0}

    ledger_path = Path(source_path) / ".determined" / "decisions.toml"
    if not ledger_path.exists():
        return {"decisions": 0, "name_resolutions": 0}

    with open(ledger_path, "rb") as f:
        data = tomllib.load(f)

    cur = conn.cursor()
    # Clear prior materialized rows so edits to the file are reflected.
    cur.execute(
        "DELETE FROM knowledge_artifacts WHERE kind IN ('decision','name_resolution')"
        " AND provenance='human-confirmed'"
    )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    decision_count = 0
    for item in data.get("decisions", []):
        subject = (item.get("subject") or "")[:200]
        content = item.get("content") or ""
        if not subject or not content:
            continue
        tags = item.get("tags", [])
        if tags:
            content = content.rstrip() + f"\n[tags: {', '.join(tags)}]"
        cur.execute(
            "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at)"
            " VALUES (?, 'decision', ?, 'human-confirmed', ?)",
            (subject, content, now),
        )
        decision_count += 1

    name_res_count = 0
    for item in data.get("name_resolutions", []):
        original = (item.get("original") or "").strip()
        canonical = (item.get("canonical") or "").strip()
        if not original or not canonical:
            continue
        scope = item.get("scope", "symbol")
        confidence = item.get("confidence", "medium")
        evidence = item.get("evidence", [])
        parent = item.get("parent", "")
        payload = json.dumps({
            "original": original,
            "canonical": canonical,
            "scope": scope,
            "confidence": confidence,
            "evidence": evidence,
            "parent": parent,
        })
        # subject encodes the original name for fast lookup by graph layer
        subject = f"name::{original}"
        if parent:
            subject = f"name::{original}::{parent}"
        cur.execute(
            "INSERT INTO knowledge_artifacts (subject, kind, content, provenance, created_at)"
            " VALUES (?, 'name_resolution', ?, 'human-confirmed', ?)",
            (subject, payload, now),
        )
        name_res_count += 1

    conn.commit()
    return {"decisions": decision_count, "name_resolutions": name_res_count}


def lookup_canonical(conn: sqlite3.Connection, original: str, parent: str = "") -> Optional[str]:
    """
    Return the committed canonical name for `original`, or None if no resolution exists.
    Checks parent-scoped resolution first, then unscoped symbol resolution.
    Used by wiring_chain fuzzy expansion and analyst narration.
    """
    candidates = []
    if parent:
        candidates.append(f"name::{original}::{parent}")
    candidates.append(f"name::{original}")
    for subject in candidates:
        row = conn.execute(
            "SELECT content FROM knowledge_artifacts WHERE subject=? AND kind='name_resolution' LIMIT 1",
            (subject,),
        ).fetchone()
        if row:
            try:
                payload = json.loads(row[0])
                return payload.get("canonical")
            except Exception:
                pass
    return None
