"""
Entry persistence queries.

All SQL for entries lives here. Callers pass the entry dict returned
by extractor.extract() and receive the new row id.
"""
from storage.db import get_db


def insert_entry(entry):
    """
    STUB: Insert an entry dict into the entries table.
    Frontier: implement with db.execute INSERT, db.commit(), return lastrowid.
    Depends on storage.db.init_db() having been called.
    """
    pass


def search_entries(query):
    """
    STUB: Full-text search across entries title and content.
    Frontier: implement with SQL LIKE or FTS5.
    """
    return []
