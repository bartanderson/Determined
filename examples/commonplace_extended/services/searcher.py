"""
Search service — text and embedding-based.

DESIGN TENSION: calls storage.queries directly, bypassing any repository layer.
If search logic grows (filters, pagination, sorting by score), it will need
its own boundary. For now, the direct call is the simplest correct thing.

semantic_search uses llama-server /embeddings for cosine ranking. Falls back
to text search when the embedding endpoint is unavailable.
"""
import json
import math
import urllib.request
from storage import queries


def search(query):
    """Text search across entries. Returns list of row dicts."""
    if not query or not query.strip():
        return []
    rows = queries.search_entries(query.strip())
    return [dict(r) for r in rows]


def semantic_search(query, endpoint=None):
    """
    Rank entries by cosine similarity to the query embedding.
    Falls back to text search when the endpoint is unavailable or returns nothing.
    """
    if not query or not query.strip():
        return []
    if not endpoint:
        return search(query)
    try:
        query_vec = _embed(query.strip(), endpoint)
        all_entries = [dict(r) for r in queries.list_entries(limit=500)]
        scored = []
        for entry in all_entries:
            content = (entry.get("content") or "") + " " + (entry.get("title") or "")
            if not content.strip():
                continue
            try:
                entry_vec = _embed(content[:800], endpoint)
                score = _cosine(query_vec, entry_vec)
                if score > 0.3:
                    scored.append((score, entry))
            except Exception:
                continue
        scored.sort(key=lambda t: t[0], reverse=True)
        return [e for _, e in scored[:20]]
    except Exception:
        return search(query)


def _embed(text, endpoint):
    """Request embedding vector from llama-server /embeddings endpoint."""
    payload = json.dumps({"content": text}).encode()
    req = urllib.request.Request(
        f"{endpoint}/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    # llama-server returns {"embedding": [...]} or {"data": [{"embedding": [...]}]}
    if "embedding" in data:
        return data["embedding"]
    return data["data"][0]["embedding"]


def _cosine(a, b):
    """Cosine similarity between two equal-length float vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if not mag_a or not mag_b:
        return 0.0
    return dot / (mag_a * mag_b)
