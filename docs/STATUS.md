# Project status: DATA722 Generative Search

Due: **31 Oct 2026**. Last updated: 24 Oct.

## Done
- Phase 1 reviewed; Phase 2 plan agreed
- GitHub repo created: `mahamnalavi/data722-generative-search`
- Synthetic catalogue v1: 195 products (`data/catalogue.csv`, `data/catalogue.json`)
- GitHub linked; Claude can push to the repo
- AI providers chosen: Groq (chat) + Gemini (embeddings, judge), OpenAI as backup
- Keys tested in Colab: Groq gpt-oss-120b OK; Gemini embeddings OK (gemini-embedding-001, 3072 dims; gemini-embedding-2 also available)
- Website v0 built and tested locally: store pages, keyword (BM25) search, This-visit panel

## In progress / waiting
- [ ] Deploy v0 to Vercel (student, Task 4)
- [ ] Screenshot of Groq organization limits (student, optional)

## Next (Claude)
- Evaluation query set (~100), with a 30/70 dev/test split
- Colab notebook part 1: load catalogue, audit, generate definitions, embeddings

## Phase 1 metrics that must appear in the evaluation
1. Keyword-search miss rate (the problem measure)
2. Definition accuracy (hand-audited sample)
3. Constraint violations (budget, stock)
4. Correct "no close match" rate on out-of-catalogue queries
5. Confidently-wrong rate, including unsupported claims in explanations
6. Context-override errors (context pushing a correct result out of the top results)
7. Cost and latency per query
Plus Hit@1/5/10 across the ladder: keyword, then embeddings on titles, then definitions, then context.
