from storage.db import get_db


def insert_entry(type, content, title, source_url, excerpt):
    db = get_db()
    cur = db.execute(
        "INSERT INTO entries (type, content, title, source_url, excerpt) VALUES (?,?,?,?,?)",
        (type, content, title, source_url, excerpt),
    )
    db.commit()
    return cur.lastrowid


def get_entry(entry_id):
    return get_db().execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()


def list_entries(limit=50, offset=0):
    return get_db().execute(
        "SELECT * FROM entries ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()


def search_entries(query):
    # DESIGN TENSION: searcher.py also calls this directly, bypassing
    # the service layer boundary. Who should own search logic?
    like = f"%{query}%"
    return get_db().execute(
        "SELECT * FROM entries WHERE content LIKE ? OR title LIKE ? ORDER BY created_at DESC",
        (like, like),
    ).fetchall()


def get_entry_tags(entry_id):
    return get_db().execute(
        "SELECT t.name, t.source FROM tags t JOIN entry_tags et ON t.id = et.tag_id WHERE et.entry_id = ?",
        (entry_id,),
    ).fetchall()


def insert_tag(name, source="manual"):
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO tags (name, source) VALUES (?,?)", (name, source)
    )
    db.commit()
    row = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    return row["id"]


def link_tag(entry_id, tag_id):
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?,?)",
        (entry_id, tag_id),
    )
    db.commit()


def insert_connection(from_id, to_id, relation, note=None):
    db = get_db()
    db.execute(
        "INSERT INTO connections (from_entry_id, to_entry_id, relation, note) VALUES (?,?,?,?)",
        (from_id, to_id, relation, note),
    )
    db.commit()


def get_connections(entry_id):
    return get_db().execute(
        "SELECT * FROM connections WHERE from_entry_id = ? OR to_entry_id = ?",
        (entry_id, entry_id),
    ).fetchall()
