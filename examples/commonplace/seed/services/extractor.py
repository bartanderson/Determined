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
    from urllib import request
    from html.parser import HTMLParser

    class _TitleParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_title = False
            self.title = ""

        def handle_starttag(self, tag, attrs):
            if tag == "title":
                self.in_title = True

        def handle_endtag(self, tag):
            if tag == "title":
                self.in_title = False

        def handle_data(self, data):
            if self.in_title:
                self.title += data

    with request.urlopen(url, timeout=10) as resp:
        raw_html = resp.read().decode("utf-8", errors="replace")

    parser = _TitleParser()
    parser.feed(raw_html)
    return {"title": parser.title.strip(), "description": "", "raw_html": raw_html}


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