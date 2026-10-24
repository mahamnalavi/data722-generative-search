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
