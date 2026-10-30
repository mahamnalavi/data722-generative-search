"""Evaluation: runs the labelled queries through the real pipeline and scores them.

Metrics (plain-language definitions; Phase 1 metric names in brackets):
  Hit@k              share of answerable queries with at least one correct product in the top k
  MRR                average of 1/rank of the first correct product (rewards ranking it higher)
  keyword miss rate  share of answerable queries where KEYWORD search has no correct product in its
                     top 10  [Phase 1 "problem measure"]
  correct no-match   share of queries with no correct product where the system says "no close match"
  false no-match     share of answerable queries wrongly flagged "no close match"
  confidently wrong  the system did NOT flag "no close match", yet the top result is wrong (or nothing
                     should have been shown)  [Phase 1 "confidently-wrong rate"]
  constraint violations   top-5 results that break the query's budget or stock limit [Phase 1]
"""

import time

from . import pipeline


def query_text_for_embedding(q: str) -> str:
    """Exactly what the live site embeds: the query without budget/stock words, lower-cased."""
    return pipeline.parse_constraints(q)["clean_query"].strip().lower()


def run_queries(rows, mode, qvecs=None, params=None, k=10):
    out = []
    for r in rows:
        t0 = time.perf_counter()
        res = pipeline.run(r["query"], mode=mode, query_vec=None if mode == "keyword" else qvecs[r["qid"]],
                           k=k, params=params)
        out.append({"qid": r["qid"], "mode": mode, "ids": [p["product_id"] for p in res["results"]],
                    "prices": [p["price_pkr"] for p in res["results"]],
                    "stock": [p["in_stock"] for p in res["results"]],
                    "no_close_match": res["no_close_match"],
                    "top_similarity": res["diagnostics"].get("top_similarity"),
                    "top_keyword": res["diagnostics"].get("top_keyword"),
                    "top_similarity_shown": res["diagnostics"].get("top_similarity_shown"),
                    "ms": (time.perf_counter() - t0) * 1000})
    return out


def _first_hit(ids, rel):
    for i, pid in enumerate(ids, start=1):
        if pid in rel:
            return i
    return None


def metrics(rows, runs):
    by_q = {r["qid"]: r for r in rows}
    ans = [x for x in runs if not by_q[x["qid"]]["expects_no_match"]]
    nom = [x for x in runs if by_q[x["qid"]]["expects_no_match"]]
    m = {"queries": len(runs), "answerable": len(ans), "no_match_queries": len(nom)}
    for k in (1, 5, 10):
        m[f"hit@{k}"] = _rate([_first_hit(x["ids"][:k], set(by_q[x["qid"]]["relevant_ids"])) is not None for x in ans])
    m["mrr"] = round(sum(1 / (_first_hit(x["ids"], set(by_q[x["qid"]]["relevant_ids"])) or float("inf"))
                         for x in ans) / max(len(ans), 1), 3)
    m["correct_no_match"] = _rate([x["no_close_match"] for x in nom])
    m["false_no_match"] = _rate([x["no_close_match"] for x in ans])
    cw = []
    for x in runs:
        q = by_q[x["qid"]]
        if x["no_close_match"]:
            cw.append(False)
        elif q["expects_no_match"]:
            cw.append(bool(x["ids"]))
        else:
            cw.append(not x["ids"] or x["ids"][0] not in set(q["relevant_ids"]))
    m["confidently_wrong"] = _rate(cw)
    viol = total = 0
    for x in runs:
        q = by_q[x["qid"]]
        if q["expected_max_price"] is None and not q["expected_in_stock"]:
            continue
        for price, stock in zip(x["prices"][:5], x["stock"][:5]):
            total += 1
            if (q["expected_max_price"] is not None and price > q["expected_max_price"]) or (q["expected_in_stock"] and not stock):
                viol += 1
    m["constraint_violations"] = f"{viol}/{total}"
    m["avg_ms"] = round(sum(x["ms"] for x in runs) / max(len(runs), 1), 1)
    return m


def hit_by_style(rows, runs, k=5):
    by_q = {r["qid"]: r for r in rows}
    styles = {}
    for x in runs:
        q = by_q[x["qid"]]
        if q["expects_no_match"]:
            continue
        styles.setdefault(q["style"], []).append(_first_hit(x["ids"][:k], set(q["relevant_ids"])) is not None)
    return {s: _rate(v) for s, v in sorted(styles.items())}


def keyword_miss_rate(rows, keyword_runs):
    by_q = {r["qid"]: r for r in rows}
    ans = [x for x in keyword_runs if not by_q[x["qid"]]["expects_no_match"]]
    utility = [x for x in ans if by_q[x["qid"]]["style"] != "name"]
    miss = lambda xs: _rate([_first_hit(x["ids"][:10], set(by_q[x["qid"]]["relevant_ids"])) is None for x in xs])
    return {"all_answerable": miss(ans), "utility_queries_only": miss(utility)}


