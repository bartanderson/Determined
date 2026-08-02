# tools/analysis/oracle/embedding_model.py
#
# Lightweight embedding wrapper using all-MiniLM-L6-v2 (384-dim, ~22MB).
# Lazy-loads on first use — no startup cost unless embeddings are needed.
# Normalized embeddings means cosine similarity = dot product.

import os
import threading

import numpy as np

# all-MiniLM-L6-v2 is a local, already-downloaded artifact. Passing a bare repo id
# makes SentenceTransformer resolve it against the HF Hub on every load: a network
# round-trip on a path that is required to work offline, with unbounded latency when
# the network is slow or the Hub is unreachable.
# This lives here, with the component that owns the ambient dependency, rather than at
# a call site. ui_server.py set HF_HUB_OFFLINE, so the UI was protected and every other
# entry point -- tests, CLI, scripts -- silently was not.
# setdefault, so an explicit HF_HUB_OFFLINE=0 in the environment still wins.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import logging
                import warnings
                warnings.filterwarnings("ignore", category=UserWarning, module="torch")
                warnings.filterwarnings("ignore", message=".*torch.*", category=FutureWarning)
                # CLAUDE-EDIT 2026-06-17: the warnings.filterwarnings() calls above
                # never suppressed the "W0617 ... NOTE: Redirects are currently not
                # supported in Windows or MacOs." line Bart kept seeing on every
                # ask.py run on his Windows machine - that line is emitted via the
                # standard `logging` module by torch.distributed.elastic (its own
                # absl-style formatter), not via warnings.warn(), so the warnings
                # filters above were suppressing the wrong mechanism entirely.
                # Silencing the actual source instead.
                logging.getLogger("torch.distributed.elastic").setLevel(logging.ERROR)
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> np.ndarray:
    """Embed a string. Returns a normalized 384-dim vector."""
    return get_model().encode(text, normalize_embeddings=True)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two normalized vectors = dot product."""
    return float(np.dot(a, b))


def embed_symbol(symbol: str) -> np.ndarray:
    """
    Embed a symbol name for similarity search.
    Converts dotted/underscored names to readable text before embedding
    so 'build_snapshot' embeds similarly to 'build snapshot'.
    """
    readable = symbol.replace("_", " ").replace(".", " ")
    return embed_text(readable)
