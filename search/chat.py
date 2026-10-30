""""Ask Sahulat": the chat assistant (the GENERATION side of RAG).

One turn = one AI call:
  1. Limits: budget and stock are read by rules from ALL the shopper's messages (a later budget replaces
     an earlier one), so "under 2000" said once still applies to the follow-up "any in stock?".
  2. Retrieve candidates with the same search as the search bar (meaning search on the AI definitions,
     keyword search if Gemini is unavailable), plus page and visit context:
     once for the latest message and once for the last two shopper messages joined, so both
     follow-ups ("cheaper one?") and topic changes ("now I need a ladder") find candidates.
  3. The chat model (gpt-oss-120b on Groq) picks up to 3 candidates and explains each in one line,
     in the shopper's language, or says honestly that nothing fits.
  4. Checks on the model's answer (code, not trust): any product id not among the candidates is
     dropped (grounding); budget/stock re-checked; reasons scanned for unsupported claim words.
  5. If the chat model is unavailable (quota, network), the shopper still gets the search results.

The prompt below is the "context design" at the centre of the chat: what the model sees,
in what order, and the rules it must follow.
"""

import json
import time
from functools import lru_cache
from pathlib import Path

from . import pipeline
from .catalogue import products_by_id
from .definitions import unsupported_claims

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SYSTEM_PROMPT = """You are "Ask Sahulat", the shopping assistant of Sahulat Home, an online household-goods store in Pakistan.

Rules:
1. Recommend ONLY products listed under CANDIDATES, by their id. Never invent products, prices, stock or features.
2. Pick at most 3, best first. For each, give one short reason that follows from its listed facts or uses.
3. Candidates already meet the stated budget and stock limits. If the shopper asks for cheaper, prefer lower prices.
4. If no candidate does what the shopper needs, set "no_match" to true, say so plainly, and suggest different words to search. Never force a product.
5. Reply in the language of the shopper's last message: English, Urdu script, or Roman Urdu.
6. PAGE and VISIT are soft hints for unclear requests only. The shopper's own words always win.
7. Keep "reply" under 60 words. No marketing words.

Return JSON only: {"reply": "...", "picks": [{"id": "...", "why": "..."}], "no_match": false}"""


@lru_cache(maxsize=1)
def _uses() -> dict:
    path = DATA_DIR / "definitions_v2.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8")).get("items", {})
    return {pid: d.get("used_for") or [] for pid, d in items.items() if not d.get("fallback")}


def merged_constraints(user_texts: list[str]) -> dict:
    out = {"max_price": None, "in_stock": False}
    for t in user_texts:
        c = pipeline.parse_constraints(t)
        if c["max_price"] is not None:
            out["max_price"] = c["max_price"]
        out["in_stock"] = out["in_stock"] or c["in_stock"]
    return out


def retrieval_texts(user_texts: list[str]) -> list[str]:
    """Texts to search for: the latest message, and (on a follow-up) the last two joined.
    A follow-up with no product words of its own ("under 5000 and in stock", "cheaper?") is
    searched only together with the previous message."""
    from .keyword import tokenize
    if len(user_texts) == 1:
        return [user_texts[-1]]
    joined = user_texts[-2] + " " + user_texts[-1]
    own_words = tokenize(pipeline.parse_constraints(user_texts[-1])["clean_query"])
    return [user_texts[-1], joined] if len(own_words) >= 2 else [joined]


def describe_context(context: dict | None) -> str:
    if not context:
        return "PAGE: home page | VISIT: nothing yet"
    page = context.get("page_category") or "home"
    cats = context.get("categories_browsed") or {}
    types = context.get("product_types_viewed") or []
    band = context.get("price_band")
    visit = []
    if cats:
        visit.append("browsed " + ", ".join(f"{c} ({n} pages)" for c, n in cats.items()))
    if types:
        visit.append("viewed " + ", ".join(t.replace("_", " ") for t in types[:5]))
    if band:
        visit.append(f"prices viewed Rs {band['min']:,} to Rs {band['max']:,}")
    searches = [q for q in (context.get("recent_searches") or []) if q][-3:]
    if searches:
        visit.append("earlier searches this visit: " + "; ".join(f'"{q[:60]}"' for q in searches))
    return f"PAGE: opened from the {page} page | VISIT: " + ("; ".join(visit) or "nothing yet")


