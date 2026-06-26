# tools/analysis/intent/semantic_summary.py
#
# Sub-layer A of the Intent Layer (DESIGN.md section 3).
#
# Generates and caches AI semantic summaries for files, modules, and
# subsystems. Summaries are stored in the `semantic_summaries` table
# with a source_hash for staleness detection. Generation is lazy:
# only computed on first query for a given subject, never at ingestion.
#
# LLM backend: local Ollama (same model as query_compiler.py).
# Falls back to a heuristic stub if Ollama is unreachable.

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT = 60

VALID_KINDS = {"file", "module", "subsystem"}


# ------------------------------------------------------------------
# Schema helpers (called from persistence_engine.ensure_schema)
# ------------------------------------------------------------------

def ensure_semantic_summaries_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS semantic_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        model_version TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        corpus TEXT,
        UNIQUE(subject, kind, corpus)
    )
    """)
    # Migrate existing DBs: add corpus column if absent (idempotent)
    try:
        cursor.execute("ALTER TABLE semantic_summaries ADD COLUMN corpus TEXT")
    except Exception:
        pass  # column already exists


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def get_or_generate_summary(
    connection: sqlite3.Connection,
    subject: str,
    kind: str,
    source_text: str,
    *,
    force_refresh: bool = False,
) -> dict:
    """
    Return a semantic summary for `subject` (file path, module name, or
    subsystem label), generating and caching it if needed.

    `source_text` is the raw content that will be summarised - the caller
    is responsible for reading the file or assembling the module text.
    Passing an empty string is valid; it results in a minimal stub summary.

    Returns a dict with keys: subject, kind, content, source_hash,
    model_version, generated_at, cache_hit (bool).
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")

    current_hash = _hash(source_text)

    if not force_refresh:
        cached = _load_cached(connection, subject, kind)
        if cached and cached["source_hash"] == current_hash:
            cached["cache_hit"] = True
            return cached

    content = _generate(subject, kind, source_text)
    model_version = OLLAMA_MODEL
    generated_at = datetime.now(timezone.utc).isoformat()

    _store(connection, subject, kind, content, current_hash, model_version, generated_at)

    return {
        "subject": subject,
        "kind": kind,
        "content": content,
        "source_hash": current_hash,
        "model_version": model_version,
        "generated_at": generated_at,
        "cache_hit": False,
    }


def get_summary_if_fresh(
    connection: sqlite3.Connection,
    subject: str,
    kind: str,
    source_text: str,
) -> Optional[dict]:
    """
    Return the cached summary only if it is fresh (hash matches).
    Returns None if missing or stale - does NOT trigger generation.
    Useful for building views without side-effects.
    """
    current_hash = _hash(source_text)
    cached = _load_cached(connection, subject, kind)
    if cached and cached["source_hash"] == current_hash:
        cached["cache_hit"] = True
        return cached
    return None


def list_summaries(
    connection: sqlite3.Connection,
    kind: Optional[str] = None,
) -> list[dict]:
    """List all stored summaries, optionally filtered by kind."""
    cursor = connection.cursor()
    if kind:
        cursor.execute(
            "SELECT subject, kind, content, source_hash, model_version, generated_at "
            "FROM semantic_summaries WHERE kind = ? ORDER BY subject",
            (kind,),
        )
    else:
        cursor.execute(
            "SELECT subject, kind, content, source_hash, model_version, generated_at "
            "FROM semantic_summaries ORDER BY subject"
        )
    rows = cursor.fetchall()
    return [
        {
            "subject": r[0], "kind": r[1], "content": r[2],
            "source_hash": r[3], "model_version": r[4], "generated_at": r[5],
        }
        for r in rows
    ]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _load_cached(
    connection: sqlite3.Connection, subject: str, kind: str
) -> Optional[dict]:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT subject, kind, content, source_hash, model_version, generated_at "
        "FROM semantic_summaries WHERE subject = ? AND kind = ?",
        (subject, kind),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "subject": row[0], "kind": row[1], "content": row[2],
        "source_hash": row[3], "model_version": row[4], "generated_at": row[5],
    }


def _store(
    connection: sqlite3.Connection,
    subject: str,
    kind: str,
    content: str,
    source_hash: str,
    model_version: str,
    generated_at: str,
) -> None:
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO semantic_summaries
            (subject, kind, content, source_hash, model_version, generated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (subject, kind, content, source_hash, model_version, generated_at),
    )
    connection.commit()


def _extract_structure(source_text: str, max_chars: int = 6000) -> str:
    """
    Build a compact structural view of a Python file:
      - imports block (first contiguous block of import/from/comment lines)
      - every class/def/async def signature (one line each, no bodies)
    Falls back to raw truncation if the result exceeds max_chars.
    """
    lines = source_text.splitlines()
    out = []
    i = 0
    # Header: imports + module-level comments/docstrings
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith(("import ", "from ", "#", '"""', "'''")) or stripped == "":
            out.append(lines[i])
            i += 1
        else:
            break

    # Signatures only: class/def/async def lines throughout the rest of file
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith(("class ", "def ", "async def ")):
            out.append(lines[i])
        i += 1

    result = "\n".join(out)
    if len(result) <= max_chars:
        return result
    return source_text[:max_chars]


def _generate(subject: str, kind: str, source_text: str) -> str:
    """Call Ollama; fall back to a minimal heuristic stub on failure."""
    if not source_text.strip():
        return f"[no source text provided for {kind} {subject!r}]"

    # Use a structured extract instead of raw truncation: top of file + key
    # def/class lines + docstrings, to stay under ~6000 chars while covering
    # the whole file's public API surface.
    source_excerpt = _extract_structure(source_text, max_chars=10000)
    prompt = (
        f"Analyse this Python {kind} and write 3-4 sentences describing:\n"
        f"1. Its primary responsibility (what problem it solves)\n"
        f"2. Key classes or entry-point functions and what they do\n"
        f"3. Any notable design pattern (e.g. dispatcher, FSM, pub/sub)\n"
        f"Be specific and concise. Use names from the code.\n\n"
        f"File: {subject}\n\n"
        f"Source structure:\n{source_excerpt}"
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("response", "").strip()
        if content:
            return content
        logger.warning("semantic_summary: Ollama returned empty response for %r", subject)
    except Exception as exc:
        logger.warning("semantic_summary: Ollama unavailable (%s), using heuristic stub", exc)

    return _heuristic_stub(subject, kind, source_text)


def _heuristic_stub(subject: str, kind: str, source_text: str) -> str:
    """Minimal summary when Ollama is unavailable."""
    lines = [l for l in source_text.splitlines() if l.strip()]
    line_count = len(lines)
    # Count def/class lines as a rough capability signal
    defs = sum(1 for l in lines if l.lstrip().startswith(("def ", "class ", "async def ")))
    return (
        f"[heuristic] {kind.capitalize()} {subject!r}: "
        f"{line_count} non-blank lines, {defs} definitions. "
        f"(Ollama unavailable - re-query to generate a real summary.)"
    )
