"""
Post-processing pipeline for captured entries.

Defines the abstract EntryProcessor interface and three concrete processors.
EnrichmentProcessor is fully implemented but excluded from run_processors by default:
it calls suggest_tags (a stub) so including it silently produces no tags.
Determined surfaces this asymmetry: class exists, is concrete, but has no callers.
The natural next step is to implement suggest_tags and wire EnrichmentProcessor in.
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
        """Strip leading/trailing whitespace from title and content fields."""
        entry = dict(entry)
        entry["title"] = (entry.get("title") or "").strip()
        entry["content"] = (entry.get("content") or "").strip()
        return entry

    def can_handle(self, entry: dict) -> bool:
        """Always return True - cleanup applies to every entry."""
        return True


class DeduplicateProcessor(EntryProcessor):
    """Collapse repeated whitespace in content."""

    def process(self, entry: dict) -> dict:
        """Collapse all runs of whitespace in content to a single space."""
        import re
        entry = dict(entry)
        entry["content"] = re.sub(r"\s+", " ", entry.get("content") or "")
        return entry

    def can_handle(self, entry: dict) -> bool:
        """Return True if the entry has non-empty content."""
        return bool(entry.get("content"))


class EnrichmentProcessor(EntryProcessor):
    """LLM-powered enrichment pass: attaches suggested tags to entry."""

    def process(self, entry: dict) -> dict:
        """Call suggest_tags on the entry content and attach the resulting tags."""
        from services.tagger import suggest_tags
        entry = dict(entry)
        entry["tags"] = suggest_tags(entry.get("content", ""))
        return entry

    def can_handle(self, entry: dict) -> bool:
        """Return True if the entry has non-empty content."""
        return bool(entry.get("content"))


def run_processors(entry: dict, processors=None) -> dict:
    """Run entry through all applicable processors in order."""
    if processors is None:
        processors = [CleanupProcessor(), DeduplicateProcessor()]
    for proc in processors:
        if proc.can_handle(entry):
            entry = proc.process(entry)
    return entry
