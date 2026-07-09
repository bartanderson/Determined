"""
Search service.

DESIGN TENSION: calls both storage.queries (raw SQL) and models directly.
This bypasses the service layer's own boundary. Determined should flag this
when reasoning about whether search should go through a repository pattern.
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
    Semantic search stub -- delegates to text search until embeddings are wired.
    Frontier: implement with sentence-transformers (all-MiniLM-L6-v2).
    """
    return search(query)
