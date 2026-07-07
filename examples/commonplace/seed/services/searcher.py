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
    STUB: Embedding-based semantic search.
    Falls back to text search until embeddings are available.
    Frontier: implement with sentence-transformers or llama-server embeddings.
    """
    return search(query)
