"""
sots_loader.py - Load SOTS tenets from bundled JSON and provide
embedding-based search. Single source of truth for the 25 tenets;
no DB required.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

_TENETS_PATH = Path(__file__).parent / "sots_tenets.json"

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_tenets() -> list[dict]:
    """Return the 25 SOTS tenets. Cached after first load."""
    with open(_TENETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def tenet_texts() -> list[str]:
    """Return one searchable string per tenet (title + description + ask)."""
    return [
        f"[{t['id']}] {t['title']} {t['description']} Ask: {t['ask']}"
        for t in load_tenets()
    ]


def search_tenets(query_text: str, threshold: float = 0.30, top_n: int = 5) -> list[dict]:
    """
    Cosine-search tenets by embedding similarity.
    Returns list of dicts: id, title, description, ask, score.
    Returns [] on embedding failure (SOTS XIII).
    """
    try:
        from determined.agent.agent_tools import _get_embed_model
        model = _get_embed_model()
        texts = tenet_texts()
        tenets = load_tenets()
        vecs = model.encode([query_text] + texts, normalize_embeddings=True)
        scores = vecs[1:] @ vecs[0]
        results = []
        for i, score in enumerate(scores):
            if float(score) >= threshold:
                results.append({**tenets[i], "score": float(score)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]
    except Exception as exc:
        log.warning("sots_loader: embedding failed: %s", exc)
        return []