def tune_rrf(rows, qvecs, w_grid=(0.5, 1.0, 1.5, 2.0, 3.0), k_grid=(10, 60)):
    """Pick hybrid weights on the DEV split: best Hit@5, ties broken by MRR."""
    table = []
    for rk in k_grid:
        for w in w_grid:
            p = {"rrf_k": rk, "w_semantic": w, "w_keyword": 1.0}
            m = metrics(rows, run_queries(rows, "hybrid", qvecs, params=p))
            table.append({**p, "hit@5": m["hit@5"], "mrr": m["mrr"], "hit@1": m["hit@1"]})
    best = max(table, key=lambda t: (t["hit@5"], t["mrr"], -abs(t["w_semantic"] - 1)))
    return {k: best[k] for k in ("rrf_k", "w_semantic", "w_keyword")}, table


def tune_no_match(rows, qvecs, mode="hybrid", params=None, grid=None, kw_grid=(6.0, 8.0, 10.0, 1e9)):
    """Pick the 'no close match' similarity threshold on DEV: best balanced accuracy of the
    yes/no decision ((correct no-match + correctly not flagged) / 2), ties -> lower threshold."""
    grid = grid or [round(0.40 + 0.01 * i, 2) for i in range(46)]
    table = []
    for kw in kw_grid:
        for t in grid:
            p = {**(params or {}), "no_match_similarity": t, "strong_keyword_score": kw}
            m = metrics(rows, run_queries(rows, mode, qvecs, params=p))
            bal = round((m["correct_no_match"] + (1 - m["false_no_match"])) / 2, 3)
            table.append({"no_match_similarity": t, "strong_keyword_score": kw, "balanced_acc": bal,
                          "correct_no_match": m["correct_no_match"], "false_no_match": m["false_no_match"]})
    best = max(table, key=lambda r: (r["balanced_acc"], -r["no_match_similarity"]))
    return {"no_match_similarity": best["no_match_similarity"], "strong_keyword_score": best["strong_keyword_score"]}, table


def _rate(flags):
    flags = list(flags)
    return round(sum(bool(f) for f in flags) / len(flags), 3) if flags else None


# ---------------- context (page + this visit) ----------------
# Synthetic sessions. Honest caveat: they can only show the personalisation the
# generator built in, so they test whether context HELPS or HARMS retrieval,
# not whether real shoppers benefit.
CATS = ["Kitchenware", "Tools", "Organizers", "Furniture"]


def make_sessions(row, catalogue):
    """Return {'helpful': ctx, 'misleading': ctx, 'target': product_id} for an answerable query.

    helpful:    opened from the target product's category page; viewed 2 other products in that
                category (not the target's type); browsing prices centred on the target's price.
    misleading: opened from a different category page, viewing and pricing in that category.
    The target is one of the correct products (for multi-variant types, a fixed random variant:
    the one this shopper's price range points to)."""
    import random as _r
    rng = _r.Random("session-" + row["qid"])
    by_id = {p["product_id"]: p for p in catalogue}
    target = by_id[rng.choice(sorted(row["relevant_ids"]))]
    def ctx(cat, price):
        pool = [p for p in catalogue if p["category"] == cat and p["product_type"] not in row["relevant_types"]]
        viewed = rng.sample(pool, 2)
        return {"page_category": cat, "categories_browsed": {cat: 3},
                "product_types_viewed": [p["product_type"] for p in viewed],
                "price_band": {"min": price, "max": price, "median": price}}
    other = CATS[(CATS.index(target["category"]) + 1 + rng.randrange(3)) % 4]
    other_price = rng.choice([p["price_pkr"] for p in catalogue if p["category"] == other])
    return {"helpful": ctx(target["category"], target["price_pkr"]),
            "misleading": ctx(other, other_price), "target": target["product_id"]}


def run_with_context(rows, mode, qvecs, catalogue, params=None, k=10):
    """Run each answerable query three ways: no context, helpful session, misleading session."""
    out = {"none": [], "helpful": [], "misleading": [], "targets": {}}
    for r in rows:
        if r["expects_no_match"]:
            continue
        sess = make_sessions(r, catalogue)
        out["targets"][r["qid"]] = sess["target"]
        for kind in ("none", "helpful", "misleading"):
            res = pipeline.run(r["query"], mode=mode, query_vec=None if mode == "keyword" else qvecs[r["qid"]],
                               context=None if kind == "none" else sess[kind], k=k, params=params)
            out[kind].append({"qid": r["qid"], "ids": [p["product_id"] for p in res["results"]]})
    return out


