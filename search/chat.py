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

Fixes after the first Notebook 03 run (31 Oct; decision 37). The first run showed that a rule in the prompt
is not enough on its own, so each of these is now enforced or set in code:
  - reply language: detected from the shopper's message by rules and stated in the message to the model
    (the first run answered English questions in Roman Urdu); one retry if the reply comes back in another language
  - conversation memory: a follow-up with no product words of its own ("only ones in stock please") is searched
    together with the last message that named a need, not just the message before it (the first run lost "rotis")
  - marketing words ("perfect", "ideal", "best") are replaced in what the shopper sees (7 answers used "perfect")
  - product codes ("TOL-027") are replaced by the product's name in the reply

The prompt below is the "context design" at the centre of the chat: what the model sees,
in what order, and the rules it must follow.
"""

import json
import re
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
2. Pick at most 3, best first. Pick a candidate only if its facts or uses show it does what the shopper asked; fewer picks are better than a weak one. For each, give one short reason that follows from its listed facts or uses.
3. Candidates already meet the stated budget and stock limits. If the shopper asks for cheaper, prefer lower prices.
4. If no candidate does what the shopper needs, set "no_match" to true, say so plainly, and suggest different words to search. Never force a product.
5. Write the reply and every reason in the REPLY LANGUAGE given in the message.
6. PAGE and VISIT are soft hints for unclear requests only. The shopper's own words always win.
7. Keep "reply" under 60 words. No marketing words such as "perfect", "ideal", "best", "premium". Refer to products by name, never by id.

Return JSON only: {"reply": "...", "picks": [{"id": "...", "why": "..."}], "no_match": false}"""


@lru_cache(maxsize=1)
def _uses() -> dict:
    path = DATA_DIR / "definitions_v2.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8")).get("items", {})
    return {pid: d.get("used_for") or [] for pid, d in items.items() if not d.get("fallback")}


# ---- reply language, set by rules (not left to the model) ----
URDU_SCRIPT = re.compile(r"[\u0600-\u06FF]")
ROMAN_URDU = {
    "hai", "hain", "ho", "ka", "ki", "ke", "ko", "se", "mein", "main", "par", "aur", "ya", "nahi", "nahin", "na",
    "kya", "kaise", "kahan", "kyun", "liye", "chahiye", "chahye", "wala", "wali", "wale", "walay", "kuch", "koi",
    "bhi", "tak", "jaye", "jata", "jati", "karne", "karna", "karta", "karti", "kar", "rakhne", "rakhna", "sasta",
    "sasti", "saste", "mehnga", "acha", "achha", "accha", "zyada", "kam", "dikhao", "batao", "mujhe", "mera",
    "meri", "mere", "hum", "aap", "ap", "yeh", "ye", "woh", "wo", "is", "us", "isay", "jo", "ab", "abhi",
    "ghar", "barik", "katne", "alag", "banane", "banana", "lagane", "chali", "roshni", "jootay", "joote",
    "kapre", "kapray", "bartan", "pani", "khana", "dhone", "saaf", "rakhein", "chahiay", "sath", "saath",
    "liay", "lye", "wastay", "waste", "tha", "thi", "hoga", "hogi", "agar", "phir", "lekin", "magar",
}
_AMBIGUOUS_RU = {"is", "us", "ya", "na", "main", "par", "jo", "ab", "kam", "wo", "ho", "ye"}   # also English words
_ENGLISH_HINTS = {"the", "a", "an", "for", "to", "my", "is", "it", "and", "of", "with", "i", "need", "want", "how"}
LANGUAGE_NAMES = {"english": "English", "roman_urdu": "Roman Urdu (Urdu in Latin letters, like 'Aap ke liye ye behtar hai')",
                  "urdu_script": "Urdu, in Urdu script"}


def detect_language(text: str) -> str:
    """'urdu_script', 'roman_urdu' or 'english', by simple word rules."""
    if URDU_SCRIPT.search(text or ""):
        return "urdu_script"
    words = re.findall(r"[a-z]+", (text or "").lower())
    ru = sum(w in ROMAN_URDU for w in words)
    ru_strict = sum(w in ROMAN_URDU and w not in _AMBIGUOUS_RU for w in words)
    en = sum(w in _ENGLISH_HINTS for w in words)
    if ru_strict >= 2 or (ru_strict >= 1 and ru >= 2 and en == 0) or (len(words) <= 3 and ru_strict >= 1 and en == 0):
        return "roman_urdu"
    return "english"


# ---- conversation memory ----
# Words that carry no product meaning in a follow-up ("only ones in stock please", "is se sasta wala?").
FOLLOW_UP_WORDS = {
    "only", "one", "ones", "please", "pls", "any", "anything", "other", "another", "more", "less", "also", "else",
    "cheaper", "cheap", "cheapest", "lower", "price", "budget", "show", "give", "them", "those", "these", "there",
    "ok", "okay", "yes", "no", "thanks", "thank", "same", "similar", "option", "options", "instead", "available",
    "under", "below", "within", "rs", "pkr", "stock", "much", "too", "expensive", "costly", "bigger", "smaller",
    "sasta", "sasti", "saste", "wala", "wali", "wale", "se", "koi", "aur", "dikhao", "chahiye", "bhi", "kam", "ka",
    "ki", "ke", "hai", "kya", "ye", "yeh", "woh", "wo", "us", "isay",
}


