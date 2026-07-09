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
