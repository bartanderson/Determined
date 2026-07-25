import sqlite3
from flask import g


def get_db(app=None):
    if app:
        return sqlite3.connect(app.config["DATABASE"])
    from flask import current_app
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db(app)
        db.executescript(SCHEMA)
        db.commit()


SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,
    content     TEXT NOT NULL,
    title       TEXT,
    source_url  TEXT,
    excerpt     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    source  TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id    INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    tag_id      INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE TABLE IF NOT EXISTS connections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entry_id   INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    to_entry_id     INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    relation        TEXT NOT NULL,
    note            TEXT
);
"""
