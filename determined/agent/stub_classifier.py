# determined/agent/stub_classifier.py
#
# Inference wrapper for the SetFit-trained stub intent classifier.
# Trained model lives at C:\Users\bartl\models\setfit\stub_classifier\
# and is loaded lazily on first call.
#
# Classes:
#   0 = genuinely-unknown
#   1 = design-intent-stated
#   2 = concept-not-applicable
#
# No setfit dependency at inference time -- uses sentence_transformers + sklearn only.
# Falls back gracefully to None if the model directory is not found.

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

MODEL_DIR = Path(r"C:\Users\bartl\models\setfit\stub_classifier")

_st_model  = None    # SentenceTransformer (fine-tuned body)
_head      = None    # sklearn classifier head
_labels    = None    # {int: str} from label_map.json
_available = None    # tri-state: None=not-checked, True=ok, False=missing

CLASS_NAMES = {
    0: "genuinely-unknown",
    1: "design-intent-stated",
    2: "concept-not-applicable",
}

# Fallback modal-verb check used when model is unavailable
_MODAL_RE = re.compile(
    r'\b(would|should|could|meant to|intended to|is supposed to|is meant to)\b',
    re.IGNORECASE,
)


def _load() -> bool:
    """
    Lazy-load the model. Returns True if available.
    Uses sentence_transformers + sklearn directly — no setfit package needed at inference.
    """
    global _st_model, _head, _labels, _available
    if _available is not None:
        return _available
    if not MODEL_DIR.exists():
        _available = False
        return False
    try:
        import pickle, json
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer(str(MODEL_DIR))
        with open(MODEL_DIR / "model_head.pkl", "rb") as f:
            _head = pickle.load(f)
        with open(MODEL_DIR / "label_map.json") as f:
            raw = json.load(f)
            _labels = {int(k): v for k, v in raw.items()}
        _available = True
    except Exception:
        _available = False
    return _available


def classify_text(text: str) -> Optional[dict]:
    """
    Classify a stub's docstring/comment text.

    Returns dict with keys:
        label      : str  — class name
        class_id   : int  — 0/1/2
        available  : bool — False if model not loaded (caller should fallback)

    Returns None if text is empty and no signal is possible.
    """
    if not text or not text.strip():
        return {"label": "genuinely-unknown", "class_id": 0, "available": True}

    if not _load():
        return {"label": None, "class_id": None, "available": False}

    vec = _st_model.encode([text], normalize_embeddings=True)
    pred = int(_head.predict(vec)[0])
    label = _labels.get(pred, CLASS_NAMES.get(pred, str(pred)))
    return {"label": label, "class_id": pred, "available": True}


def has_intent(text: str) -> bool:
    """
    True if text signals design-intent-stated.
    Uses SetFit model when available; falls back to modal-verb regex.
    """
    result = classify_text(text)
    if result and result["available"]:
        return result["class_id"] == 1
    # Fallback: sentence-level embedding + modal verbs (original hybrid)
    return _fallback_has_intent(text)


def has_removal(text: str) -> bool:
    """
    True if text signals concept-not-applicable.
    Uses SetFit model when available; falls back to embedding similarity.
    """
    result = classify_text(text)
    if result and result["available"]:
        return result["class_id"] == 2
    return _fallback_has_removal(text)


def _fallback_has_intent(text: str) -> bool:
    """Hybrid fallback: embedding prototypes OR modal verbs."""
    if bool(_MODAL_RE.search(text)):
        return True
    try:
        from determined.oracle.embedding_model import embed_text, cosine_similarity
        _INTENT_PROTOTYPES = [
            "implement this when the dependency is ready",
            "to be implemented",
            "returns placeholder until wired up",
            "stub: fill in when prerequisite is built",
            "not yet implemented, waiting on upstream",
            "frontier: implement against endpoint",
        ]
        proto_vecs = [embed_text(p) for p in _INTENT_PROTOTYPES]
        sentences = [s.strip() for s in re.split(r'[.\n]', text) if s.strip()]
        for sentence in sentences:
            vec = embed_text(sentence)
            if any(cosine_similarity(vec, pv) >= 0.35 for pv in proto_vecs):
                return True
    except Exception:
        pass
    return False


def _fallback_has_removal(text: str) -> bool:
    """Fallback: embedding similarity against removal prototypes."""
    try:
        from determined.oracle.embedding_model import embed_text, cosine_similarity
        _REMOVAL_PROTOTYPES = [
            "this concept was removed and does not belong",
            "deliberately absent, not part of this system",
            "return empty, concept dropped by design",
            "for compatibility only, not used",
            "deprecated and no longer applicable",
            "this feature does not exist in the new system",
            "always returns empty, concept was eliminated",
        ]
        proto_vecs = [embed_text(p) for p in _REMOVAL_PROTOTYPES]
        sentences = [s.strip() for s in re.split(r'[.\n]', text) if s.strip()]
        for sentence in sentences:
            vec = embed_text(sentence)
            if any(cosine_similarity(vec, pv) >= 0.35 for pv in proto_vecs):
                return True
    except Exception:
        pass
    return False
