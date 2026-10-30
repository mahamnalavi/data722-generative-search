"""Search engine package for the Sahulat Home demo store.

Shared by the live app (app.py) and the Colab notebooks, so evaluation scores
describe the system that is actually deployed.
"""

import os
import time
from functools import lru_cache
from pathlib import Path

from .catalogue import load_catalogue, product_text, products_by_id
from .keyword import BM25Index

VERSION = "v2-context-chat"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def keyword_index() -> BM25Index:
    return BM25Index({p["product_id"]: product_text(p) for p in load_catalogue()})


def semantic_ready() -> bool:
    """Meaning-based search needs the saved product embeddings and a Gemini key."""
    return (DATA_DIR / "emb_definitions_v2.json").exists() and bool(os.environ.get("GEMINI_API_KEY"))


@lru_cache(maxsize=1)
def _embedder():
    from .llm import GeminiEmbedder
    return GeminiEmbedder()


@lru_cache(maxsize=512)
def embed_query(query: str) -> tuple:
    """One Gemini call per new query; repeated queries are served from memory (saves free quota)."""
    return tuple(_embedder().embed([query], kind="query", task="embed_live_query", retries=1)[0])


def search(query: str, mode: str = "hybrid", context: dict | None = None, k: int = 10) -> dict:
    """Website entry point. Falls back to keyword search if the AI side is unavailable,
    and says so in the response, so the site never breaks."""
    from . import pipeline
    t0 = time.perf_counter()
    clean = pipeline.parse_constraints(query)["clean_query"]   # embed without budget/stock words
    fallback_reason = None
    qvec = None
    if mode != "keyword":
        if not semantic_ready():
            fallback_reason = "meaning-based search is not set up yet"
        else:
            try:
                qvec = list(embed_query(clean.strip().lower()))
            except Exception as e:   # quota reached, network problem, bad key...
                fallback_reason = f"AI search unavailable ({type(e).__name__})"
        if fallback_reason:
            mode = "keyword"
    out = pipeline.run(query, mode=mode, query_vec=qvec, context=context, k=k)
    out["version"] = VERSION
    out["fallback"] = fallback_reason
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out
