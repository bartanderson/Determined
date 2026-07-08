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
    Ask LLM to suggest tags for the given content.
    Returns list of tag strings. Falls back to keyword extraction if LLM unavailable.
    """
    if endpoint:
        try:
            prompt = (
                f"Suggest 3-5 short tags (comma-separated, lowercase) for this content:\n\n"
                f"{content[:500]}\n\nTags:"
            )
            response = _call_llm(prompt, endpoint)
            tags = _parse_tags(response)
            if tags:
                return tags
        except Exception:
            pass
    return _keyword_tags(content)


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


def _keyword_tags(content):
    """Extract top keywords from content as fallback tags when LLM is unavailable."""
    import re
    stop = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "was", "are", "were", "this", "that", "it", "from",
    }
    words = re.findall(r"[a-z]+", content.lower())
    freq = {}
    for w in words:
        if len(w) >= 4 and w not in stop:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq, key=freq.get, reverse=True)
    return top[:5]
