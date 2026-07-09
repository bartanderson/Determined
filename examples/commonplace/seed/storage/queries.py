"""
Entry persistence queries.

All SQL for entries lives here. Callers pass the entry dict returned
by extractor.extract() and receive the new row id.
"""
from storage.db import get_db


def insert_entry(entry):
    """Insert an entry dict into the entries table. Returns new row id."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO entries (type, content, title, source_url, excerpt) VALUES (?, ?, ?, ?, ?)",
        (
            entry.get("type", "note"),
            entry.get("content", ""),
            entry.get("title", ""),
            entry.get("source_url", ""),
            entry.get("excerpt", ""),
        ),
    )
    db.commit()
    return cur.lastrowid


def search_entries(query):
    """Full-text search across entries title and content. Returns list of Row objects."""
    db = get_db()
    pattern = f"%{query}%"
    return db.execute(
        "SELECT * FROM entries WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC",
        (pattern, pattern),
    ).fetchall()
