# Market Lab web research through GPT-Researcher — implementation checkpoint

Branch: `codex/market-lab-gpt-researcher`; main base `bde4578`.
Claude opens the draft PR. This task uses git only, no GitHub API.

The existing room job calls Perplexity's gated `/v1/research`; the client `/market/ask` only searches stored sources. This change will use GPT-Researcher 0.16.1 (MIT), over the deployed SearXNG, after the saved-source lookup. Perplexity's code remains intact.

Integration uses GPT-Researcher's actual orchestration, SearXNG retriever and page-text extraction. Its OpenAI-compatible model transport points only to a local adapter that calls Tank `/v1/route` with the existing Market Lab room key and request tenant. No provider/model key is added. Context selection uses code, without embeddings or verifier model calls. Sources must come from SearXNG results, be fetched successfully and have recorded fetch times; the returned claims are validated in code before being rendered in the existing cited-answer format.

The service will be internal only, with no published host port or public UI. Each request gets its own researcher and transport context; no shared research history or cross-tenant cache. Tank continues to own policy, ledger, cache and cost limits.

Proof is pending implementation and offline tests with the real pinned package, stubbed search/pages/model, real Tank routing/ledger code, and two tenants. No live model call, deployment, founder screenshot or acceptance is claimed.
