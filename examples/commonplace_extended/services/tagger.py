"""
LLM-powered tag suggestion.

Calls llama-server-compatible /completion endpoint. Falls back to [] when the
endpoint is unavailable rather than raising, so capture always succeeds.

DESIGN TENSION (resolved here as lazy): tags are suggested after the entry is
stored, not blocking capture. Eager tagging (block on LLM at capture time) is
an alternative worth revisiting if tag freshness matters more than capture speed.
"""
import json
import urllib.request


def suggest_tags(content, endpoint=None):
    """
    Ask LLM to suggest 3-5 tags for content.
    Returns list of lowercase tag strings. Returns [] on any failure.
    """
    if not endpoint or not content:
        return []
    prompt = (
        "Suggest 3-5 short, specific tags for the following content. "
        "Reply with comma-separated tags only, no explanation, no punctuation.\n\n"
        f"Content: {content[:600]}"
    )
    try:
        raw = _call_llm(prompt, endpoint)
        return _parse_tags(raw)
    except Exception:
        return []


def _call_llm(prompt, endpoint):
    """POST to llama-server /completion. Returns response content string."""
    payload = json.dumps({
        "prompt": prompt,
        "max_tokens": 80,
        "temperature": 0.2,
        "stop": ["\n"],
    }).encode()
    req = urllib.request.Request(
        f"{endpoint}/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    return data.get("content", "")


def _parse_tags(llm_response):
    """Parse comma-separated tags; lowercase, strip whitespace, drop empties."""
    tags = [t.strip().lower() for t in llm_response.split(",")]
    return [t for t in tags if t and len(t) <= 40][:8]
