"""
Post-processing pipeline for captured entries.

Defines the abstract EntryProcessor interface and two concrete processors.
The third processor (EnrichmentProcessor) is intentionally left as a gap:
its ABC method has no override -- Determined should detect this via find_abc_gaps.
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
    STUB: LLM-powered enrichment pass.
    Frontier: call suggest_tags and find_connections, attach results to entry.
    ABC gap: process() and can_handle() not overridden -- Determined detects this.
    """
    pass


def run_processors(entry: dict, processors=None) -> dict:
    """Run entry through all applicable processors in order."""
    if processors is None:
        processors = [CleanupProcessor(), DeduplicateProcessor()]
    for proc in processors:
        if proc.can_handle(entry):
            entry = proc.process(entry)
    return entry
