# MODELS-1: Remove the China-provider ban; add DeepSeek and Kimi to the roster

> Written 18 Oct 2026, 21:25 PT. **Founder decision:** the ban on China-hosted providers is removed. DeepSeek and Moonshot (Kimi) may be used like any other provider. This overrides every earlier brief and code comment that says "no China-hosted providers".

**Files you may change:** `tank/main.py` (remove `_CHINA_PROVIDERS` and `_china_model` and every check that uses them; nothing else in this file), `litellm/config.yaml` and `litellm/config.za.yaml` (add the models, remove the "deliberately absent" comments), `tank/schema.sql` (policy rows only, additive, `ON CONFLICT DO NOTHING`), `docker-compose.za.yml` (add `DEEPSEEK_API_KEY` and `MOONSHOT_API_KEY` to the LiteLLM service environment, same as Boston), `.env.example` (names only), `tests/test_model_roster.py`, `tests/test_za_region.py`, new tests.

## Do
1. Remove the China-provider refusal in Tank. DeepSeek and Moonshot models are treated like OpenAI, Google and xAI: the per-tenant allow-list (`TANK_PROVIDER_ALLOW`) still applies, and the existing South Africa identifier rule (`model_call_refusal`, `IDENTIFIER_REFUSAL`) is unchanged.
2. Add to both LiteLLM rosters, with prices from each provider's own pricing page on the day you build (USD per token, page URL and date in a comment): DeepSeek's current chat and reasoning models, and Moonshot's current Kimi model. Keys come from `DEEPSEEK_API_KEY` and `MOONSHOT_API_KEY`. A provider with no key or no funds is skipped automatically, as today.
3. Put the cheapest one that fits on the ladder as a candidate rung for batch work (Zenas self-test, Market Lab research, Base enrichment). It only takes over a task after it matches on held-out cases (existing graduation rule). No task changes route on merge.
4. Tests: replace the "no China provider" tests with ones that prove DeepSeek and Kimi are in both rosters, that the allow-list still restricts them, and that the SA identifier rule still applies to them exactly as it does to other non-SA providers.

## Done when
CI green; both rosters list the new models with sourced prices; the old ban tests are gone and the new ones pass; no route changes until graduation.

## Founder
Add `DEEPSEEK_API_KEY` and `MOONSHOT_API_KEY` in Coolify (Boston main app and the ZA stack) when you want them live.
