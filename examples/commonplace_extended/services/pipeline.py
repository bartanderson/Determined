"""
Entry enrichment pipeline: chain-middle topology shape.

enrich_entry() is the chain middle:
  - called by capture route (chain head)
  - calls find_connections() from linker and suggest_tags from tagger (chain tails)

Both calls degrade gracefully: find_connections falls back to Jaccard when no
embedding endpoint; suggest_tags returns [] when no LLM endpoint.
"""
from services.linker import find_connections
from services.tagger import suggest_tags


def enrich_entry(entry: dict, all_entries: list,
                 llm_endpoint: str = None, embedding_endpoint: str = None) -> dict:
    """
    Enrich a captured entry with connections and LLM-suggested tags.
    Chain middle: called from capture route, calls linker and tagger.
    """
    connections = find_connections(
        entry.get("id"), entry.get("content", ""), all_entries,
        embedding_endpoint=embedding_endpoint,
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
