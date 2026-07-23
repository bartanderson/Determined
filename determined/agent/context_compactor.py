# determined/agent/context_compactor.py
#
# Snapcompact-style context compression for long LLM call chains.
# Renders accumulated text context to a pixel-font PNG and passes it to
# Qwen3-VL-8B-Instruct on port 8082 for verbatim read-back.
# NOTE: use the Instruct variant, NOT Thinking — thinking suppression is broken
# in llama.cpp for vision models (issue #20182). Start server with --jinja flag.
#
# Why: prose summarizers destroy facts (SQuAD F1 ~0.00); PNG read-back
# scores 0.88 vs 0.90 for raw text at ~1/3 the token cost.
# (1568x1568 ≈ 3,279 image tokens vs ~10K text tokens for same content)
#
# Public API:
#   compress_context(text, threshold=6000) -> str | None
#   render_to_png(text, width=1568, height=1568) -> bytes
#   is_available() -> bool

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

VISION_BASE_URL    = "http://localhost:8082"
VISION_TIMEOUT     = 180
VISION_MAX_TOKENS  = 8192
COMPRESS_THRESHOLD = 6000   # chars; below this, skip compression

CANVAS_W    = 1568
CANVAS_H    = 1568
FONT_SIZE   = 14
LINE_PAD    = 2
BG_COLOR    = (255, 255, 255)
FG_COLOR    = (0, 0, 0)
MARGIN      = 4


def render_to_png(text: str, width: int = CANVAS_W, height: int = CANVAS_H) -> bytes:
    """Render text as a monochrome pixel-font PNG. Returns raw PNG bytes."""
    img  = Image.new("RGB", (width, height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default(size=FONT_SIZE)
    except TypeError:
        font = ImageFont.load_default()

    try:
        char_w = max(1, round(draw.textlength("M", font=font)))
    except Exception:
        char_w = FONT_SIZE

    line_h        = FONT_SIZE + LINE_PAD
    chars_per_line = max(1, (width - MARGIN * 2) // char_w)
    y             = MARGIN

    for raw_line in text.splitlines():
        if y + line_h > height - MARGIN:
            break
        if not raw_line:
            y += line_h
            continue
        for i in range(0, len(raw_line), chars_per_line):
            if y + line_h > height - MARGIN:
                break
            draw.text((MARGIN, y), raw_line[i:i + chars_per_line], fill=FG_COLOR, font=font)
            y += line_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def is_available(timeout: int = 3) -> bool:
    """True if the Qwen3-VL vision server on port 8082 is reachable."""
    try:
        r = requests.get(f"{VISION_BASE_URL}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def compress_context(text: str, threshold: int = COMPRESS_THRESHOLD) -> Optional[str]:
    """Compress text context via PNG render + vision model read-back.

    Returns the model's transcription, or None if compression is skipped
    (text under threshold, server unavailable, or read-back fails).
    """
    if len(text) < threshold:
        return None
    if not is_available():
        logger.debug("context_compactor: vision server unavailable, skipping")
        return None

    png_bytes = render_to_png(text)
    b64       = base64.b64encode(png_bytes).decode()

    try:
        resp = requests.post(
            f"{VISION_BASE_URL}/v1/chat/completions",
            json={
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "This image contains text in a small monospace font. "
                                "Transcribe all visible text exactly as it appears, "
                                "preserving line breaks and indentation. "
                                "Wrap the transcription in <transcript> and </transcript> tags. "
                                "Example: <transcript>def foo():\n    pass\n</transcript>"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }],
                "max_tokens": VISION_MAX_TOKENS,
                "stream":     False,
            },
            timeout=VISION_TIMEOUT,
        )
        resp.raise_for_status()
        msg     = resp.json()["choices"][0]["message"]
        raw     = msg.get("content", "").strip() or msg.get("reasoning_content", "").strip()
        # Extract content between <transcript>...</transcript> if present
        m = re.search(r"<transcript>(.*?)</transcript>", raw, re.DOTALL)
        if m:
            return m.group(1).strip() or None
        # Fallback: strip <think> blocks and return whatever remains
        clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return clean or None
    except Exception as exc:
        logger.warning("context_compactor.compress_context failed: %s", exc)
        return None
