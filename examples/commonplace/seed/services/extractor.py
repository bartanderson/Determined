"""
Extracts metadata and content from a URL.

DESIGN TENSION: this module does three distinct things -- fetching, parsing,
and metadata extraction. Whether to split into fetcher + parser + extractor
is an open question. The seam is at extract_full_content().

Determined surfaces this tension via check_design_violations when the
DESIGN.md rules are ingested.
"""


def extract_metadata(url):
    """Fetch URL and return dict with title, description, raw_html."""
    import urllib.request, html.parser

    class _P(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(); self.title = ""; self._in = False
        def handle_starttag(self, t, a):
            if t == "title": self._in = True
        def handle_endtag(self, t):
            if t == "title": self._in = False
        def handle_data(self, d):
            if self._in: self.title += d

    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            raw_html = r.read().decode("utf-8", errors="replace")
        p = _P(); p.feed(raw_html)
        return {"title": p.title.strip(), "description": "", "raw_html": raw_html}
    except Exception:
        return {"title": "", "description": "", "raw_html": ""}


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