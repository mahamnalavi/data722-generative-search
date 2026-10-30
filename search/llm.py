"""Connections to the two AI providers, with usage logging and pacing.

  Groq   -> chat model (writes definitions; later: understands queries, writes replies)
  Gemini -> embeddings ("meaning fingerprints") and, later, the judge

Every call is logged (task, model, tokens, seconds), so the notebook can report
token use and cost for a representative run, as the brief requires.

Free-tier limits (checked 24 Oct 2026 on the student's Groq account):
  openai/gpt-oss-120b: 30 requests/min, 1,000/day, 8,000 tokens/min, 200,000 tokens/day
The per-minute token cap is the tight one, so `GroqChat` paces itself and
waits instead of failing.
"""

import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field

# Published paid prices (USD per 1M tokens), used only to estimate what a real
# deployment would cost. We run on free tiers. Sources and dates in the notebook.
PRICES = {
    "openai/gpt-oss-120b": {"in": 0.15, "out": 0.60},   # Groq; third-party price index, Oct 2026
    "gemini-embedding-001": {"in": 0.15, "out": 0.0},   # Google Developers Blog (GA announcement)
}

GROQ_MODEL = "openai/gpt-oss-120b"
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768          # smaller fingerprints: 4x smaller file, still a Google-recommended size


@dataclass
class UsageLog:
    rows: list = field(default_factory=list)

    def add(self, task, model, tokens_in, tokens_out, seconds, n_items=1):
        self.rows.append({"task": task, "model": model, "tokens_in": tokens_in,
                          "tokens_out": tokens_out, "seconds": round(seconds, 2), "items": n_items})

    def summary(self):
        """Totals per task, plus estimated cost at paid prices."""
        out = {}
        for r in self.rows:
            s = out.setdefault(r["task"], {"model": r["model"], "calls": 0, "items": 0,
                                           "tokens_in": 0, "tokens_out": 0, "seconds": 0.0})
            s["calls"] += 1; s["items"] += r["items"]
            s["tokens_in"] += r["tokens_in"]; s["tokens_out"] += r["tokens_out"]; s["seconds"] += r["seconds"]
        for s in out.values():
            p = PRICES.get(s["model"].replace("models/", ""), {"in": 0, "out": 0})
            s["est_cost_usd"] = round(s["tokens_in"] / 1e6 * p["in"] + s["tokens_out"] / 1e6 * p["out"], 5)
            s["seconds"] = round(s["seconds"], 1)
        return out


USAGE = UsageLog()


def _parse_json(text: str):
    """Models sometimes wrap JSON in prose or code fences; take the first {...} block."""
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text or "", re.S)
        if not m:
            raise ValueError("No JSON found in model reply")
        return json.loads(m.group(0))


class GroqChat:
    """Groq chat model with a rolling 60-second token budget and retry on rate limits."""

    def __init__(self, api_key: str | None = None, model: str = GROQ_MODEL, tokens_per_min: int = 8000):
        from groq import Groq  # imported here so the website does not need it until it uses it
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.model = model
        self.budget = int(tokens_per_min * 0.85)   # keep a safety margin
        self.window = deque()                       # (timestamp, tokens)

    def _wait_for_budget(self, expected_tokens: int):
        while True:
            now = time.time()
            while self.window and now - self.window[0][0] > 60:
                self.window.popleft()
            used = sum(t for _, t in self.window)
            if used + expected_tokens <= self.budget or not self.window:
                return
            time.sleep(max(0.5, 60 - (now - self.window[0][0]) + 0.5))

    def chat(self, messages, task="chat", json_mode=False, max_tokens=1500, effort="low", n_items=1, attempts=6):
        """Send messages, return (text, usage dict). Retries on rate limits (attempts=1: fail fast, used live)."""
        import groq
        expected = int(sum(len(m["content"]) for m in messages) / 3.5) + max_tokens // 3
        for attempt in range(attempts):
            self._wait_for_budget(expected)
            t0 = time.time()
            try:
                kwargs = dict(model=self.model, messages=messages, temperature=0.2,
                              max_completion_tokens=max_tokens, reasoning_effort=effort)
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                r = self.client.chat.completions.create(**kwargs)
            except groq.RateLimitError as e:
                if attempt == attempts - 1:
                    break
                wait = float(getattr(e, "response", None) and e.response.headers.get("retry-after") or 20)
                print(f"  rate limit reached; waiting {wait:.0f}s (attempt {attempt + 1})")
                time.sleep(wait + 1)
                continue
            secs = time.time() - t0
            u = r.usage
            self.window.append((time.time(), u.total_tokens))
            USAGE.add(task, self.model, u.prompt_tokens, u.completion_tokens, secs, n_items)
            return (r.choices[0].message.content or ""), {"in": u.prompt_tokens, "out": u.completion_tokens, "seconds": secs}
        raise RuntimeError(f"Groq rate limit (after {attempts} attempt(s)); try again in a few minutes")

    def chat_json(self, messages, **kw):
        """Ask for JSON. If the model rejects JSON mode, ask again without it and parse the reply."""
        import groq
        try:
            text, usage = self.chat(messages, json_mode=True, **kw)
        except groq.BadRequestError:
            text, usage = self.chat(messages, json_mode=False, **kw)
        return _parse_json(text), usage


class GeminiEmbedder:
    """Gemini embeddings: turns text into a list of numbers that captures its meaning."""

    def __init__(self, api_key: str | None = None, model: str = EMBED_MODEL, dims: int = EMBED_DIMS):
        from google import genai
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model, self.dims = model, dims

    def embed(self, texts: list[str], kind: str = "document", task="embed", batch_size: int = 20,
              retries: int = 6) -> list[list[float]]:
        """kind='document' for products, 'query' for shopper searches (Gemini tunes each differently).
        retries=1 fails fast (the website uses this, then falls back to keyword search)."""
        from google.genai import types
        task_type = "RETRIEVAL_DOCUMENT" if kind == "document" else "RETRIEVAL_QUERY"
        cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dims)
        vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for attempt in range(retries):
                t0 = time.time()
                try:
                    res = self.client.models.embed_content(model=self.model, contents=batch, config=cfg)
                    break
                except Exception as e:
                    if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < retries - 1:
                        print(f"  Gemini rate limit; waiting 30s (attempt {attempt + 1})")
                        time.sleep(30)
                        continue
                    if len(batch) > 1:   # some models accept one text per request: fall back to singles
                        vectors.extend(self.embed(batch, kind=kind, task=task, batch_size=1, retries=retries))
                        res = None
                        break
                    raise
            else:
                raise RuntimeError(f"Gemini kept rate-limiting after {retries} attempts")
            if res is None:
                continue
            secs = time.time() - t0
            est_tokens = sum(len(t) for t in batch) // 4   # Gemini does not return token counts for embeddings
            USAGE.add(task, self.model, est_tokens, 0, secs, len(batch))
            vectors.extend(normalise(e.values) for e in res.embeddings)
        return vectors


def normalise(v):
    """Scale a vector to length 1, so comparing two vectors is a simple dot product."""
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / n for x in v]
