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

import json
import math
import re
import time
from pathlib import Path

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
    "strip_constraint_words": True,   # False reproduces the 24 Oct budget-word bug (for the before/after)
    # Context (page + this visit): a small, bounded boost on top of rank. Tuned on dev in Notebook 02.
    "ctx_scale": 1.0,              # 0 switches context off
    "ctx_depth": 20,               # only the top 20 can be re-ordered; nothing is pulled up from further down
    "ctx_k": 10,
    "b_page": 0.006,               # product is in the category page the search was made from
    "b_cat_browsed": 0.003,        # product is in the category browsed most this visit
    "b_type": 0.008,               # same product type as one viewed this visit
    "b_price": 0.010,              # the price variant closest to this visit's typical price (among variants of one type)
}

# Settings tuned on the dev split (Notebook 02), reviewed, then copied to data/live_params.json.
_LIVE = Path(__file__).resolve().parent.parent / "data" / "live_params.json"
if _LIVE.exists():
    PARAMS.update(json.loads(_LIVE.read_text()))

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
                clean = pat.sub(" ", clean)   # remove every budget phrase, not just the first
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


# ---------------- 5. context: page + this visit (soft boost) ----------------
def apply_context(ranked, context, P):
    """Re-order the top results slightly using the page and this visit's browsing.

    Rules that keep this safe (decision 4 and the brief's "never overrides an explicit request"):
      - runs AFTER the hard budget/stock filter, so it can never bring back an excluded item;
      - only the top `ctx_depth` results can move, by at most a few places (boost is small vs rank gaps);
      - the price boost applies only between price variants of the same product type.
    Base score = 1/(ctx_k + rank). At ctx_scale 1, the largest total boost (0.027) is about
    the gap between ranks 1 and 6, so context can lift a relevant item a few places but
    cannot turn an unrelated product into the top answer from deep in the list.
    """
    if not context or not P["ctx_scale"]:
        return ranked, {"context_used": False}
    by_id = products_by_id()
    head, tail = ranked[:P["ctx_depth"]], ranked[P["ctx_depth"]:]
    page = context.get("page_category")
    cats = context.get("categories_browsed") or {}
    top_cat = max(cats, key=cats.get) if cats else None
    types = set(context.get("product_types_viewed") or [])
    band = context.get("price_band") or {}
    median = band.get("median")
    # among price variants of the same type in the top results, the one closest to this visit's
    # typical price is the "preferred" variant
    preferred = set()
    if median:
        groups = {}
        for pid, _ in head:
            groups.setdefault(by_id[pid]["product_type"], []).append(pid)
        for pids in groups.values():
            if len(pids) > 1:
                preferred.add(min(pids, key=lambda i: abs(math.log(by_id[i]["price_pkr"] / median))))
    a = P["ctx_scale"]
    rescored = []
    for r, (pid, _) in enumerate(head, start=1):
        p = by_id[pid]
        boost = 0.0
        if page and p["category"] == page:
            boost += a * P["b_page"]
        if top_cat and p["category"] == top_cat:
            boost += a * P["b_cat_browsed"]
        if p["product_type"] in types:
            boost += a * P["b_type"]
        if pid in preferred:
            boost += a * P["b_price"]
        rescored.append((pid, 1 / (P["ctx_k"] + r) + boost))
    rescored.sort(key=lambda x: -x[1])
    moved = sum(1 for (a_, _), (b_, _) in zip(head, rescored) if a_ != b_)
    return rescored + tail, {"context_used": True, "positions_changed": moved}


# ---------------- full search ----------------
def run(query: str, mode: str = "hybrid", query_vec=None, context: dict | None = None,
        k: int = 10, params: dict | None = None, constraints: dict | None = None) -> dict:
    """Constraints -> retrieve -> filter -> context -> confidence. Used by the website, the chat and
    the evaluation. `constraints` adds limits stated elsewhere (e.g. earlier in a chat)."""
    P = {**PARAMS, **(params or {})}
    t0 = time.perf_counter()
    cons = parse_constraints(query)
    if constraints:
        if constraints.get("max_price") is not None:
            cons["max_price"] = constraints["max_price"]
        cons["in_stock"] = cons["in_stock"] or bool(constraints.get("in_stock"))
    text = cons["clean_query"] if P["strip_constraint_words"] else query
    hits, diag = retrieve(text, mode, query_vec=query_vec, params=P)
    by_id = products_by_id()
    kept = [(pid, s) for pid, s in hits if satisfies(by_id[pid], cons)]
    removed = len(hits) - len(kept)
    kept, ctx_diag = apply_context(kept, context, P)

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
        "context": ctx_diag,
        "no_close_match": no_close_match,
        "diagnostics": {k_: round(v, 4) for k_, v in diag.items()},
        "results": [{**by_id[pid], "score": round(s, 4)} for pid, s in kept[:k]],
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def catalogue_ids():
    return [p["product_id"] for p in load_catalogue()]