def content_words(text: str) -> list[str]:
    from .keyword import tokenize
    return [w for w in tokenize(pipeline.parse_constraints(text)["clean_query"]) if w not in FOLLOW_UP_WORDS]


def merged_constraints(user_texts: list[str]) -> dict:
    out = {"max_price": None, "in_stock": False}
    for t in user_texts:
        c = pipeline.parse_constraints(t)
        if c["max_price"] is not None:
            out["max_price"] = c["max_price"]
        out["in_stock"] = out["in_stock"] or c["in_stock"]
    return out


def retrieval_texts(user_texts: list[str]) -> list[str]:
    """Texts to search for. A follow-up with fewer than 2 product words of its own ("only ones in stock please",
    "is se sasta wala?") is searched together with the TOPIC: the last earlier message that named a need with
    at least 2 product words. A message with its own product words is searched on its own and joined with
    the topic, so both a refinement ("in steel?") and a new topic ("now I need a ladder") find candidates.
    (Before 31 Oct only the previous message was used, so a topic two messages back was lost.)"""
    latest = user_texts[-1]
    if len(user_texts) == 1:
        return [latest]
    earlier = user_texts[:-1]
    topic = next((t for t in reversed(earlier) if len(content_words(t)) >= 2), earlier[0])
    joined = topic + " " + latest
    return [latest, joined] if len(content_words(latest)) >= 2 else [joined]


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


def build_user_prompt(messages, cons, context, candidates, language=None) -> str:
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
            f"REPLY LANGUAGE: {LANGUAGE_NAMES[language or detect_language(messages[-1]['content'])]}\n"
            f"LIMITS: {', '.join(limits) or 'none stated'}\n"
            f"{describe_context(context)}\n\n"
            f"CANDIDATES:\n" + ("\n".join(lines) or "(none: nothing in the catalogue matched)"))


# ---- what the shopper sees: no marketing words, no product codes ----
MARKETING = [(r"\bthe best\b", "the most suitable"), (r"\bbest\b", "good"), (r"\bperfect\b", "right"),
             (r"\bperfectly\b", "well"), (r"\bideal\b", "suitable"), (r"\bpremium\b", "")]


def clean_text(text: str, by_id: dict, candidates: list[str]) -> tuple[str, list[str]]:
    """Replace marketing words and product codes in text shown to the shopper. Returns (text, what was changed)."""
    changed = []
    for pat, rep in MARKETING:
        if re.search(pat, text, flags=re.I):
            changed.append(re.search(pat, text, flags=re.I).group(0).lower())
            text = re.sub(pat, rep, text, flags=re.I)
    for pid in set(re.findall(r"\b[A-Z]{3}-\d{3}\b", text)):
        if pid in by_id:
            changed.append(pid)
            text = text.replace(pid, by_id[pid]["title"])
    return re.sub(r"\s{2,}", " ", text).strip(), changed


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

    language = detect_language(user_texts[-1])
    diag = {"mode": mode, "candidates": candidates, "dropped_ids": [], "claim_flags": {}, "cleaned": [],
            "language": language, "language_retry": False, "tokens_in": 0, "tokens_out": 0, "fallback": None}
    picks, reply, no_match = [], "", False
    try:
        if llm is None:
            raise RuntimeError("chat model not configured")
        prompt = [{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": build_user_prompt(messages, cons, context, candidates, language)}]
        data, usage = llm.chat_json(prompt, task="chat_turn", max_tokens=900, attempts=1 if live else 6)
        diag["tokens_in"], diag["tokens_out"] = usage["in"], usage["out"]
        got = detect_language(str(data.get("reply", "")))
        if got != language and not (language == "roman_urdu" and got == "english"):
            # one retry when the reply came back in another language (English asked, Roman Urdu answered, etc.)
            diag["language_retry"] = True
            prompt[1]["content"] += f"\n\nYour previous reply was not in {LANGUAGE_NAMES[language]}. Write it in {LANGUAGE_NAMES[language]}."
            data, usage = llm.chat_json(prompt, task="chat_turn", max_tokens=900, attempts=1 if live else 6)
            diag["tokens_in"] += usage["in"]; diag["tokens_out"] += usage["out"]
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
                diag["claim_flags"][pid] = flags        # recorded as written by the model (evidence)
            why, changed = clean_text(why, by_id, candidates)
            diag["cleaned"] += changed
            picks.append({**p, "why": why})
        reply, changed = clean_text(reply, by_id, candidates)
        diag["cleaned"] += changed
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
