"""
Search service.
"""
from storage import queries


def search(query):
    """Text search across entries. Returns list of row dicts."""
    if not query or not query.strip():
        return []
    rows = queries.search_entries(query.strip())
    return [dict(r) for r in rows]


def semantic_search(query):
    """
    Semantic search over entries. Currently delegates to text search.
    Replace with embedding-based ranking when embeddings are available.
    """
    return search(query)
