"""
Artifact bag storage layer.

Two kinds of bags:
  "system"   - auto-populated as tools run; acts as session memory
  "user:*"   - manually curated by the user, named/labeled

Items are typed JSON objects (EdgeRef, SymbolRef, FileRef). Dedup is
by item_key so running the same tool twice doesn't double-count.

Storage: two tables added to knowledge.db alongside existing artifact tables.
Scoped by corpus_path so harrow and dj2 bags don't mix.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from determined.agent.edge_types import EdgeRef

SYSTEM_BAG = "system"


class BagStore:
    """
    Manages bag tables in an already-open knowledge.db connection.
    Corpus-scoped so multiple corpora can share one knowledge.db.
    """

    def __init__(self, conn: sqlite3.Connection, corpus_path: str = ""):
        self.conn = conn
        self.corpus_path = corpus_path
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS bags (
                bag_id       TEXT NOT NULL,
                corpus_path  TEXT NOT NULL DEFAULT '',
                label        TEXT,
                created_at   TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (bag_id, corpus_path)
            );
            CREATE TABLE IF NOT EXISTS bag_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                bag_id       TEXT NOT NULL,
                corpus_path  TEXT NOT NULL DEFAULT '',
                item_type    TEXT NOT NULL,
                item_key     TEXT,
                content      TEXT NOT NULL,
                note         TEXT,
                added_at     TEXT DEFAULT (datetime('now'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS bag_items_dedup
                ON bag_items (bag_id, corpus_path, item_key)
                WHERE item_key IS NOT NULL;
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_item(
        self,
        bag_id: str,
        item_type: str,
        content: dict,
        key: str | None = None,
        note: str | None = None,
    ) -> bool:
        """Add an item. Returns True if new, False if duplicate (by key)."""
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO bag_items
                   (bag_id, corpus_path, item_type, item_key, content, note)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (bag_id, self.corpus_path, item_type, key, json.dumps(content), note),
            )
            self.conn.commit()
            return self.conn.execute("SELECT changes()").fetchone()[0] > 0
        except Exception:
            return False

    def add_edge(self, bag_id: str, edge: "EdgeRef") -> bool:
        return self.add_item(bag_id, "edge", edge.to_dict(), key=edge.key())

    def add_symbol(self, bag_id: str, name: str, file_path: str, note: str | None = None) -> bool:
        return self.add_item(bag_id, "symbol",
                             {"name": name, "file_path": file_path},
                             key=f"symbol::{name}", note=note)

    def add_file(self, bag_id: str, file_path: str, note: str | None = None) -> bool:
        return self.add_item(bag_id, "file",
                             {"file_path": file_path},
                             key=f"file::{file_path}", note=note)

    def set_label(self, bag_id: str, label: str) -> None:
        self.conn.execute(
            """INSERT INTO bags (bag_id, corpus_path, label)
               VALUES (?, ?, ?)
               ON CONFLICT(bag_id, corpus_path) DO UPDATE SET label=excluded.label""",
            (bag_id, self.corpus_path, label),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_items(
        self,
        bag_id: str | None = None,
        item_type: str | None = None,
    ) -> list[dict]:
        q = ("SELECT bag_id, item_type, item_key, content, note, added_at "
             "FROM bag_items WHERE corpus_path = ?")
        params: list = [self.corpus_path]
        if bag_id:
            q += " AND bag_id = ?"
            params.append(bag_id)
        if item_type:
            q += " AND item_type = ?"
            params.append(item_type)
        q += " ORDER BY bag_id, item_type, added_at"
        rows = self.conn.execute(q, params).fetchall()
        return [
            {"bag_id": r[0], "item_type": r[1], "key": r[2],
             "content": json.loads(r[3]), "note": r[4], "added_at": r[5]}
            for r in rows
        ]

    def status(self) -> dict[str, dict[str, int]]:
        """Returns {bag_id: {item_type: count}} for this corpus."""
        rows = self.conn.execute(
            """SELECT bag_id, item_type, COUNT(*)
               FROM bag_items WHERE corpus_path = ?
               GROUP BY bag_id, item_type ORDER BY bag_id, item_type""",
            (self.corpus_path,),
        ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for bag_id, itype, count in rows:
            result.setdefault(bag_id, {})[itype] = count
        # Include bags that have labels but no items
        label_rows = self.conn.execute(
            "SELECT bag_id, label FROM bags WHERE corpus_path = ?",
            (self.corpus_path,),
        ).fetchall()
        for bag_id, label in label_rows:
            if bag_id not in result:
                result[bag_id] = {}
        return result

    def bag_labels(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT bag_id, label FROM bags WHERE corpus_path = ? AND label IS NOT NULL",
            (self.corpus_path,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def clear(self, bag_id: str) -> int:
        c = self.conn.execute(
            "DELETE FROM bag_items WHERE bag_id = ? AND corpus_path = ?",
            (bag_id, self.corpus_path),
        )
        self.conn.commit()
        return c.rowcount

    # ------------------------------------------------------------------
    # Auto-accumulate from tool return values
    # ------------------------------------------------------------------

    def auto_add_items(self, items: list) -> int:
        """
        Accept a list of typed objects from a tool return and add them
        to the system bag. Items can be EdgeRef instances or plain dicts
        with a '__type__' key.
        """
        from determined.agent.edge_types import EdgeRef
        added = 0
        for item in items:
            if isinstance(item, EdgeRef):
                if self.add_edge(SYSTEM_BAG, item):
                    added += 1
            elif isinstance(item, dict):
                itype = item.get("__type__", "finding")
                key = item.get("__key__")
                content = {k: v for k, v in item.items()
                           if not k.startswith("__")}
                if self.add_item(SYSTEM_BAG, itype, content, key=key):
                    added += 1
        return added
