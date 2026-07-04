"""
Database connection and schema initialization.

Only this module touches the database directly. No other module
may call get_db() or execute SQL.
"""
import sqlite3
import flask


def get_db():
    """Return the database connection for the current Flask app context."""
    if "db" not in flask.g:
        flask.g.db = sqlite3.connect(
            flask.current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        flask.g.db.row_factory = sqlite3.Row
    return flask.g.db


def init_db():
    """Create tables if they do not exist."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT NOT NULL DEFAULT 'note',
            content    TEXT NOT NULL,
            title      TEXT,
            source_url TEXT,
            excerpt    TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
