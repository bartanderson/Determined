# determined/agent/llm_client.py
#
# Thin LLM backend shim. All inference calls go through here.
# Backend: llama-server (llama.cpp built-in OpenAI-compatible server).
#
# Model/port come from the active profile (see _PROFILES; select with env
# DETERMINED_LLM_PROFILE or determined.cfg [llm] profile). Default "analysis":
# Qwen3-VL-8B-Thinking (Q4_K_M) on GPU, port 8081, launched on demand by ui_server.py.
# Text-only use: no mmproj is loaded. /no_think system prefix suppresses chain-of-thought
# for text calls -- do NOT add --jinja to the analysis profile (triggers llama.cpp
# thinking-suppression bug #20182; untested without the mmproj, so left off).
# No always-on service required. start_server() / stop_server() manage the subprocess.
#
# Public API:
#   generate(prompt)   -> str | None   -- single prompt, text completion
#   chat(messages)     -> str | None   -- message list, chat completion
#   generate_quality() / chat_quality() -- aliases, kept for call-site compatibility
#   start_server()     -> bool          -- launch llama-server if not already running
#   stop_server()                       -- terminate the subprocess we launched

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
from pathlib import Path

import requests

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

logger = logging.getLogger(__name__)

LLM_TIMEOUT      = 600
LLM_COLD_TIMEOUT = 10
LLM_MAX_TOKENS   = 1200

# Server launch config — used by start_server() / stop_server()
LLM_SERVER_EXE   = r"C:\Users\bartl\models\llama-server\llama-server.exe"
_VL_SNAPSHOT     = r"C:\hf_cache\hub\models--Qwen--Qwen3-VL-8B-Thinking-GGUF\snapshots\bca5838231f8cc1303cf8810afffcfbdc41bc75a"

# Server profiles. Exactly one is active per process, chosen by
# determined.config.get_llm_profile() (env DETERMINED_LLM_PROFILE > determined.cfg
# [llm] profile > "analysis"). Add a profile here; do not fork this module.
#   analysis -- Determined's own narrow calls (decompose / narrate). Qwen3-VL-8B used as a
#               text model (no mmproj). Do NOT add --jinja: triggers llama.cpp #20182
#               thinking-suppression bug. ctx 32768 = Qwen3-VL native max.
#   agent    -- the model a coding agent (opencode) drives. Text-only MoE with experts on
#               CPU so it fits an 8 GB card alongside a 32k KV cache. Needs --jinja for
#               tool calling. Separate port so it never collides with `analysis`.
# Only one profile's server fits in VRAM at a time on the 8 GB card.
_PROFILES: dict[str, dict] = {
    "analysis": {
        "port": 8081,
        "display_name": "Qwen3-VL-8B",
        "model_path": _VL_SNAPSHOT + r"\Qwen3VL-8B-Thinking-Q4_K_M.gguf",
        "server_args": ["--ctx-size", "32768", "-ngl", "99"],
        "prefix_no_think": True,
        "chat_kwargs": {},
    },
    "agent": {
        "port": 8083,
        "display_name": "Qwen3.6-35B-A3B",
        "model_path": r"C:\Users\bartl\models\gguf\Qwen3.6-35B-A3B-MTP-IMAT-IQ4_XS-Q8nextn.gguf",
        "server_args": [
            "--jinja", "-ngl", "99", "--n-cpu-moe", "99",
            "-c", "32768", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
            "-t", "8", "--alias", "qwen36-35b",
        ],
        "prefix_no_think": False,
        "chat_kwargs": {"chat_template_kwargs": {"enable_thinking": False}},
    },
}


def _resolve_profile() -> tuple[str, dict]:
    from determined.config import get_llm_profile
    name = get_llm_profile()
    if name not in _PROFILES:
        logger.warning("llm_client: unknown profile %r, using 'analysis' (known: %s)",
                       name, ", ".join(sorted(_PROFILES)))
        name = "analysis"
    return name, _PROFILES[name]


LLM_PROFILE, _ACTIVE = _resolve_profile()
LLM_PORT         = _ACTIVE["port"]
LLM_BASE_URL     = f"http://localhost:{LLM_PORT}"
LLM_DISPLAY_NAME = _ACTIVE["display_name"]
LLM_MODEL_PATH   = _ACTIVE["model_path"]
LLM_SERVER_ARGS  = ["--port", str(LLM_PORT), "--host", "127.0.0.1"] + list(_ACTIVE["server_args"])

