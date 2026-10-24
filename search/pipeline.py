"""The search pipeline: one function used by the website AND by the evaluation.

Steps for every search (a fixed pipeline, see decision 3):
  1. Read explicit constraints from the query text (budget, "in stock") with simple rules.
  2. Retrieve candidates:
       keyword               BM25 over the store's own text (the baseline)
       semantic_catalogue    meaning-based, over the store's own text
       semantic_definitions  meaning-based, over the AI utility definitions
       hybrid                keyword + semantic_definitions combined (what the live site uses)
  3. Apply hard constraints: over-budget or out-of-stock items are removed, never just demoted.
  4. Decide confidence: if nothing is close enough, say "no close match" honestly.
  5. (Sunday, v2) apply page and visit context as a soft boost; the chat model explains.

HYBRID = Reciprocal Rank Fusion (RRF), a standard way to merge two ranked lists:
  score(product) = w_kw / (K + rank_in_keyword) + w_sem / (K + rank_in_semantic)
A product near the top of either list scores well, and near the top of both scores best.
Exact name searches ("pressure cooker") stay strong through the keyword list, while
utility searches ("stop milk boiling over") are carried by the semantic list.
"""

import re
import time

from .catalogue import load_catalogue, products_by_id
from .semantic import load_index, rank

# Defaults; tuned on the DEV split in Notebook 02 (never on the test split).
PARAMS = {
    "rrf_k": 60,
    "w_keyword": 1.0,
    "w_semantic": 1.0,
    "no_match_similarity": 0.60,   # below this best similarity (and no strong keyword hit) -> "no close match"
    "strong_keyword_score": 8.0,   # BM25 score treated as a confident name match
    "semantic_pool": 50,           # how many semantic candidates go into the merge
}

DEF_INDEX = "emb_definitions_v2"
CAT_INDEX = "emb_catalogue"
MODES = ("keyword", "semantic_catalogue", "semantic_definitions", "hybrid")

# ---------------- 1. constraints from the query text ----------------
_NUM = r"(?:rs\.?|pkr)?\s*([\d][\d,]*(?:\.\d+)?)\s*(k)?"
BUDGET_PATTERNS = [
    re.compile(r"\b(?:under|below|less than|within|upto|up to|max(?:imum)?|budget(?: of| is)?|not more than)\s*" + _NUM, re.I),
    re.compile(_NUM + r"\s*(?:rs\.?|rupees|pkr)?\s*(?:tak|se kam|or less|max)\b", re.I),
]
IN_STOCK = re.compile(r"\b(in stock|available now|abhi available|stock mein|jo available ho)\b", re.I)


def parse_constraints(query: str) -> dict:
    """Rule-based reading of budget and stock wishes (no AI needed).
    Returns e.g. {'max_price': 1500, 'in_stock': True, 'clean_query': 'emergency light'}.
    The budget/stock words are removed from the text used for matching. Without this,
    "emergency light under 2000" matched "Under-Bed Storage Bag" on the word "under"
    (found while testing on 24 Oct; see decisions log)."""
    out = {"max_price": None, "in_stock": bool(IN_STOCK.search(query)), "clean_query": query}
    clean = IN_STOCK.sub(" ", query)
    for pat in BUDGET_PATTERNS:
        m = pat.search(clean)
        if m:
            value = float(m.group(1).replace(",", ""))
            if m.group(2):
                value *= 1000
            if value >= 50:            # ignore numbers like "3 tiers" that sneak through
                out["max_price"] = int(value)
                clean = clean[:m.start()] + " " + clean[m.end():]
                break
    out["clean_query"] = re.sub(r"\s+", " ", clean).strip(" ,.-") or query
    return out


def satisfies(p: dict, cons: dict) -> bool:
    if cons.get("max_price") is not None and p["price_pkr"] > cons["max_price"]:
        return False
    if cons.get("in_stock") and not p["in_stock"]:
        return False
    return True


# ---------------- 2. retrieval ----------------
def _keyword(query, k):
    from . import keyword_index
    return keyword_index().search(query, k=k)


def retrieve(query: str, mode: str, query_vec=None, params: dict | None = None, pool: int = 60):
    """Return (ranked list of (product_id, score), diagnostics dict). Semantic modes need query_vec."""
    P = {**PARAMS, **(params or {})}
    diag = {}
    if mode == "keyword":
        hits = _keyword(query, pool)
        diag["top_keyword"] = hits[0][1] if hits else 0.0
        return hits, diag
    if query_vec is None:
        raise ValueError("semantic modes need a query embedding")
    if mode == "semantic_catalogue":
        hits = rank(query_vec, load_index(CAT_INDEX), pool)
        diag["top_similarity"] = hits[0][1] if hits else 0.0
        return hits, diag
    sem = rank(query_vec, load_index(DEF_INDEX), max(pool, P["semantic_pool"]))
    diag["top_similarity"] = sem[0][1] if sem else 0.0
    if mode == "semantic_definitions":
        return sem[:pool], diag
    if mode == "hybrid":
        kw = _keyword(query, pool)
        diag["top_keyword"] = kw[0][1] if kw else 0.0
        fused = {}
        for r, (pid, _) in enumerate(kw, start=1):
            fused[pid] = fused.get(pid, 0) + P["w_keyword"] / (P["rrf_k"] + r)
        for r, (pid, _) in enumerate(sem[:P["semantic_pool"]], start=1):
            fused[pid] = fused.get(pid, 0) + P["w_semantic"] / (P["rrf_k"] + r)
        return sorted(fused.items(), key=lambda x: -x[1])[:pool], diag
    raise ValueError(f"unknown mode {mode!r}; choose from {MODES}")


# ---------------- full search ----------------
def run(query: str, mode: str = "hybrid", query_vec=None, context: dict | None = None,
        k: int = 10, params: dict | None = None) -> dict:
    """Constraints -> retrieve -> filter -> confidence. Used by the website and the evaluation."""
    P = {**PARAMS, **(params or {})}
    t0 = time.perf_counter()
    cons = parse_constraints(query)
    hits, diag = retrieve(cons["clean_query"], mode, query_vec=query_vec, params=P)
    by_id = products_by_id()
    kept = [(pid, s) for pid, s in hits if satisfies(by_id[pid], cons)]
    removed = len(hits) - len(kept)

    strong_kw = diag.get("top_keyword", 0.0) >= P["strong_keyword_score"]
    if mode == "keyword":
        no_close_match = not kept
    else:
        no_close_match = (diag.get("top_similarity", 0.0) < P["no_match_similarity"]) and not strong_kw
    if not kept:
        no_close_match = True

    return {
        "query": query,
        "mode": mode,
        "constraints": cons,
        "removed_by_constraints": removed,
        "no_close_match": no_close_match,
        "diagnostics": {k_: round(v, 4) for k_, v in diag.items()},
        "results": [{**by_id[pid], "score": round(s, 4)} for pid, s in kept[:k]],
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def catalogue_ids():
    return [p["product_id"] for p in load_catalogue()]
