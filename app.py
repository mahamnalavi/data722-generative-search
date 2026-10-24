"""Sahulat Home demo store: web app + search API (FastAPI).

Vercel finds the FastAPI object named `app` in this file and runs it as a
serverless function. The website files (HTML/CSS/JS) live in static/.

API endpoints (the "API" concept in this project):
  GET  /api/health     -> is the app up, which search is active, how many products
  GET  /api/catalogue  -> all products (the website draws its pages from this)
  POST /api/search     -> run a search; body: {"query": "...", "mode": "hybrid", "context": {...}}

Secrets (set in Vercel > Settings > Environment Variables, never in code):
  GEMINI_API_KEY  -> meaning-based search (without it, the site falls back to keyword search)
"""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import search as engine
from search.pipeline import MODES

ROOT = Path(__file__).resolve().parent

# Show the AI "What it's for" box on product pages. Switched on only after the
# student's hand-check of definition accuracy (Notebook 01, section 5).
SHOW_WHAT_ITS_FOR = False

app = FastAPI(title="Sahulat Home search API", version=engine.VERSION)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    mode: str = "hybrid"
    context: dict | None = None   # category page + this-visit summary (used from v2)
    k: int = Field(12, ge=1, le=24)


@lru_cache(maxsize=1)
def _definitions() -> dict:
    path = ROOT / "data" / "definitions_v2.json"
    if not SHOW_WHAT_ITS_FOR or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("items", {})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": engine.VERSION, "products": len(engine.load_catalogue()),
            "meaning_search": "on" if engine.semantic_ready() else "off (keyword fallback)"}


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
    if req.mode not in MODES:
        raise HTTPException(status_code=400, detail=f"mode must be one of {MODES}")
    return engine.search(req.query, mode=req.mode, context=req.context, k=req.k)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
