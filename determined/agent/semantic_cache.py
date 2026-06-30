# determined/agent/semantic_cache.py
#
# Semantic response cache: embed a prompt, cosine-search prior responses,
# return the stored answer if similarity >= threshold. Writes are append-only.
# The embedding is stored as a raw float32 blob alongside the response text.
#
# Table: semantic_cache (created by persistence_engine on first open)
# Wired into agent_tools._distill_to_one_sentence and _synthesize_with_ollama.

from __future__ import annotations

import hashlib
import logging
import sqlite3
import struct
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)

_EMBED_DIM = 384  # all-MiniLM-L6-v2 output dimension
CACHE_THRESHOLD = 0.92

_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _embed(text: str) -> np.ndarray:
    model = _get_embed_model()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec.astype(np.float32)


def _to_blob(vec: np.ndarray) -> bytes:
    return vec.tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def ensure_semantic_cache_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS semantic_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_hash TEXT NOT NULL,
        embedding BLOB NOT NULL,
        response TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sc_hash ON semantic_cache(prompt_hash)"
    )


def lookup(prompt: str, conn: sqlite3.Connection, threshold: float = CACHE_THRESHOLD) -> str | None:
    """
    Embed prompt, cosine-search semantic_cache, return stored response if
    best match >= threshold. Returns None on miss or embedding failure.
    """
    try:
        rows = conn.execute(
            "SELECT embedding, response FROM semantic_cache"
        ).fetchall()
    except Exception:
        return None  # table may not exist yet
    if not rows:
        return None
    try:
        query_vec = _embed(prompt)
    except Exception as exc:
        logger.warning("semantic_cache.lookup: embed failed: %s", exc)
        return None
    best_score = -1.0
    best_response = None
    for blob, response in rows:
        stored_vec = _from_blob(blob)
        score = float(np.dot(query_vec, stored_vec))
        if score > best_score:
            best_score = score
            best_response = response
    if best_score >= threshold:
        logger.debug("semantic_cache hit (score=%.3f)", best_score)
        return best_response
    return None


def store(prompt: str, response: str, conn: sqlite3.Connection) -> None:
    """
    Embed prompt and store (embedding, response) in semantic_cache.
    Silently skips on embedding failure or DB error.
    """
    try:
        vec = _embed(prompt)
    except Exception as exc:
        logger.warning("semantic_cache.store: embed failed: %s", exc)
        return
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "INSERT INTO semantic_cache (prompt_hash, embedding, response, created_at) "
            "VALUES (?, ?, ?, ?)",
            (prompt_hash, _to_blob(vec), response, now),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("semantic_cache.store: write failed: %s", exc)
