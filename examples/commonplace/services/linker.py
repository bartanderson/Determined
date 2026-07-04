"""
Connection inference between entries.

STUB: find_connections always returns [] until inference is implemented.
Frontier: implement using embedding similarity or keyword overlap.

Open question: infer on write (expensive, always fresh) or on demand
(cheap writes, stale connections)?
"""


def find_connections(entry_id, content, all_entries):
    """
    STUB: Given a new entry, find likely connections to existing entries.
    Returns list of (other_entry_id, relation_type, confidence) tuples.
    """
    return []


def _similarity_score(text_a, text_b):
    """
    STUB: Compute similarity between two texts.
    Placeholder for embedding cosine similarity.
    """
    return 0.0
