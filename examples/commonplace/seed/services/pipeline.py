"""
Entry enrichment pipeline.

enrich_entry() wires tagger and linker services together for post-capture enrichment.
"""
from services.linker import find_connections
from services.tagger import suggest_tags


def enrich_entry(entry: dict, all_entries: list) -> dict:
    """Enrich a captured entry with suggested tags and related-entry connections."""
    connections = find_connections(
        entry.get("id"), entry.get("content", ""), all_entries
    )
    tags = suggest_tags(entry.get("content", ""))
    return dict(entry, connections=connections, suggested_tags=tags)