def build_user_prompt(messages, cons, context, candidates) -> str:
    by_id = products_by_id()
    uses = _uses()
    convo = "\n".join(f'{"Shopper" if m["role"] == "user" else "Assistant"}: {m["content"]}' for m in messages[-6:])
    limits = []
    if cons["max_price"] is not None:
        limits.append(f"max price Rs {cons['max_price']:,}")
    if cons["in_stock"]:
        limits.append("in stock only")
    lines = []
    for pid in candidates:
        p = by_id[pid]
        specs = "; ".join(f"{k}: {v}" for k, v in p["attributes"].items())
        use = "; ".join(uses.get(pid, [])) or "-"
        stock = "in stock" if p["in_stock"] else "out of stock"
        lines.append(f"- {pid} | {p['title']} | Rs {p['price_pkr']:,} | {stock} | uses: {use} | specs: {specs}")
    return (f"CONVERSATION (latest last):\n{convo}\n\n"
            f"LIMITS: {', '.join(limits) or 'none stated'}\n"
            f"{describe_context(context)}\n\n"
            f"CANDIDATES:\n" + ("\n".join(lines) or "(none: nothing in the catalogue matched)"))


def respond(messages, context=None, embed_fn=None, llm=None, params=None, k_each=6, live=False) -> dict:
    """One chat turn. messages: [{'role': 'user'|'assistant', 'content': str}, ...], last one from the shopper.
    embed_fn(list_of_texts) -> list_of_vectors, or None for keyword-only retrieval."""
    t0 = time.perf_counter()
    by_id = products_by_id()
    user_texts = [m["content"] for m in messages if m["role"] == "user"]
    cons = merged_constraints(user_texts)

    texts = retrieval_texts(user_texts)
    vecs = None
    mode = "keyword"
    if embed_fn is not None:
        try:
            vecs = embed_fn([pipeline.parse_constraints(t)["clean_query"].strip().lower() for t in texts])
            mode = pipeline.LIVE_MODE
        except Exception:
            vecs = None
    candidates, searches = [], []
    for i, t in enumerate(texts):
        res = pipeline.run(t, mode=mode, query_vec=vecs[i] if vecs else None,
                           context=context, k=k_each, params=params, constraints=cons)
        searches.append(res)
        for p in res["results"]:
            if p["product_id"] not in candidates:
                candidates.append(p["product_id"])
    search_no_match = searches[0]["no_close_match"]

    diag = {"mode": mode, "candidates": candidates, "dropped_ids": [], "claim_flags": {},
            "tokens_in": 0, "tokens_out": 0, "fallback": None}
    picks, reply, no_match = [], "", False
    try:
        if llm is None:
            raise RuntimeError("chat model not configured")
        data, usage = llm.chat_json(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": build_user_prompt(messages, cons, context, candidates)}],
            task="chat_turn", max_tokens=900, attempts=1 if live else 6)
        diag["tokens_in"], diag["tokens_out"] = usage["in"], usage["out"]
        reply = str(data.get("reply", "")).strip()
        no_match = bool(data.get("no_match", False))
        for pk in (data.get("picks") or [])[:3]:
            pid = str(pk.get("id", "")).strip()
            if pid not in candidates:            # grounding check: never show a product search didn't find
                diag["dropped_ids"].append(pid)
                continue
            p = by_id[pid]
            if not pipeline.satisfies(p, cons):   # limits re-checked in code
                diag["dropped_ids"].append(pid)
                continue
            why = str(pk.get("why", "")).strip()
            flags = unsupported_claims(why, p)
            if flags:
                diag["claim_flags"][pid] = flags
            picks.append({**p, "why": why})
    except Exception as e:
        diag["fallback"] = f"assistant unavailable ({type(e).__name__})"
        picks = [{**by_id[pid], "why": ""} for pid in candidates[:3]]
        no_match = search_no_match
        reply = ("The assistant is unavailable right now, so here are the closest search results."
                 if picks else "The assistant is unavailable right now, and search found nothing that fits.")
    if not picks and not no_match:
        no_match = True
    diag["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return {"reply": reply, "products": picks, "no_match": no_match,
            "constraints": cons, "search_no_close_match": search_no_match, "diagnostics": diag}
