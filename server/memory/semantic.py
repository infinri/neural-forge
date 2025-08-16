import os
import hashlib
from typing import Callable, Optional

_DIM = 384  # all-MiniLM-L6-v2 dimension; used for mock too
_embedder: Optional[Callable[[str], list[float]]] = None


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in ("1", "true", "yes", "on")


def is_semantic_enabled() -> bool:
    # Primary gate: explicit flag
    if _truthy(os.getenv("SEMANTIC_SEARCH_ENABLED", "false")):
        return True
    # Secondary: enabled if a non-disabled model is selected
    model = os.getenv("SEMANTIC_MODEL", "disabled").strip().lower()
    return model in ("mock", "minilm")


def get_dimension() -> int:
    return _DIM


def _mock_embed(text: str) -> list[float]:
    # Deterministic simple hash -> vector for tests/CI, normalized
    if not text:
        return [0.0] * _DIM
    # Produce a repeatable byte stream
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand to _DIM floats via cycling the digest
    vals = []
    for i in range(_DIM):
        b = h[i % len(h)]
        # Map byte 0..255 to [-1, 1]
        v = (float(b) / 127.5) - 1.0
        vals.append(v)
    # L2 normalize
    norm = sum(v * v for v in vals) ** 0.5 or 1.0
    return [v / norm for v in vals]


def get_embedder() -> Optional[Callable[[str], list[float]]]:
    global _embedder
    if _embedder is not None:
        return _embedder
    model = os.getenv("SEMANTIC_MODEL", "disabled").strip().lower()
    if model in ("", "disabled", "off", "false"):
        _embedder = None
        return _embedder
    if model == "mock":
        _embedder = _mock_embed
        return _embedder
    if model == "minilm":
        # Defer heavy import; raise clear error if not installed/configured
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "SEMANTIC_MODEL=minilm requires sentence-transformers. Install and set the model weights."
            ) from e
        model_name = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
        st_model = SentenceTransformer(model_name)

        def _st_embed(t: str) -> list[float]:
            # Returns Python list for easy JSON/DB handling
            vec = st_model.encode([t])[0]
            return [float(x) for x in vec]

        _embedder = _st_embed
        return _embedder
    # Unknown model
    raise RuntimeError(f"Unsupported SEMANTIC_MODEL={model}")


def compute_embedding(text: str) -> Optional[list[float]]:
    emb = get_embedder()
    if emb is None:
        return None
    return emb(text or "")
