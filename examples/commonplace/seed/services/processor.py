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
    """

    def __init__(self, llm_endpoint=None, all_entries=None):
        self.llm_endpoint = llm_endpoint
        self.all_entries = all_entries or []

    def can_handle(self, entry: dict) -> bool:
        return bool(entry.get("content"))

    def process(self, entry: dict) -> dict:
        from services import tagger, linker
        entry = dict(entry)
        entry["tags"] = tagger.suggest_tags(entry["content"], self.llm_endpoint)
        entry["connections"] = linker.find_connections(
            entry.get("id"), entry["content"], self.all_entries
        )
        return entry


def run_processors(entry: dict, processors=None) -> dict:
    """Run entry through all applicable processors in order."""
    if processors is None:
        processors = [CleanupProcessor(), DeduplicateProcessor()]
    for proc in processors:
        if proc.can_handle(entry):
            entry = proc.process(entry)
    return entry
