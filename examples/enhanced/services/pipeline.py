"""
Entry enrichment pipeline: chain-middle topology shape.

enrich_entry() is the chain middle:
  - called by capture route (chain head)
  - calls find_connections() from linker (chain tail stub)

This means enrich_entry is both a callee (from routes) and a caller (to stubs).
Determined should detect it as chain-middle in detect_topology().
"""
from services.linker import find_connections
from services.tagger import suggest_tags


def enrich_entry(entry: dict, all_entries: list, llm_endpoint: str = None) -> dict:
    """
    Enrich a newly captured entry with connections and tags.
    Calls find_connections and suggest_tags.
    Chain middle: called from capture route, calls stub services.
    """
    connections = find_connections(
        entry.get("id"), entry.get("content", ""), all_entries
    )
    tags = suggest_tags(entry.get("content", ""), endpoint=llm_endpoint)
    return dict(entry, connections=connections, suggested_tags=tags)


def _normalize_entry(entry: dict) -> dict:
    """Ensure required fields are present with defaults."""
    return {
        "id": entry.get("id"),
        "title": entry.get("title", ""),
        "content": entry.get("content", ""),
        "source_url": entry.get("source_url", ""),
        "connections": entry.get("connections", []),
        "suggested_tags": entry.get("suggested_tags", []),
    }
