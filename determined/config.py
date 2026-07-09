# determined/config.py
#
# Central config loader. Priority: env var > determined.cfg > default.
# Config file is searched at:
#   1. ~/.determined/determined.cfg
#   2. <repo-root>/determined.cfg  (sibling of this file's parent)

from __future__ import annotations

import configparser
import os
from pathlib import Path

_CFG_PATHS = [
    Path.home() / ".determined" / "determined.cfg",
    Path(__file__).parent.parent / "determined.cfg",
]


def _load() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    for p in _CFG_PATHS:
        if p.exists():
            cfg.read(p, encoding="utf-8")
            break
    return cfg


def get_fast_ctx(default: int = 131072) -> int:
    """Context window (tokens) for the fast tier (llama-server, port 8081)."""
    if "LLM_FAST_CTX" in os.environ:
        return int(os.environ["LLM_FAST_CTX"])
    return _load().getint("llm", "fast_ctx", fallback=default)


def get_quality_ctx(default: int = 32768) -> int:
    """Context window (tokens) for the quality tier (llama-server, port 8081).
    32768 = Qwen3's native max. Raised from 4096 for Discovery mode (session 123).
    To revert: change default back to 4096, or set LLM_QUALITY_CTX=4096 in env."""
    if "LLM_QUALITY_CTX" in os.environ:
        return int(os.environ["LLM_QUALITY_CTX"])
    return _load().getint("llm", "quality_ctx", fallback=default)
