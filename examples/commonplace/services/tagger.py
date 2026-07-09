"""
LLM-powered tag suggestion.

STUB: suggest_tags always returns [] until LLM integration is wired.
Frontier: implement against LLM_ENDPOINT using a structured prompt.

DESIGN TENSION: should this be called eagerly on capture (slow but immediate)
or lazily on first view (fast capture but stale tags)? Open question for Reason.
"""


def suggest_tags(content, endpoint=None):
    """
    Ask LLM to suggest tags for the given content.
    STUB: returns empty list until LLM endpoint is wired.
    """
    return []
