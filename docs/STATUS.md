# Project status: DATA722 Generative Search

Due: **31 Oct 2026**. Last updated: 24 Oct.

## Done
- Phase 1 reviewed; Phase 2 plan agreed
- GitHub repo created: `mahamnalavi/data722-generative-search`
- Synthetic catalogue v1: 195 products (`data/catalogue.csv`, `data/catalogue.json`)
- GitHub linked; Claude can push to the repo
- AI providers chosen: Groq (chat) + Gemini (embeddings, judge), OpenAI as backup
- Keys tested in Colab: Groq gpt-oss-120b OK; Gemini embeddings OK (gemini-embedding-001, 3072 dims; gemini-embedding-2 also available)
- Website v0 live on Vercel (/api/health OK, 195 products)
- Groq limits verified (decision 13)
- Notebook 01 (definitions and embeddings) written and test-run offline
- Website v1: regular storefront, hybrid search with safe keyword fallback, illustrations, "What it's for" box (off until the hand-check)

## In progress / waiting
- [ ] Find the permanent public web address and check it in a private window (student, Task 4b)
- [ ] Create a GitHub token; run Notebook 01 (student, Task 5)

## Next (Claude)
- Evaluation query set (~100), with a 30/70 dev/test split
- Turn on meaning-based search on the live site (needs Notebook 01 outputs and GEMINI_API_KEY in Vercel)
- Notebook 02: evaluation ladder on the dev split

## Phase 1 metrics that must appear in the evaluation
1. Keyword-search miss rate (the problem measure)
2. Definition accuracy (hand-audited sample)
3. Constraint violations (budget, stock)
4. Correct "no close match" rate on out-of-catalogue queries
5. Confidently-wrong rate, including unsupported claims in explanations
6. Context-override errors (context pushing a correct result out of the top results)
7. Cost and latency per query
Plus Hit@1/5/10 across the ladder: keyword, then embeddings on titles, then definitions, then context.
