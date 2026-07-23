"""
Tests for determined/agent/context_compactor.py.

All tests are offline — no live vision server required.
PIL/Pillow must be installed in the venv.
"""

import io
from unittest.mock import patch

import pytest

from determined.agent.context_compactor import (
    CANVAS_H,
    CANVAS_W,
    COMPRESS_THRESHOLD,
    compress_context,
    is_available,
    render_to_png,
)


def test_render_to_png_returns_bytes():
    png = render_to_png("hello world")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_render_to_png_valid_png_header():
    png = render_to_png("hello world")
    # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_to_png_correct_dimensions():
    from PIL import Image

    png = render_to_png("hello world")
    img = Image.open(io.BytesIO(png))
    assert img.size == (CANVAS_W, CANVAS_H)


def test_render_to_png_custom_dimensions():
    from PIL import Image

    png = render_to_png("test", width=400, height=300)
    img = Image.open(io.BytesIO(png))
    assert img.size == (400, 300)


def test_render_to_png_empty_string():
    png = render_to_png("")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_to_png_multiline():
    text = "\n".join(f"line {i}: {'x' * 40}" for i in range(50))
    png = render_to_png(text)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_compress_context_below_threshold_returns_none():
    short_text = "x" * (COMPRESS_THRESHOLD - 1)
    result = compress_context(short_text)
    assert result is None


def test_compress_context_exactly_at_threshold_checks_server():
    # At exactly threshold, the function should proceed past the length check
    # and call is_available(). We mock it to return False to avoid needing a server.
    text = "x" * COMPRESS_THRESHOLD
    with patch("determined.agent.context_compactor.is_available", return_value=False):
        result = compress_context(text)
    assert result is None


def test_compress_context_server_unavailable_returns_none():
    text = "x" * (COMPRESS_THRESHOLD + 100)
    with patch("determined.agent.context_compactor.is_available", return_value=False):
        result = compress_context(text)
    assert result is None


def test_compress_context_extracts_transcript_tag():
    text = "x" * (COMPRESS_THRESHOLD + 100)
    fake_response = {
        "choices": [{
            "message": {
                "content": "<transcript>extracted text here</transcript>",
                "reasoning_content": "",
            }
        }]
    }
    with patch("determined.agent.context_compactor.is_available", return_value=True):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = fake_response
            mock_post.return_value.raise_for_status.return_value = None
            result = compress_context(text)
    assert result == "extracted text here"


def test_compress_context_fallback_strips_think_tags():
    text = "x" * (COMPRESS_THRESHOLD + 100)
    fake_response = {
        "choices": [{
            "message": {
                "content": "<think>internal reasoning</think>\nactual output",
                "reasoning_content": "",
            }
        }]
    }
    with patch("determined.agent.context_compactor.is_available", return_value=True):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = fake_response
            mock_post.return_value.raise_for_status.return_value = None
            result = compress_context(text)
    assert result == "actual output"


def test_compress_context_request_exception_returns_none():
    import requests

    text = "x" * (COMPRESS_THRESHOLD + 100)
    with patch("determined.agent.context_compactor.is_available", return_value=True):
        with patch("requests.post", side_effect=requests.RequestException("timeout")):
            result = compress_context(text)
    assert result is None


def test_is_available_returns_false_when_server_down():
    with patch("requests.get", side_effect=Exception("connection refused")):
        assert is_available() is False


def test_is_available_returns_true_when_server_up():
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert is_available() is True
