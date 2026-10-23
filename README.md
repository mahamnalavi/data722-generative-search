# Sahulat Home: Generative Search (DATA722 mid-term, Phase 2)

A demo online store for household goods (a fictional Pakistani store, all data synthetic). Shoppers describe **what they need it for** in plain English, Urdu or Roman Urdu, and the search finds matching products. It uses the category page the shopper is on and what they browsed earlier in the same visit.

> All products, brands, prices and stock levels are invented. No real customer or company data is used.

## Folder guide
| Folder | What is in it |
|---|---|
| `data/` | Synthetic catalogue (`catalogue.csv` / `.json`) and the script that builds it |
| `docs/DECISIONS.md` | Decisions log: what we tried, chose and rejected, and why |
| `docs/STATUS.md` | Current project status and next steps |
| `app/` | The website and search API (FastAPI), deployed on Vercel *(coming next)* |
| `notebook/` | Google Colab notebook: definitions, embeddings, evaluation *(coming next)* |
