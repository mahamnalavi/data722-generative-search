# Project status: DATA722 Generative Search

Due: **31 Oct 2026, 11:59 PM**. Last updated: 30 Oct (evening).

Step-by-step run instructions (kept outside the notebooks): the "Sahulat Home: run guide" doc, https://claude.ai/artifact/JfYv6EP9mMduLXfMyUf4Az

## Working rules (from the student)
- Don't assume; ask. One task per message, each with a "done when" check.
- Notebooks stay in the student's voice; run instructions live in the run guide, not the notebooks.
- Verify claims; flag schedule slips early; no cuts unless something is certainly impossible to build.
- API keys only in Colab secrets and Vercel, never in chat. No real confidential data.
- **Do not merge the notebooks without asking the student first** (30 Oct).
- Observations: Claude drafts, the student reviews and picks. Don't edit the AI-use section of the notebooks.

## Done
- Phase 1 reviewed; Phase 2 plan agreed; decisions log kept (`docs/DECISIONS.md`, 33 decisions)
- Synthetic catalogue: 195 products, 4 categories, 144 types, 49 multi-variant, 22 out of stock
- Evaluation set: 114 labelled queries (35 dev / 79 test)
- Website live at sahulat-home.vercel.app: storefront, search bar, "Ask Sahulat" chat, This-visit panel, illustrations
- Notebooks 02, 03, 04 and the MCP server written and test-run offline
- **Notebook 01 run by the student** (30 Oct): v1 vs v2 prompts, 195 definitions, corrected claim check (1 flag), hand-check 10 Y / 10 P / 0 N, embeddings, cost about $0.023 at paid prices. Revised intro and section 5 note committed (6ac6804).
- "What it's for" box switched on (uses only, never local names)
- Chat uses this visit's earlier searches as a soft hint (decision 33)

## In progress / waiting (student)
- [ ] Add GEMINI_API_KEY and GROQ_API_KEY in Vercel, redeploy; /api/health should show both "on" (30 Oct: both off)
- [ ] Test the live site: Roman Urdu search, budget search, "What it's for" box, chat follow-up
- [ ] Check the public address in a private window (Deployment Protection off)
- [ ] Run Notebook 02 (about 20 min); send section 6 table, sections 8/9 outputs, the downloaded file

## Next
- Claude: copy tuned "live" params into `data/live_params.json`; draft NB02 observations
- 31 Oct morning: Notebook 03 (fresh Groq quota), hand-check of 16 judge verdicts; Notebook 04 (MCP)
- Ask the student, then build the single submission notebook (outputs preserved, results summary up front)
- Honesty page (madhani "hand-crank", unreliable local names, synthetic sessions, free-tier limits, the author also wrote the parser and queries, cost)
- Video script (5 min max), viva notes, clean-browser test, final link check, submit

## Phase 1 metrics that must appear in the evaluation
1. Keyword-search miss rate (the problem measure)
2. Definition accuracy (hand-audited sample): **done, strict 50% / lenient 100% / 0 wrong**
3. Constraint violations (budget, stock)
4. Correct "no close match" rate on out-of-catalogue queries
5. Confidently-wrong rate, including unsupported claims in explanations
6. Context-override errors (context pushing a correct result out of the top results)
7. Cost and latency per query
Plus Hit@1/5/10 across the ladder: keyword, then embeddings on titles, then definitions, then context.
