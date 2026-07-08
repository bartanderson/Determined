"""
grasp_loader.py - Load GRASP principles from bundled JSON and provide
embedding-based search. Mirrors sots_loader.py. No DB required.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

_PRINCIPLES_PATH = Path(__file__).parent / "grasp_principles.json"

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_principles() -> list[dict]:
    """Return the 9 GRASP principles. Cached after first load."""
    with open(_PRINCIPLES_PATH, encoding="utf-8") as f:
        return json.load(f)


def principle_texts() -> list[str]:
    """Return one searchable string per principle (id + name + description + violation_signal + ask)."""
    return [
        f"[{p['id']}] {p['name']} {p['description']} Violation: {p['violation_signal']} Ask: {p['ask']}"
        for p in load_principles()
    ]


def search_principles(query_text: str, threshold: float = 0.30, top_n: int = 3) -> list[dict]:
    """
    Cosine-search GRASP principles by embedding similarity.
    Returns list of dicts: id, name, description, violation_signal, ask, score.
    Returns [] on embedding failure.
    """
    try:
        from determined.agent.agent_tools import _get_embed_model
        model = _get_embed_model()
        texts = principle_texts()
        principles = load_principles()
        vecs = model.encode([query_text] + texts, normalize_embeddings=True)
        scores = vecs[1:] @ vecs[0]
        results = []
        for i, score in enumerate(scores):
            if float(score) >= threshold:
                results.append({**principles[i], "score": float(score)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]
    except Exception as exc:
        log.warning("grasp_loader: embedding failed: %s", exc)
        return []
