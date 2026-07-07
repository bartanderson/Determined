"""
Connection inference between entries.

Uses keyword overlap as a proxy for semantic similarity until embeddings are wired.
"""
from __future__ import annotations


def find_connections(entry_id, content, all_entries):
    """
    Given a new entry, find likely connections to existing entries.
    Returns list of (other_entry_id, relation_type, confidence) tuples.
    Uses keyword overlap similarity; entries scoring above 0.15 are returned.
    """
    results = []
    for other in all_entries:
        if other.get("id") == entry_id:
            continue
        score = _similarity_score(content, other.get("content", ""))
        if score >= 0.15:
            results.append((other["id"], "related", round(score, 3)))
    results.sort(key=lambda t: t[2], reverse=True)
    return results[:10]


def _similarity_score(text_a: str, text_b: str) -> float:
    """Keyword overlap similarity: |intersection| / |union| of word sets."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)