_server_proc: subprocess.Popen | None = None
_server_lock = threading.Lock()
_server_starting = False

# SearXNG web search config (RM12)
# Set SEARXNG_URL to the base URL of a running SearXNG instance.
# None = web search disabled; search_web tool returns a "not configured" message.
SEARXNG_URL: str | None = "http://localhost:8888"
SEARXNG_TIMEOUT = 10
SEARXNG_MAX_RESULTS = 5

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


def _ensure_server() -> None:
    """Start llama-server if it's not reachable. No-op if already running."""
    if not is_available():
        start_server()


def generate(prompt: str, timeout: int = LLM_TIMEOUT, max_tokens: int = LLM_MAX_TOKENS) -> str | None:
    """Single-prompt completion via /v1/completions."""
    _ensure_server()
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
    _ensure_server()
    try:
        msgs = _no_think(messages) if _ACTIVE["prefix_no_think"] else list(messages)
        resp = requests.post(
            f"{LLM_BASE_URL}/v1/chat/completions",
            json={"messages": msgs, "stream": False, "max_tokens": max_tokens,
                  **_ACTIVE["chat_kwargs"]},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()["choices"][0]["message"]
        content = _THINK_RE.sub("", data.get("content", "")).strip()
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


_PORT_RE = re.compile(r"--port[ =]+(\d+)")


def _parse_port(cmdline: str) -> int | None:
    """Port from a llama-server command line, or None if it has no --port."""
    m = _PORT_RE.search(cmdline or "")
    return int(m.group(1)) if m else None


def _llama_servers() -> list[tuple[int, str]]:
    """(pid, command line) of every running llama-server.exe. Windows only."""
    import platform
    if platform.system() != "Windows":
        return []
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
          "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, timeout=15,
    )
    out = r.stdout.strip()
    if not out:
        return []
    data = json.loads(out)
    if isinstance(data, dict):
        data = [data]
    return [(int(d["ProcessId"]), d.get("CommandLine") or "") for d in data]


def _kill_servers_on_port(port: int, spare_pid: int | None = None) -> None:
    """Kill llama-server.exe processes listening on `port`, except `spare_pid`.

    Only the given port is touched: a server on another port (another profile, or a
    coding agent's model) is never ours to kill. A process whose command line is
    unreadable is left alone."""
    try:
        for pid, cmdline in _llama_servers():
            if pid == spare_pid or _parse_port(cmdline) != port:
                continue
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            logger.info("llm_client: killed llama-server pid %d on port %d", pid, port)
    except Exception as exc:
        logger.warning("llm_client._kill_servers_on_port: %s", exc)


def _kill_orphaned_servers() -> None:
    """Kill llama-server.exe on this profile's port that this session did not start."""
    _kill_servers_on_port(LLM_PORT, spare_pid=_server_proc.pid if _server_proc else None)


def start_server(wait_seconds: int = 90) -> bool:
    """Launch llama-server as a subprocess if not already running.

    Returns True when the server is ready to accept requests.
    Serialized: concurrent callers block until the first launch completes.
    Returns False if the exe is missing or the server fails to start.
    """
    global _server_proc, _server_starting
    if is_available():
        return True
    with _server_lock:
        if is_available():
            return True
        if _server_starting:
            return False  # another thread is mid-launch; don't stack another
        _server_starting = True
    _kill_orphaned_servers()
    try:
        if not Path(LLM_SERVER_EXE).exists():
            logger.warning("llm_client.start_server: exe not found at %s", LLM_SERVER_EXE)
            return False
        if not Path(LLM_MODEL_PATH).exists():
            logger.warning("llm_client.start_server: model not found at %s", LLM_MODEL_PATH)
            return False
        _server_proc = subprocess.Popen(
            [LLM_SERVER_EXE, "-m", LLM_MODEL_PATH] + LLM_SERVER_ARGS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info("llm_client.start_server: launched pid %d", _server_proc.pid)
        return warmup(wait_seconds=wait_seconds)
    finally:
        _server_starting = False


def stop_server(any_owner: bool = False) -> None:
    """Terminate the subprocess started by start_server(). No-op if we didn't launch it.

    any_owner=True also stops a server on this profile's port that another process
    started (used by tools/llm_server.py, which runs in a different process)."""
    global _server_proc
    if _server_proc and _server_proc.poll() is None:
        logger.info("llm_client.stop_server: terminating pid %d", _server_proc.pid)
        _server_proc.terminate()
    elif any_owner:
        _kill_servers_on_port(LLM_PORT)
    _server_proc = None
