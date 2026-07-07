"""
Post-processing pipeline for captured entries.

Defines the abstract EntryProcessor interface and two concrete processors.
EnrichmentProcessor is intentionally left as an ABC gap: process() and
can_handle() have no override -- Determined detects this via find_abc_gaps().
"""
from abc import ABC, abstractmethod


class EntryProcessor(ABC):
    """Abstract base for all entry post-processors."""

    @abstractmethod
    def process(self, entry: dict) -> dict:
        """Apply this processor's transformation to an entry. Returns modified entry."""

    @abstractmethod
    def can_handle(self, entry: dict) -> bool:
        """Return True if this processor applies to the given entry."""


class CleanupProcessor(EntryProcessor):
    """Strip trailing whitespace from title and content."""

    def process(self, entry: dict) -> dict:
        entry = dict(entry)
        entry["title"] = (entry.get("title") or "").strip()
        entry["content"] = (entry.get("content") or "").strip()
        return entry

    def can_handle(self, entry: dict) -> bool:
        return True


class DeduplicateProcessor(EntryProcessor):
    """Collapse repeated whitespace in content."""

    def process(self, entry: dict) -> dict:
        import re
        entry = dict(entry)
        entry["content"] = re.sub(r"\s+", " ", entry.get("content") or "")
        return entry

    def can_handle(self, entry: dict) -> bool:
        return bool(entry.get("content"))


class EnrichmentProcessor(EntryProcessor):
    """
    LLM enrichment pass: attaches suggested tags and related entry connections.
    Requires llm_endpoint and all_entries to be set before use.

    STUB: process() and can_handle() are not yet overridden.
    Determined detects this via find_abc_gaps() -- this is the ABC gap the
    guided journey is designed to surface.
    """

    def __init__(self, llm_endpoint=None, all_entries=None):
        self.llm_endpoint = llm_endpoint
        self.all_entries = all_entries or []

    def can_handle(self, entry: dict) -> bool:
        """Only enrich entries that have content and a configured LLM endpoint."""
        return bool(self.llm_endpoint and entry.get("content"))

    def process(self, entry: dict) -> dict:
        """Attach suggested tags and related entry IDs via LLM call (stubbed HTTP)."""
        import urllib.request
        import json
        entry = dict(entry)
        payload = json.dumps({
            "content": entry.get("content", ""),
            "title": entry.get("title", ""),
        }).encode()
        try:
            req = urllib.request.Request(
                self.llm_endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
            entry["tags"] = result.get("tags", [])
            entry["related"] = result.get("related", [])
        except Exception:
            entry.setdefault("tags", [])
            entry.setdefault("related", [])
        return entry


def run_processors(entry: dict, processors=None) -> dict:
    """Run entry through all applicable processors in order."""
    if processors is None:
        processors = [CleanupProcessor(), DeduplicateProcessor()]
    for proc in processors:
        if proc.can_handle(entry):
            entry = proc.process(entry)
    return entry
