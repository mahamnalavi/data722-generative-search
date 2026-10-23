"""Load the synthetic product catalogue.

The same code runs in the live app (Vercel) and in the Colab notebook, so
evaluation scores describe the system that is actually deployed.
"""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def load_catalogue() -> list[dict]:
    """Return all products as a list of dicts (loaded once, then cached)."""
    with open(DATA_DIR / "catalogue.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def products_by_id() -> dict[str, dict]:
    return {p["product_id"]: p for p in load_catalogue()}


def product_text(p: dict) -> str:
    """The text a keyword search can see: what a normal store search indexes."""
    return " ".join([p["title"], p["brand"], p["category"], p["subcategory"], p["description"]])
