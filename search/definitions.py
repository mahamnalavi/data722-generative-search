"""Semantic definitions: the AI-written, utility-focused text each product is searched by.

This is the instructor's key suggestion. The catalogue says what a product IS
(material, size, pieces). The definition says what it is FOR, in the words a
shopper would use, including common Urdu and Roman Urdu names.

Two prompt versions are kept, as evidence of development:
  v1: a simple first attempt
  v2: adds grounding rules after checking v1's output for unsupported claims
      (claims a seller cannot back up are a deceptive-marketing risk under the
      CCP's 2023 guidelines on Section 10 of the Competition Act 2010)
"""

import json
import re

PROMPT_V1 = """You write short descriptions for an online household-goods store in Pakistan.
For each product below, describe what it is and what people use it for.

Return JSON: {"items": [{"product_id": "...", "definition": "..."}]}

Products:
{products}"""

PROMPT_V2 = """You write search definitions for an online household-goods store in Pakistan.
A shopper may not know a product's name, so they describe the job they need done.
For each product, write what it is FOR, in plain everyday words.

Rules:
1. Use only the facts given (title, category, specs). Do not add features, materials,
   certifications, safety, health or durability claims that are not in the facts.
2. Uses must follow directly from what the product is. No marketing words
   ("best", "premium", "perfect", "must-have").
3. Include phrases a shopper might type, in English, and common Urdu or Roman Urdu
   names only if you are confident they are used in Pakistan (otherwise leave the list empty).
4. Keep each field short.

Return JSON exactly in this shape:
{"items": [{"product_id": "...",
            "what_it_is": "one sentence",
            "used_for": ["2-4 short uses"],
            "shopper_phrases": ["3-5 things a shopper might type"],
            "local_names": ["0-3 Urdu or Roman Urdu names"]}]}

Products:
{products}"""


def product_facts(p: dict) -> str:
    """The facts we give the model: nothing beyond what is in the catalogue."""
    specs = "; ".join(f"{k}: {v}" for k, v in p["attributes"].items())
    return f'- product_id: {p["product_id"]} | title: {p["title"]} | category: {p["category"]} > {p["subcategory"]} | specs: {specs}'


def build_prompt(version: str, products: list[dict]) -> str:
    template = PROMPT_V1 if version == "v1" else PROMPT_V2
    return template.replace("{products}", "\n".join(product_facts(p) for p in products))


def definition_text(d: dict) -> str:
    """Flatten a definition into the single text that gets embedded and searched."""
    if "definition" in d:                      # v1 format
        return d["definition"]
    parts = [d.get("what_it_is", "")]
    if d.get("used_for"):
        parts.append("Used for: " + "; ".join(d["used_for"]) + ".")
    if d.get("shopper_phrases"):
        parts.append("Shoppers say: " + "; ".join(d["shopper_phrases"]) + ".")
    if d.get("local_names"):
        parts.append("Also called: " + ", ".join(d["local_names"]) + ".")
    return " ".join(x for x in parts if x).strip()


# ---- automatic check for claims the catalogue does not support ----
# Words that signal a claim needing evidence. A hit is only a flag if the
# product's own facts do not contain the same word.
CLAIM_WORDS = [
    "dishwasher", "microwave", "oven-safe", "oven safe", "induction", "bpa", "non-toxic", "food-grade",
    "food grade", "rust", "waterproof", "warranty", "guarantee", "durable", "long-lasting", "lifetime",
    "unbreakable", "eco", "safe for", "healthy", "hygienic", "antibacterial", "premium", "best",
    "perfect", "high-quality", "high quality", "must-have", "professional", "heavy-duty", "heavy duty",
]


def unsupported_claims(defn_text: str, p: dict) -> list[str]:
    """Return claim words in the definition that do not appear in the product's facts."""
    facts = (p["title"] + " " + json.dumps(p["attributes"]) + " " + p["description"]).lower()
    text = defn_text.lower()
    return [w for w in CLAIM_WORDS if re.search(r"\b" + re.escape(w) + r"\b", text) and w not in facts]
