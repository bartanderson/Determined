"""
Connection inference between entries.

Uses keyword overlap to find related entries. Entries sharing many non-trivial
keywords score higher. The DESIGN TENSION (infer on write vs. on demand) is
resolved here as on-demand: find_connections is called explicitly, not
triggered automatically.
"""
import re


_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "it", "its", "from", "by",
}


def find_connections(entry_id, content, all_entries):
    """
    Given a new entry, find likely connections to existing entries.
    Returns list of (other_entry_id, relation_type, confidence) tuples.
    Uses keyword overlap; confidence is Jaccard similarity of keyword sets.
    """
    source_keywords = _extract_keywords(content)
    if not source_keywords:
        return []

    results = []
    for other in all_entries:
        other_id = other.get("id") if isinstance(other, dict) else getattr(other, "id", None)
        other_content = other.get("content", "") if isinstance(other, dict) else getattr(other, "content", "")
        if other_id == entry_id or not other_content:
            continue
        score = _similarity_score(content, other_content)
        if score >= 0.1:
            results.append((other_id, "related", round(score, 3)))

    results.sort(key=lambda t: t[2], reverse=True)
    return results[:10]


def _similarity_score(text_a, text_b):
    """
    Compute keyword-overlap (Jaccard) similarity between two texts.
    Returns float in [0.0, 1.0].
    """
    kw_a = _extract_keywords(text_a)
    kw_b = _extract_keywords(text_b)
    if not kw_a or not kw_b:
        return 0.0
    intersection = kw_a & kw_b
    union = kw_a | kw_b
    return len(intersection) / len(union)


def _extract_keywords(text):
    """Return set of lowercase non-stop words (length >= 4) from text."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOP_WORDS}
