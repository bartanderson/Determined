"""
Extracts metadata and content from a URL.

DESIGN TENSION: this module does three distinct things -- fetching, parsing,
and metadata extraction. Determined should flag this when reasoning about
whether extractor should be split into fetcher + parser + metadata.
"""
import urllib.request
from html.parser import HTMLParser
from utils.text import truncate


class _TitleParser(HTMLParser):
    def __init__(self):
        """Initialise parser state for title and description extraction."""
        super().__init__()
        self.title = None
        self.description = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        """Set in-title flag or capture meta description attribute."""
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            attrs = dict(attrs)
            if attrs.get("name") == "description":
                self.description = attrs.get("content", "")

    def handle_endtag(self, tag):
        """Clear in-title flag when the title element closes."""
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        """Capture the first text chunk inside the title element."""
        if self._in_title and not self.title:
            self.title = data.strip()


class _TextExtractor(HTMLParser):
    """Extract visible text, skipping script/style blocks."""

    _SKIP_TAGS = {"script", "style", "head", "noscript"}

    def __init__(self):
        """Initialise the extractor with skip-depth counter and parts list."""
        super().__init__()
        self._skip_depth = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        """Increment skip depth when entering a non-visible tag."""
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        """Decrement skip depth when leaving a non-visible tag."""
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        """Collect visible text chunks, skipping content inside skip-depth."""
        if not self._skip_depth:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self):
        """Return all collected visible text joined by spaces."""
        return " ".join(self._parts)


def extract_metadata(url):
    """Fetch URL and return (title, description, raw_html). Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "Commonplace/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read(65536).decode("utf-8", errors="replace")
    parser = _TitleParser()
    parser.feed(raw)
    return {
        "title": parser.title or url,
        "description": parser.description or "",
        "raw_html": raw,
    }


def extract_full_content(url):
    """Fetch URL and return visible text, stripping script/style/head tags."""
    req = urllib.request.Request(url, headers={"User-Agent": "Commonplace/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read(65536).decode("utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(raw)
    return parser.get_text()


def extract(url):
    """Entry point called by capture route."""
    meta = extract_metadata(url)
    full = extract_full_content(url)
    content = full if full else meta["description"]
    return {
        "title": meta["title"],
        "content": truncate(content, 2000) if content else "",
        "source_url": url,
        "excerpt": truncate(meta["description"], 200),
    }
