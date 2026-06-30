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
import time

import requests

logger = logging.getLogger(__name__)

LLM_BASE_URL     = "http://localhost:8080"
LLM_TIMEOUT      = 30   # GPU inference: complex prompts ~2-5s, 30s is generous safety margin
LLM_COLD_TIMEOUT = 10   # probe timeout for warmup (GPU loads model in <5s)


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


def warmup(wait_seconds: int = 30, probe_timeout: int = LLM_COLD_TIMEOUT) -> bool:
    """
    Block until the model is responding, or give up after wait_seconds.
    GPU cold-load is typically <5s. Returns True if ready, False if timed out.
    """
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
