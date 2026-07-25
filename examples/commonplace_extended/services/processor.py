"""
Post-processing pipeline for captured entries.

Three concrete processors run in order: cleanup, deduplication, enrichment.
EnrichmentProcessor calls suggest_tags with the LLM endpoint from config;
it is included in the default processor list now that suggest_tags is wired.

DESIGN TENSION: EnrichmentProcessor adds latency to every capture. If LLM
calls are slow, the capture route blocks until tagging completes. An async
queue (celery, rq) would decouple enrichment from the HTTP response cycle.
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
    LLM-powered enrichment: attaches suggested tags to entry.
    Reads LLM_ENDPOINT from Flask config when available.
    Falls back to no-op if endpoint is not configured or call fails.
    """

    def __init__(self, llm_endpoint=None):
        self.llm_endpoint = llm_endpoint

    def process(self, entry: dict) -> dict:
        from services.tagger import suggest_tags
        entry = dict(entry)
        entry["tags"] = suggest_tags(entry.get("content", ""), endpoint=self.llm_endpoint)
        return entry

    def can_handle(self, entry: dict) -> bool:
        return bool(entry.get("content"))


def run_processors(entry: dict, processors=None, llm_endpoint=None) -> dict:
    """
    Run entry through all applicable processors in order.
    Pass llm_endpoint to enable LLM enrichment in EnrichmentProcessor.
    """
    if processors is None:
        processors = [
            CleanupProcessor(),
            DeduplicateProcessor(),
            EnrichmentProcessor(llm_endpoint=llm_endpoint),
        ]
    for proc in processors:
        if proc.can_handle(entry):
            entry = proc.process(entry)
    return entry
