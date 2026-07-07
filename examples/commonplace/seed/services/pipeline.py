"""
Entry enrichment pipeline: chain-middle topology shape.

enrich_entry() is the chain middle:
  - called by capture route (chain head)
  - calls find_connections() and suggest_tags() (chain tail stubs)

Determined should detect enrich_entry as chain-middle in detect_topology().
"""
from services.linker import find_connections
from services.tagger import suggest_tags


def enrich_entry(entry: dict, all_entries: list) -> dict:
    """
    STUB: Enrich a newly captured entry with connections and tags.
    Calls find_connections and suggest_tags -- both stubs.
    Chain middle: called from capture route, calls stub services.
    """
    connections = find_connections(
        entry.get("id"), entry.get("content", ""), all_entries
    )
    tags = suggest_tags(entry.get("content", ""))
    return dict(entry, connections=connections, suggested_tags=tags)
