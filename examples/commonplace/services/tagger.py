"""
LLM-powered tag suggestion.

STUB: suggest_tags always returns [] until LLM integration is wired.
Frontier: implement against LLM_ENDPOINT using a structured prompt.

DESIGN TENSION: should this be called eagerly on capture (slow but immediate)
or lazily on first view (fast capture but stale tags)? Open question for Reason.
"""
import json
import urllib.request


def suggest_tags(content, endpoint=None):
    """
    STUB: Ask LLM to suggest tags for the given content.
    Returns list of tag strings. Returns [] if LLM unavailable or disabled.
    """
    return []


def _call_llm(prompt, endpoint):
    """Send prompt to llama-server compatible endpoint. Returns response text."""
    payload = json.dumps({
        "prompt": prompt,
        "max_tokens": 100,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        f"{endpoint}/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("content", "")


def _parse_tags(llm_response):
    """Parse comma-separated tags from LLM response text."""
    tags = [t.strip().lower() for t in llm_response.split(",") if t.strip()]
    return tags[:10]
