"""Sahulat Home catalogue search as an MCP server.

MCP (Model Context Protocol) is an open standard that lets AI assistants (Claude, ChatGPT,
coding tools) call outside tools and data through one common interface. This server
exposes the store's search as two tools:

  search_products(query, max_price, in_stock, page_category, limit)
  get_product(product_id)

Why it is here: an assistant connected to this server can answer shopping questions from
the store's real catalogue, using the same meaning search, budget/stock filters and
"no close match" decision as the website, instead of guessing from its training data.
The live website does NOT use MCP; its chat calls the search directly as a fixed pipeline
(decision 3). MCP is the integration layer for other assistants.

Run:  python mcp_server.py   (talks MCP over stdin/stdout; set GEMINI_API_KEY for meaning-based search,
      otherwise it falls back to keyword search and says so)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x)

import search  # noqa: E402
from search import chat as _chat  # noqa: E402
from search.catalogue import products_by_id  # noqa: E402

server = MCPServer(
    name="sahulat-home",
    instructions=("Search the Sahulat Home demo catalogue (a fictional Pakistani household-goods store; all data "
                  "synthetic). Use search_products for product names or needs described in plain words, in English, "
                  "Urdu or Roman Urdu. Budget is in Pakistani rupees. Recommend only products the tools return."),
)


def _brief(p: dict) -> dict:
    return {"id": p["product_id"], "title": p["title"], "price_pkr": p["price_pkr"], "in_stock": p["in_stock"],
            "category": p["category"], "uses": _chat._uses().get(p["product_id"], [])}


@server.tool()
def search_products(query: str, max_price: int | None = None, in_stock: bool = False,
                    page_category: str | None = None, limit: int = 5) -> dict:
    """Find products by name or by what the shopper needs them for.
    max_price (PKR) and in_stock are applied strictly. page_category (Kitchenware, Tools, Organizers,
    Furniture) is an optional soft hint. Returns results, plus no_close_match=true when nothing fits well."""
    res = search.search(query, k=max(1, min(limit, 10)),
                        context={"page_category": page_category} if page_category else None,
                        constraints={"max_price": max_price, "in_stock": in_stock})
    return {"results": [_brief(p) for p in res["results"]], "no_close_match": res["no_close_match"],
            "search_mode": res["mode"], "note": res["fallback"] or "",
            "limits_applied": {"max_price": res["constraints"]["max_price"], "in_stock": res["constraints"]["in_stock"]}}


@server.tool()
def get_product(product_id: str) -> dict:
    """Full details for one product id returned by search_products."""
    p = products_by_id().get(product_id)
    if not p:
        return {"error": f"No product with id {product_id}"}
    return {**_brief(p), "brand": p["brand"], "subcategory": p["subcategory"], "stock_qty": p["stock_qty"],
            "specs": p["attributes"]}


if __name__ == "__main__":
    server.run("stdio")
