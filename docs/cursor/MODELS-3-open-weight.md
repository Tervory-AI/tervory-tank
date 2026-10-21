# MODELS-3: every major open-weight model on the roster, Llama included

> Written 21 Oct 2026. Founder: "I want to add all the open weight models including Llama."
>
> **Why it matters beyond choice.** Open-weight models are the ones we can later fine-tune and serve ourselves (TRAIN-2). Putting them on the roster now means the bench and shadow tests measure each base model on our real tasks *before* we train it. That gives us the "before" for every trained model we ship.

**Files you may change:**
- `litellm/config.yaml` and `litellm/config.za.yaml`;
- `tank/graduate.py` (only if a new provider prefix needs handling, as MODELS-2 did);
- `docker-compose.yml` and `docker-compose.za.yml` (litellm env names only);
- `.env.example` (names only);
- tests.

No policy rows change. Nothing is promoted.

1. **How to reach them: Hugging Face Inference Providers first.** One Hugging Face token reaches open-weight models hosted by many inference companies, billed to the founder's Hugging Face account. LiteLLM supports it as the `huggingface` provider.
   - Use a separate token name, `HF_INFERENCE_TOKEN`, with only the "Inference Providers" permission. It is not the training `HF_TOKEN`: least privilege, and either can be revoked alone.
   - Where a model is not available there, a direct host (Together, Fireworks, Groq, DeepInfra and similar) may be added as a second route, with its own key name. Do not add a new paid provider unless the model is unavailable on Hugging Face; say so in the PR.
2. **Which models: the current flagship and a small variant of each major open-weight family:**
   - Meta **Llama**;
   - Alibaba **Qwen**;
   - **Mistral**;
   - Google **Gemma**;
   - OpenAI **gpt-oss**;
   - **DeepSeek** (open weights served by a host, next to our existing DeepSeek API entries);
   - Moonshot **Kimi** (open weights served by a host);
   - Zhipu **GLM**;
   - Microsoft **Phi**.

   Choose the current versions from the Hugging Face Inference Providers catalogue on the build day. Do not use versions from memory.
3. **Every entry:**
   - a Tervory name (for example `llama`, `llama-small`, `qwen`, `qwen-small`);
   - the underlying model id;
   - which host serves it;
   - the price per million tokens from the catalogue, with URL and date;
   - the model's licence (Llama community licence, Apache 2.0, MIT and so on), with a link;
   - a fallback.

   Both rosters (Boston and ZA) get the same entries.
4. **Licence check.**
   - Note any licence condition that matters for commercial use (for example Llama's acceptable-use policy and its threshold for very large services).
   - Flag in the PR any model whose licence would stop Tervory from fine-tuning or serving it commercially.
   - Do not add it until the founder decides.
5. **The provider allow-list (`TANK_PROVIDER_ALLOW`) still applies.** A tenant who excludes a provider family excludes its open-weight hosts too. Name the family by the model maker, not the host.
6. **After deploy:**
   - every new model shows on the Tank page with its price;
   - the nightly bench includes them automatically (CORE-1);
   - nothing switches model by itself.

## Done when
CI green. Tests:
- every new model is in both rosters with a sourced price, licence and fallback;
- no policy row changes;
- the allow-list excludes a family's open-weight entries;
- `HF_INFERENCE_TOKEN` is passed only to LiteLLM, never to Tank or a room.