def context_metrics(rows, ctx_runs, catalogue):
    """Hit@1/5 with no / helpful / misleading context, context-override errors, price personalisation."""
    by_q = {r["qid"]: r for r in rows}
    by_id = {p["product_id"]: p for p in catalogue}
    def hit(runs, k):
        return _rate([any(i in set(by_q[x["qid"]]["relevant_ids"]) for i in x["ids"][:k]) for x in runs])
    m = {}
    for kind in ("none", "helpful", "misleading"):
        m[f"hit@1_{kind}"] = hit(ctx_runs[kind], 1)
        m[f"hit@5_{kind}"] = hit(ctx_runs[kind], 5)
    # Phase 1 metric: context pushes a correct result out of the top 5
    override = 0
    for a, b in zip(ctx_runs["none"], ctx_runs["misleading"]):
        rel = set(by_q[a["qid"]]["relevant_ids"])
        if any(i in rel for i in a["ids"][:5]) and not any(i in rel for i in b["ids"][:5]):
            override += 1
    m["context_override_errors"] = f"{override}/{len(ctx_runs['none'])}"
    # price personalisation: for products sold in several price variants, does the variant matching
    # this visit's price range come first among the correct variants?
    pers = {"none": [], "helpful": []}
    for kind in pers:
        for x in ctx_runs[kind]:
            q = by_q[x["qid"]]
            rel_shown = [i for i in x["ids"] if i in set(q["relevant_ids"])]
            same_type = [i for i in q["relevant_ids"] if by_id[i]["product_type"] == by_id[ctx_runs["targets"][x["qid"]]]["product_type"]]
            if len(same_type) < 2 or not rel_shown:
                continue
            pers[kind].append(rel_shown[0] == ctx_runs["targets"][x["qid"]])
    m["price_variant_first_none"] = _rate(pers["none"])
    m["price_variant_first_helpful"] = _rate(pers["helpful"])
    m["price_variant_queries"] = len(pers["helpful"])
    return m


def tune_context(rows, qvecs, catalogue, params, mode="hybrid",
                 grid_page=(0.0, 0.003, 0.006), grid_type=(0.0, 0.004, 0.008), grid_price=(0.0, 0.010)):
    """Pick each context weight on DEV. Objective = Hit@1 with a helpful session
    + Hit@5 with a misleading session (help when right, don't lose correct results when wrong)
    + half the price-personalisation rate. Ties -> the weaker (safer) setting."""
    table = []
    for bp in grid_page:
        for bt in grid_type:
            for bpr in grid_price:
                p = {**params, "ctx_scale": 1.0, "b_page": bp, "b_cat_browsed": bp / 2, "b_type": bt, "b_price": bpr}
                m = context_metrics(rows, run_with_context(rows, mode, qvecs, catalogue, params=p), catalogue)
                obj = (m["hit@1_helpful"] or 0) + (m["hit@5_misleading"] or 0) + 0.5 * (m["price_variant_first_helpful"] or 0)
                table.append({"b_page": bp, "b_type": bt, "b_price": bpr, "objective": round(obj, 3), **m})
    best = max(table, key=lambda t: (t["objective"], -(t["b_page"] + t["b_type"] + t["b_price"])))
    chosen = {"ctx_scale": 1.0, "b_page": best["b_page"], "b_cat_browsed": best["b_page"] / 2,
              "b_type": best["b_type"], "b_price": best["b_price"]}
    return chosen, table


# ---------------- page context on ambiguous words ----------------
# One word, different meaning depending on the page it is searched from. This tests the
# instructor's "the search knows which category page it was opened from" directly.
AMBIGUOUS = [
    ("box", {"Organizers": ["storage_cubes", "under_bed_storage", "medicine_box", "cable_box"],
             "Tools": ["toolbox"], "Kitchenware": ["masala_dabba", "hot_pot"]}),
    ("stand", {"Furniture": ["plant_stand", "coat_stand", "rehal"], "Organizers": ["mug_tree", "drying_stand"]}),
    ("cutter", {"Kitchenware": ["pizza_cutter", "mandoline_slicer", "apple_corer"],
                "Tools": ["utility_knife", "hacksaw", "wire_stripper"]}),
]


def page_context_check(qvecs_by_word, catalogue, params, k=3, mode="hybrid"):
    """For each ambiguous word and page: is a product that fits THAT page in the top k,
    without page context vs with it?"""
    types_of = {}
    for p in catalogue:
        types_of.setdefault(p["product_type"], []).append(p["product_id"])
    rows = []
    for word, pages in AMBIGUOUS:
        for page, types in pages.items():
            rel = {pid for t in types for pid in types_of[t]}
            out = {"word": word, "page": page}
            for label, ctx in (("without page", None), ("with page", {"page_category": page, "categories_browsed": {page: 1}})):
                res = pipeline.run(word, mode=mode, query_vec=qvecs_by_word[word], context=ctx, k=k, params=params)
                ids = [r["product_id"] for r in res["results"]]
                out[f"fits page in top {k}: {label}"] = any(i in rel for i in ids)
                out[f"top result: {label}"] = res["results"][0]["title"][:40] if res["results"] else "-"
            rows.append(out)
    return rows
