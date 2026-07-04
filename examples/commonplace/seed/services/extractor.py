"""
Extracts metadata and content from a URL.

DESIGN TENSION: this module does three distinct things -- fetching, parsing,
and metadata extraction. Whether to split into fetcher + parser + extractor
is an open question. The seam is at extract_full_content().

Determined surfaces this tension via check_design_violations when the
DESIGN.md rules are ingested.
"""


def extract_metadata(url):
    """
    STUB: Fetch URL and return dict with title, description, raw_html.
    Frontier: implement with urllib.request and an HTML parser.
    """
    return {"title": url, "description": "", "raw_html": ""}


def extract_full_content(url):
    """
    STUB: Extract cleaned readable text from URL.
    Frontier: implement with readability-lxml or trafilatura.
    Depends on extract_metadata() being implemented first.
    """
    return ""


def extract(url):
    """Entry point called by the capture route."""
    meta = extract_metadata(url)
    full = extract_full_content(url)
    content = full if full else meta["description"]
    return {
        "title": meta["title"],
        "content": content,
        "source_url": url,
        "excerpt": content[:200] if content else "",
    }
