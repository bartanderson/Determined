def truncate(text, max_chars, suffix="..."):
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix


def clean(text):
    """Collapse whitespace, strip leading/trailing."""
    import re
    return re.sub(r"\s+", " ", text).strip()


def make_excerpt(text, max_chars=200):
    return truncate(clean(text), max_chars)


_embed_model = None


def get_embed_model():
    """Lazy-load all-MiniLM-L6-v2. Returns None if sentence-transformers unavailable."""
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embed_model = False
    return _embed_model if _embed_model else None


def cosine_similarity(a, b):
    """Cosine similarity between two numpy vectors."""
    import numpy as np
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0
