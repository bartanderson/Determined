"""Regression tests for search_web agent tool (RM12)."""
from __future__ import annotations

import importlib
import types
from unittest.mock import MagicMock, patch

import pytest

from determined.agent.agent_tools import search_web


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assessor():
    a = MagicMock()
    a.oracle.get_project_root.return_value = "C:/fake/root"
    return a


def _mock_response(results: list[dict], status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"results": results}
    return resp


# ---------------------------------------------------------------------------
# Tests: disabled / unreachable
# ---------------------------------------------------------------------------

def test_searxng_not_configured():
    """Returns 'not configured' when SEARXNG_URL is None."""
    import determined.agent.llm_client as cfg
    original = cfg.SEARXNG_URL
    try:
        cfg.SEARXNG_URL = None
        result = search_web(_assessor(), {"query": "python abc"})
        assert "not configured" in result
    finally:
        cfg.SEARXNG_URL = original


def test_missing_query():
    result = search_web(_assessor(), {})
    assert "ERROR" in result


def test_searxng_unreachable():
    """Returns a graceful message when SearXNG is down."""
    import determined.agent.llm_client as cfg
    with patch("requests.get", side_effect=ConnectionError("refused")):
        result = search_web(_assessor(), {"query": "test"})
    assert "unavailable" in result.lower()


# ---------------------------------------------------------------------------
# Tests: successful responses
# ---------------------------------------------------------------------------

_SAMPLE_RESULTS = [
    {
        "title": "Python ABC docs",
        "url": "https://docs.python.org/abc",
        "content": "Abstract base classes in Python allow you to define interfaces.",
    },
    {
        "title": "Real Python guide",
        "url": "https://realpython.com/abc",
        "content": "A hands-on tutorial on Python abstract base classes.",
    },
]


def test_returns_formatted_results():
    with patch("requests.get", return_value=_mock_response(_SAMPLE_RESULTS)):
        result = search_web(_assessor(), {"query": "python abc"})
    assert "WEB SEARCH: python abc" in result
    assert "Python ABC docs" in result
    assert "https://docs.python.org/abc" in result
    assert "Abstract base classes" in result


def test_respects_n_limit():
    results = _SAMPLE_RESULTS * 5  # 10 items
    with patch("requests.get", return_value=_mock_response(results)):
        result = search_web(_assessor(), {"query": "test", "n": 2})
    # count numbered items
    count = sum(1 for line in result.splitlines() if line.startswith("1.") or line.startswith("2.") or line.startswith("3."))
    assert count <= 2


def test_n_capped_at_10():
    results = _SAMPLE_RESULTS * 10  # 20 items
    with patch("requests.get", return_value=_mock_response(results)):
        result = search_web(_assessor(), {"query": "test", "n": 999})
    numbered = [l for l in result.splitlines() if l and l[0].isdigit() and ". " in l[:4]]
    assert len(numbered) <= 10


def test_no_results():
    with patch("requests.get", return_value=_mock_response([])):
        result = search_web(_assessor(), {"query": "xyzzy nonce query"})
    assert "no results" in result.lower()


def test_snippet_truncated_at_200():
    long_snippet = "x" * 500
    results = [{"title": "T", "url": "https://example.com", "content": long_snippet}]
    with patch("requests.get", return_value=_mock_response(results)):
        result = search_web(_assessor(), {"query": "test"})
    # snippet in output must not exceed 200 chars (check the indented line)
    for line in result.splitlines():
        stripped = line.strip()
        if stripped.startswith("x"):
            assert len(stripped) <= 200


def test_result_missing_snippet():
    """Handles results with no content field without crashing."""
    results = [{"title": "No snippet", "url": "https://example.com"}]
    with patch("requests.get", return_value=_mock_response(results)):
        result = search_web(_assessor(), {"query": "test"})
    assert "No snippet" in result


def test_http_error():
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("HTTP 503")
    with patch("requests.get", return_value=resp):
        result = search_web(_assessor(), {"query": "test"})
    assert "unavailable" in result.lower()
