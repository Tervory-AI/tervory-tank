# TRAIN-2: serve our own trained models, and use the Hugging Face storage

> Written 20 Oct 2026. `jobs/train/` (#190) can train a LoRA on Hugging Face, but nothing can serve the result, so Tank cannot test or use it. The founder also has Hugging Face storage sitting unused.

**Files you may change:**
- `jobs/train/` and new `jobs/serve/`;
- `litellm/` (roster entries);
- `tank/` (price_book, graduate.py hooks; route registration only in main.py);
- `.env.example` (names only), docs, tests.

1. **Serving, which the founder starts with one action and never starts by itself.** Two modes:
   - `HF_SERVE_MODE=endpoint`: a private Hugging Face Inference Endpoint that scales to zero.
   - `HF_SERVE_MODE=lora`: one base model with many skill adapters on a single endpoint (LoRAX or vLLM multi-LoRA), so each skill's adapter costs nothing extra.
   - **Cap:** serving cost is limited by `HF_SERVE_MAX_USD_DAY` (default 5) and recorded on the ledger.
2. **Register it.** The served version goes into LiteLLM as `tervory-own-<skill>-<version>`, with its real cost per call in `tank.price_book` (endpoint hourly price ÷ measured calls).
3. **Prove it.** The served version enters the CORE-1 bench and the graduation table like any roster model, scored on held-out gold only. Promotion stays the founder's click.
4. **Hugging Face storage, private, public material only:**
   - versioned training datasets per region (already in #190);
   - model and adapter versions;
   - bench results, so every model version keeps its scores;
   - snapshots of the public law corpora (US and SA decided cases and legislation, which are public record) as training data.

   Never client matters, uploads or tenant data. A test fails the upload if any appears.

## Done when
CI green. Tests:
- a trained version appears in the roster after publishing;
- the bench scores it;
- it cannot be promoted without passing held-out gold;
- the cap stops serving;
- an upload containing a client row is refused.
