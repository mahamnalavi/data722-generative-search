"""Sahulat Home demo store: web app + search API (FastAPI).

Vercel finds the FastAPI object named `app` in this file and runs it as a
serverless function. The website files (HTML/CSS/JS) live in static/.

API endpoints (the "API" concept in this project):
  GET  /api/health     -> is the app up, which search is active, how many products
  GET  /api/catalogue  -> all products (the website draws its pages from this)
  POST /api/search     -> run a search; body: {"query": "...", "context": {...}} (optional "mode"; default: meaning search on the AI definitions)
  POST /api/chat       -> one "Ask Sahulat" turn; body: {"messages": [{"role": "user", "content": "..."}], "context": {...}}

Secrets (set in Vercel > Settings > Environment Variables, never in code):
  GEMINI_API_KEY  -> meaning-based search (without it, the site falls back to keyword search)
  GROQ_API_KEY    -> the chat assistant (without it, the chat shows plain search results)
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import search as engine
from search import chat as chat_engine
from search.pipeline import MODES

ROOT = Path(__file__).resolve().parent

# Show the AI "What it's for" box on product pages. Switched on only after the
# student's hand-check of definition accuracy (Notebook 01, section 5).
SHOW_WHAT_ITS_FOR = True   # switched on 30 Oct: hand-check 10 Y, 10 P, 0 N; the box shows uses only, never local names

app = FastAPI(title="Sahulat Home search API", version=engine.VERSION)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    mode: str | None = None   # default: pipeline.LIVE_MODE (meaning search on the AI definitions)
    context: dict | None = None   # category page + this-visit summary (used from v2)
    k: int = Field(12, ge=1, le=24)


class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., min_length=1, max_length=12)
    context: dict | None = None


@lru_cache(maxsize=1)
def _chat_llm():
    if not os.environ.get("GROQ_API_KEY"):
        return None
    from search.llm import GroqChat
    # No local pacing on the live site (each server instance would pace alone); fail fast instead
    # and show search results, so a shopper never waits on a rate limit.
    return GroqChat(tokens_per_min=10**9)


@lru_cache(maxsize=1)
def _definitions() -> dict:
    path = ROOT / "data" / "definitions_v2.json"
    if not SHOW_WHAT_ITS_FOR or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("items", {})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": engine.VERSION, "products": len(engine.load_catalogue()),
            "meaning_search": "on" if engine.semantic_ready() else "off (keyword fallback)",
            "chat_assistant": "on" if os.environ.get("GROQ_API_KEY") else "off (search results only)"}


@app.get("/api/catalogue")
def catalogue():
    defs = _definitions()
    out = []
    for p in engine.load_catalogue():
        d = defs.get(p["product_id"])
        out.append({**p, "what_its_for": d.get("used_for") if d and not d.get("fallback") else None})
    return out


@app.post("/api/search")
def run_search(req: SearchRequest):
    if req.mode is not None and req.mode not in MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {MODES}")
    return engine.search(req.query, mode=req.mode, context=req.context, k=req.k)


@app.post("/api/chat")
def run_chat(req: ChatRequest):
    msgs = [{"role": m.get("role"), "content": str(m.get("content", ""))[:300]}
            for m in req.messages if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()][-6:]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="the last message must be from the shopper")
    embed_fn = (lambda texts: [list(engine.embed_query(t)) for t in texts]) if engine.semantic_ready() else None
    return chat_engine.respond(msgs, context=req.context, embed_fn=embed_fn, llm=_chat_llm(), live=True)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
