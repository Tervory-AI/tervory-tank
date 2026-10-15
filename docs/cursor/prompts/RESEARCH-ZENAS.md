Repo Tervory-AI/tervory-tank. Research only: do not change any code. Read AGENTS.md, docs/cursor/Z-zenas-plan.md, docs/cursor/ZA1-za-region.md, docs/cursor/Z2b-us-law-bulk.md and docs/research/AGENT-TESTS.md (Zenas rows).

Find the best open source and paid options for Zenas, the US + South Africa legal agent (no criminal law). For each option: name, link, what it does for us, licence (commercial use allowed?) or price per month, runs on our own server or not, where the data goes (US / SA / elsewhere).

1. Legal sources. US: statutes, regulations, case law, court rules, state law (bulk download terms). South Africa: legislation, Government Gazette, SAFLII judgments, court rules, Laws.Africa, Juta, LexisNexis SA, and the official government sources. Say exactly what each allows: bulk copy, API, link only.
2. Reasoning and research quality: legal-tuned embedding models and rerankers, citation extractors and citators (good-law checks), retrieval methods for statutes and cases, legal reasoning benchmarks (for example LegalBench) and public legal Q&A sets we can use as tests.
3. Models: which models do legal reasoning best per dollar today; which providers offer models hosted in South Africa (a provider's SA region), and which open-weight models we could run on our own SA server for prompts that contain personal information (state the server size each needs).
4. Drafting and review: open clause libraries and contract datasets (with licences), redline (.docx tracked changes) libraries, court-deadline calculators.
5. Compliance: POPIA cross-border processing requirements for using US model providers; anything that limits storing judgments.

Rules: no China-hosted services; SA personal data stays in SA; no sign-ups, no keys.

End with "Top picks": the one best option per numbered area, cheapest first, and what it would cost per month.

Write it to docs/research/ZENAS-TOOLS.md, plain English, tables. One branch, one PR, never push to main. Do not merge: the founder merges after review (docs/RUNBOOK.md). Write "ready for review" in the PR description.
