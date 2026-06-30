# determined/agent/llm_client.py
#
# Thin LLM backend shim. All inference calls go through here.
# Backend: llama-server (llama.cpp built-in OpenAI-compatible server).
# Start: llama-server.exe -m C:\Users\bartl\models\gguf\llama3.2-3b.gguf --port 8080
#
# Two public functions:
#   generate(prompt) -> str | None   -- single prompt, text completion
#   chat(messages)   -> str | None   -- message list, chat completion

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

LLM_BASE_URL = "http://localhost:8080"
LLM_TIMEOUT  = 60


def generate(prompt: str, timeout: int = LLM_TIMEOUT) -> str | None:
    """
    Single-prompt completion via /v1/completions.
    Returns the generated text, or None on any failure.
    """
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/completions",
            json={"prompt": prompt, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["text"].strip() or None
    except Exception as exc:
        logger.warning("llm_client.generate failed: %s", exc)
        return None


def chat(messages: list[dict], timeout: int = LLM_TIMEOUT) -> str | None:
    """
    Chat completion via /v1/chat/completions.
    Returns the assistant content string, or None on any failure.
    """
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={"messages": messages, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip() or None
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


def warmup(wait_seconds: int = 60, probe_timeout: int = 10) -> bool:
    """
    Block until the model is loaded and responding, or give up after
    wait_seconds. Sends a trivial chat request as the probe — /health
    returns ok before the model is ready, so a real inference call is
    the only reliable readiness signal.

    Returns True if the model responded, False if it never did.
    Call this once at the start of any script that will use chat().
    """
    import time
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        result = chat(
            [{"role": "user", "content": "ping"}],
            timeout=probe_timeout,
        )
        if result is not None:
            return True
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(3, remaining))
    return False
