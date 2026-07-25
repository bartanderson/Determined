"""
Connection inference between entries using embedding cosine similarity.

The DESIGN TENSION (infer on write vs. on demand) is resolved as on-demand:
find_connections is called explicitly by the capture pipeline, not triggered
by a storage-layer hook.

_similarity_score uses embedding vectors when an endpoint is supplied; falls
back to Jaccard keyword overlap when not. The Jaccard path is retained so the
module works in a no-LLM environment and can be tested without a running server.
"""
import json
import math
import re
import urllib.request


_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "it", "its", "from", "by",
}


def find_connections(entry_id, content, all_entries, embedding_endpoint=None):
    """
    Return up to 10 (other_entry_id, relation_type, confidence) tuples.
    Entries scoring above 0.25 (cosine) or 0.1 (Jaccard fallback) are returned.
    """
    if not content:
        return []
    results = []
    threshold = 0.25 if embedding_endpoint else 0.1
    for other in all_entries:
        other_id = other.get("id") if isinstance(other, dict) else getattr(other, "id", None)
        other_content = other.get("content", "") if isinstance(other, dict) else getattr(other, "content", "")
        if other_id == entry_id or not other_content:
            continue
        score = _similarity_score(content, other_content, embedding_endpoint)
        if score >= threshold:
            results.append((other_id, "related", round(score, 3)))
    results.sort(key=lambda t: t[2], reverse=True)
    return results[:10]


def _similarity_score(text_a, text_b, endpoint=None):
    """
    Cosine similarity via embeddings when endpoint is set; Jaccard keyword
    overlap otherwise. Both return a float in [0, 1].
    """
    if endpoint:
        try:
            vec_a = _embed(text_a[:800], endpoint)
            vec_b = _embed(text_b[:800], endpoint)
            return _cosine(vec_a, vec_b)
        except Exception:
            pass
    return _jaccard(text_a, text_b)


def _embed(text, endpoint):
    payload = json.dumps({"content": text}).encode()
    req = urllib.request.Request(
        f"{endpoint}/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if "embedding" in data:
        return data["embedding"]
    return data["data"][0]["embedding"]


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if not mag_a or not mag_b:
        return 0.0
    return dot / (mag_a * mag_b)


def _jaccard(text_a, text_b):
    kw_a = _keywords(text_a)
    kw_b = _keywords(text_b)
    if not kw_a or not kw_b:
        return 0.0
    return len(kw_a & kw_b) / len(kw_a | kw_b)


def _keywords(text):
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOP_WORDS}
