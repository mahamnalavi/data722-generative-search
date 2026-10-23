"""Sahulat Home demo store: web app + search API (FastAPI).

Vercel finds the FastAPI object named `app` in this file and runs it as a
serverless function. The website files (HTML/CSS/JS) live in static/.

API endpoints (the "API" concept in this project):
  GET  /api/health     -> is the app up, how many products are loaded
  GET  /api/catalogue  -> all products (the website draws pages from this)
  POST /api/search     -> run a search; body: {"query": "...", "mode": "keyword", "context": {...}}
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import search as engine

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Sahulat Home search API", version=engine.VERSION)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    mode: str = "keyword"
    context: dict | None = None   # category page + this-visit behaviour (used from v2)
    k: int = Field(10, ge=1, le=20)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": engine.VERSION, "products": len(engine.load_catalogue())}


@app.get("/api/catalogue")
def catalogue():
    return engine.load_catalogue()


@app.post("/api/search")
def run_search(req: SearchRequest):
    try:
        return engine.search(req.query, mode=req.mode, context=req.context, k=req.k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
