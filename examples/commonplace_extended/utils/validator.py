"""
Input validation utilities.

validate_entry() contains a conditional stub:
  raise NotImplementedError is inside an if-branch (strict mode).
Determined should detect this via find_conditional_stubs().
"""
import urllib.parse


def validate_url(url: str) -> bool:
    """Return True if url has a valid http/https scheme and netloc."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_entry(entry: dict, strict: bool = False) -> list:
    """
    Validate a captured entry dict.
    Returns a list of error strings (empty = valid).

    In strict mode, content validation is not yet implemented.
    """
    errors = []
    if not entry.get("title"):
        errors.append("title is required")
    if not entry.get("source_url"):
        errors.append("source_url is required")
    elif not validate_url(entry["source_url"]):
        errors.append("source_url is not a valid http/https URL")

    if strict:
        raise NotImplementedError("strict content validation not yet implemented")

    return errors
