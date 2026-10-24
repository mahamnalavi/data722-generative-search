"""Meaning-based search over saved embeddings (the "retrieval" in RAG).

Product embeddings are computed once in the notebook and saved under data/.
At search time we embed only the shopper's query and compare it with every
product. 195 products x 768 numbers is small enough for plain Python.

Similarity = dot product of two length-1 vectors (cosine similarity):
1.0 means the same meaning, around 0.5 or below means unrelated, for this model.
"""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=8)
def load_index(name: str) -> dict:
    """name e.g. 'emb_definitions_v2' -> {'ids': [...], 'vectors': [[...]], 'model': ..., 'dims': ...}"""
    with open(DATA_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def save_index(name: str, ids: list[str], vectors: list[list[float]], meta: dict) -> Path:
    path = DATA_DIR / f"{name}.json"
    payload = {**meta, "ids": ids, "vectors": [[round(x, 5) for x in v] for v in vectors]}
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return path


def rank(query_vec: list[float], index: dict, k: int = 10) -> list[tuple[str, float]]:
    """Return the k most similar (product_id, similarity), best first."""
    scored = [(pid, sum(a * b for a, b in zip(query_vec, vec))) for pid, vec in zip(index["ids"], index["vectors"])]
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
