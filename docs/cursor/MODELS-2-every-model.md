# MODELS-2: every available model on the roster, including DeepSeek, Kimi and Perplexity

> Written 20 Oct 2026. Founder: "linked with every available model. I want Kimi and DeepSeek included, I want Perplexity included."
>
> MODELS-1 (#154, branch `models-1-deepseek-kimi`) removed the China-provider ban and began adding DeepSeek and Kimi, but its CI is failing. **Take over that branch and PR**: merge `main` in without force-pushing, finish it, and add everything below. Read `docs/cursor/MODELS-1-add-deepseek-kimi.md` first; it still applies.

**Files you may change:** everything MODELS-1 allows, plus `agents/market_lab/` (research adapter only), `.env.example` (names only), tests.

1. **The roster on both boxes** (`litellm/config.yaml`, `litellm/config.za.yaml`).
   - Add:
     - **DeepSeek:** current chat and reasoning models;
     - **Moonshot Kimi:** current model;
     - **Perplexity:** Sonar models (search-grounded answers with citations);
     - any current flagship or cheap model from the existing providers (OpenAI, Anthropic, Google, xAI) that is not yet listed.
   - Each model gets a Tervory name and its **price from the provider's own pricing page on the build day**, with the URL and date in a comment.
   - Set fallbacks for the new models.
2. **Keys:** `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY` and `PERPLEXITY_API_KEY`, passed to LiteLLM on both boxes. A provider with no key or no funds is skipped automatically, as today.
3. **Perplexity is a research model, not a general one.**
   - Its answers carry its citations through to Tank's receipt.
   - Market Lab's research step may use it as a rung, after code lookups and before any general model.
   - Search calls have a per-request fee on top of tokens. Record that fee in `tank.price_book` and on the ledger, so it is never hidden in the receipt.
4. **No task changes route on merge.** New models enter the CORE-1 bench and shadow testing like any other, and the founder promotes. The per-tenant provider allow-list (`TANK_PROVIDER_ALLOW`) still applies, so a tenant can exclude providers.
5. **Visible:** after deploy, all new models show on the Tank page with prices (#210).

## Done when
CI green. Tests:
- every new model is in both rosters with a sourced price;
- the allow-list restricts them;
- Perplexity's citations and search fee reach the ledger and receipt;
- no policy row changes.
