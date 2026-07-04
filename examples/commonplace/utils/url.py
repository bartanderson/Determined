"""
URL utilities.

DESIGN TENSION: validate_url is also called inline in capture.py route handler.
Two validation sites for the same constraint -- who owns it?
Determined should flag this when reasoning about the capture boundary.
"""
from urllib.parse import urlparse


def normalize(url):
    """Strip trailing slash, lowercase scheme and host."""
    url = url.strip()
    parsed = urlparse(url)
    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return normalized.geturl().rstrip("/")


def validate_url(url):
    """Return True if url looks like a valid http/https URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
