# BATCH-1: send work that can wait through the providers' batch APIs, automatically

> Written 20 Oct 2026. `tank.policy.batch_eligible` exists but nothing uses it. OpenAI, Anthropic and Google all run batch jobs at roughly half price, returned within 24 hours. Base runs and Zenas Convert over court archives are exactly that kind of work.

**Files you may change:**
- new `tank/batch.py`;
- `tank/main.py` (route registration only);
- `tank/schema.sql` (additive);
- `litellm/` (batch settings);
- `agents/zenas/core/convert.py` and `agents/base/pipeline.py` (only to submit work as a batch when asked);
- `workspace/app/tank/` (batch view);
- tests.

1. **Batch route.** `POST /v1/route/batch` takes many requests for one task type. If the task's policy has `batch_eligible` true, Tank submits them through LiteLLM's batch API to the provider of the chosen model. Otherwise it runs them as normal calls.
2. **Tracking.** `tank.batches` holds id, task type, model, count, status, submitted and finished times, estimated and actual cost. Results are written back request by request, each with a normal ledger row (`batch: true`) and the batch discount on its receipt (baseline versus actual).
3. **Automatic choice.** Convert over an archive and a Base batch larger than `TANK_BATCH_MIN` (default 50) go to batch when the task is batch-eligible. Anything a user is waiting on in the window never does.
4. **Failures and limits.**
   - A failed or expired batch is retried once as normal calls, inside the task's cap.
   - Nothing is left unfinished without an error on the batch view.
   - The 24-hour limit is shown to the founder before submitting.

## Done when
CI green. Tests:
- an eligible task is submitted as a batch;
- results come back with ledger rows and the discount;
- an interactive window request is never batched;
- an expired batch falls back once;
- spend stays within the cap.
