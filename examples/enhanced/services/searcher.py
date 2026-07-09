"""
Search service.

DESIGN TENSION: calls both storage.queries (raw SQL) and models directly.
This bypasses the service layer's own boundary. Determined should flag this
when reasoning about whether search should go through a repository pattern.
"""
from storage import queries
from utils.text import get_embed_model, cosine_similarity


def search(query):
    """Text search across entries. Returns list of row dicts."""
    if not query or not query.strip():
        return []
    rows = queries.search_entries(query.strip())
    return [dict(r) for r in rows]


def semantic_search(query):
    """
    Embedding-based semantic search using all-MiniLM-L6-v2.
    Falls back to text search if sentence-transformers unavailable.
    """
    if not query or not query.strip():
        return []
    model = get_embed_model()
    if not model:
        return search(query)
    all_entries = [dict(r) for r in queries.list_entries(limit=500)]
    if not all_entries:
        return []
    texts = [e.get("content") or e.get("title") or "" for e in all_entries]
    embeddings = model.encode([query] + texts, normalize_embeddings=True)
    query_vec = embeddings[0]
    entry_vecs = embeddings[1:]
    scored = [
        (cosine_similarity(query_vec, entry_vecs[i]), all_entries[i])
        for i in range(len(all_entries))
    ]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [e for score, e in scored if score >= 0.25]
