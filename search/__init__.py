"""Search engine package for the Sahulat Home demo store.

Shared by the live app (app.py) and the Colab notebook.
"""

import time
from functools import lru_cache

from .catalogue import load_catalogue, product_text, products_by_id
from .keyword import BM25Index

VERSION = "v0-keyword"


@lru_cache(maxsize=1)
def keyword_index() -> BM25Index:
    return BM25Index({p["product_id"]: product_text(p) for p in load_catalogue()})


def search(query: str, mode: str = "keyword", context: dict | None = None, k: int = 10) -> dict:
    """Run one search and return results plus timing.

    v0 supports mode="keyword" only. `context` (category page and this-visit
    behaviour) is accepted but not used yet; it is added in a later version.
    """
    t0 = time.perf_counter()
    if mode != "keyword":
        raise ValueError(f"Unknown mode {mode!r}; v0 supports 'keyword' only")
    hits = keyword_index().search(query, k=k)
    by_id = products_by_id()
    results = [{**by_id[pid], "score": round(s, 3)} for pid, s in hits]
    return {
        "query": query,
        "mode": mode,
        "version": VERSION,
        "results": results,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
