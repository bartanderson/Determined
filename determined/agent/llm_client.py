# determined/agent/llm_client.py
#
# Thin LLM backend shim. All inference calls go through here.
# Backend: llama-server (llama.cpp built-in OpenAI-compatible server).
#
# Both models run on port 8081 (8B on GPU).
# Port 8080 (3B on CPU) is slower — not used.
#
# Public API:
#   generate(prompt)   -> str | None   -- single prompt, text completion
#   chat(messages)     -> str | None   -- message list, chat completion
#   generate_quality() / chat_quality() -- aliases, kept for call-site compatibility

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

LLM_BASE_URL     = "http://localhost:8081"
LLM_TIMEOUT      = 600
LLM_COLD_TIMEOUT = 10
LLM_MAX_TOKENS   = 400

# Legacy alias — same server, kept so existing call sites don't break
LLM_QUALITY_BASE_URL = LLM_BASE_URL
LLM_QUALITY_TIMEOUT  = LLM_TIMEOUT


def _no_think(messages: list[dict]) -> list[dict]:
    """Prepend /no_think to disable Qwen3 chain-of-thought mode."""
    msgs = list(messages)
    if msgs and msgs[0].get("role") == "system":
        msgs[0] = dict(msgs[0], content="/no_think\n" + msgs[0]["content"])
    else:
        msgs.insert(0, {"role": "system", "content": "/no_think"})
    return msgs


def generate(prompt: str, timeout: int = LLM_TIMEOUT, max_tokens: int = LLM_MAX_TOKENS) -> str | None:
    """Single-prompt completion via /v1/completions."""
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/completions",
            json={"prompt": prompt, "stream": False, "max_tokens": max_tokens},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["text"].strip() or None
    except Exception as exc:
        logger.warning("llm_client.generate failed: %s", exc)
        return None


def chat(messages: list[dict], timeout: int = LLM_TIMEOUT, max_tokens: int = LLM_MAX_TOKENS) -> str | None:
    """Chat completion via /v1/chat/completions."""
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={"messages": _no_think(messages), "stream": False, "max_tokens": max_tokens},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()["choices"][0]["message"]
        content = data.get("content", "").strip()
        if not content:
            content = data.get("reasoning_content", "").strip()
        return content or None
    except Exception as exc:
        logger.warning("llm_client.chat failed: %s", exc)
        return None


def is_available(timeout: int = 5) -> bool:
    """Quick health check — True if llama-server is reachable."""
    try:
        resp = requests.get(f"{LLM_BASE_URL}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


# Aliases — generate_quality/chat_quality are identical to generate/chat now.
# Kept so call sites that explicitly request the quality tier still work.
generate_quality  = generate
chat_quality      = chat
is_available_quality = is_available


def warmup(wait_seconds: int = 30, probe_timeout: int = LLM_COLD_TIMEOUT) -> bool:
    """Block until the model is responding, or give up after wait_seconds."""
    deadline = time.monotonic() + wait_seconds
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        remaining = deadline - time.monotonic()
        this_timeout = min(probe_timeout, remaining)
        if this_timeout <= 0:
            break
        result = generate("ping", timeout=int(this_timeout))
        if result is not None:
            logger.info("llm_client.warmup: ready after %d probe(s)", attempt)
            return True
        if time.monotonic() < deadline:
            time.sleep(min(2, deadline - time.monotonic()))
    logger.warning("llm_client.warmup: not ready within %ds", wait_seconds)
    return False
