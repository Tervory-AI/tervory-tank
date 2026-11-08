# Maker first-party LiteLLM keys (2026-11-07)

## Env names (LiteLLM only, US + ZA compose)

`MINIMAX_API_KEY`, `ZAI_API_KEY`, `DASHSCOPE_API_KEY`, `STEPFUN_API_KEY`, `ARCEE_API_KEY`, `TINKER_API_KEY`, `SARVAM_API_KEY`

Empty Coolify slots only until filled. No redeploy required by this note.

## Routes added (exact upstream ids; prices checked 2026-11-07)

| Tank model_name | Upstream model | api_base | key | $/1M in→out |
| --- | --- | --- | --- | --- |
| minimax-m3.1-flash-direct | MiniMax-M3.1-Flash | https://api.minimax.io/v1 | MINIMAX_API_KEY | 0.15→0.60 ([pricing](https://platform.minimax.io/docs/guides/pricing)) |
| minimax-m3-direct | MiniMax-M3 | https://api.minimax.io/v1 | MINIMAX_API_KEY | 0.30→1.20 Standard ≤512k 50% off |
| glm-5.3-direct … glm-5.1-direct | glm-5.3, glm-5.2, glm-5.1 | https://api.z.ai/api/paas/v4 | ZAI_API_KEY | 1.4→4.4 ([pricing](https://docs.z.ai/guides/overview/pricing)) |
| glm-5-direct | glm-5 | same | ZAI_API_KEY | 1.0→3.2 |
| glm-4.7-direct / glm-4.6-direct | glm-4.7, glm-4.6 | same | ZAI_API_KEY | 0.6→2.2 |
| qwen3.5-27b-direct | qwen3.5-27b | https://dashscope-intl.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY | 0.3→2.4 Singapore ≤256K ([pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing)) |
| qwen3.5-122b-a10b-direct | qwen3.5-122b-a10b | same | DASHSCOPE_API_KEY | 0.4→3.2 |
| qwen3.5-397b-a17b-direct | qwen3.5-397b-a17b | same | DASHSCOPE_API_KEY | 0.6→3.6 |
| step-3.5-flash-direct | step-3.5-flash | https://api.stepfun.ai/v1 | STEPFUN_API_KEY | 0.10→0.30 ([pricing](https://platform.stepfun.ai/docs/en/pricing/details)) |
| step-3.7-flash-direct | step-3.7-flash | same | STEPFUN_API_KEY | 0.20→1.15 |
| trinity-large-thinking-direct | trinity-large-thinking | https://api.arcee.ai/api/v1 | ARCEE_API_KEY | UNVERIFIED for Tank USD ledger — blog $0.25→$0.80 ([blog](https://www.arcee.ai/blog/open-models-api-beta)); not on [docs pricing](https://docs.arcee.ai/get-started/pricing) as of 2026-11-07; config costs = 0 |
| sarvam-105b-direct | sarvam-105b | https://api.sarvam.ai/v1 | SARVAM_API_KEY (+ `api-subscription-key` header via `extra_headers`) | Official INR ₹15→₹60 /1M ([pricing](https://docs.sarvam.ai/api/pricing)); Tank USD ledger omitted (no invented FX); config costs = 0 |

Existing aliases (`glm`, `glm-small`, `kimi`, `deepseek-*`, HF open-weight seats) are unchanged.

## Unsupported / deferred

**TINKER_API_KEY** is wired in compose only.

- OpenAI-compatible Tinker base `https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1` requires a `tinker://…/sampler_weights/…` checkpoint path as `model`, not a fixed public chat id ([docs](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/)).
- Inkling is served on the **Anthropic** Messages base `https://tinker.thinkingmachines.dev/services/tinker-prod/anthropic/api` as `thinkingmachines/Inkling` ([docs](https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/anthropic/)). No LiteLLM Anthropic route was added in this change (no Tank USD per-token price recorded from an official Tinker pricing table in this pass).

Do not invent a fixed OpenAI model id for Inkling.


## Soft-spot verification (offline, 2026-11-07 correction)

- **Sarvam `extra_headers`**: nested `api-subscription-key: os.environ/SARVAM_API_KEY` is resolved by LiteLLM **proxy** `ProxyConfig._check_for_os_environ_vars` recursive walk (pinned image `ghcr.io/berriai/litellm:v1.106.4`). Router top-level-only init does **not** expand nested dict values; Tank serves via the proxy path. Covered by `tests/test_maker_direct_routes.py` (no live inference).
- **Prices**: Sarvam USD FX conversion removed from config/docs. Arcee blog USD marked UNVERIFIED; ledger costs zeroed until docs pricing lists the model.
