# Route deferred Vertex and Anthropic work as provider batches

Tank previously queued only OpenAI provider batches. Eligible Vertex Gemini and
Anthropic work now uses one provider batch instead of full-price per-item calls.
The 28 Oct 03:15 PT founder decision authorizes the Anthropic pass-through path.
LiteLLM stays pinned to v1.106.4. Standalone Gemini remains unsupported for batches.

Implementation and offline verification are complete. **No live batch or founder
browser acceptance is claimed.** No paid calls, new settings, dependencies,
provider credentials, UI changes, production writes or deployments were made.
Claude opens this branch's PR; the founder merges.

## Provider paths and real discounts

| Provider | Submit | Poll/results | Charge multiplier |
| --- | --- | --- | --- |
| OpenAI (existing) | LiteLLM `/v1/files` then `/v1/batches` | Existing LiteLLM batch/file endpoints | 0.5, existing behavior |
| Vertex Gemini (`vertex_ai/gemini-*`) | Same LiteLLM batch/file API | Same normalized LiteLLM batch/file API | 0.5 for input and output |
| Anthropic | LiteLLM `/anthropic/v1/messages/batches`, one POST containing all items | GET the same route with the batch ID; GET its `/results`; POST its `/cancel` | 0.5 for input and output |
| Standalone `gemini` and other providers | Existing capped per-item route | Unchanged | No batch discount assumed |

Discount evidence: [Google's Gemini batch pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
and [Anthropic Message Batches pricing](https://platform.claude.com/docs/en/build-with-claude/batch-processing).
Both authorize a 50% reduction for these paths; the code does not assume that all
providers, Vertex Model Garden or Anthropic-on-Vertex have this discount.
Normal input/output prices still come from Tank's existing selected-model roster.

## Pinned LiteLLM evidence

`litellm/Dockerfile:7` pins v1.106.4. Upstream tag commit:
`ea7ca16dbc3904d9e59a9505f379a2ca3091821f`.

- [Anthropic pass-through route](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py#L892)
  accepts GET/POST under `/anthropic/{endpoint:path}`, selects the credential
  inside LiteLLM, and forwards to Anthropic. The existing compose already passes
  the `ANTHROPIC_API_KEY` name into LiteLLM; Tank does not receive that provider key.
- [Pass-through credential selection](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/proxy/pass_through_endpoints/passthrough_endpoint_router.py#L73)
  falls back to the existing provider environment name. No new pass-through
  configuration or credential is needed for this path.
- [Vertex batch dispatcher](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/batches/main.py#L341)
  already supports submission; [Vertex file results](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/llms/vertex_ai/files/transformation.py#L1246)
  are normalized into the existing OpenAI-compatible result shape.
- The unified `/v1/batches` Anthropic creation methods remain unimplemented.
  The original [source audit](initial-blocker.md) is retained as historical proof.
  The new authorization uses the separate, already implemented pass-through route.
- The pinned [Anthropic file handler](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/llms/anthropic/files/transformation.py#L291)
  returns native result content. Tank therefore reads native results through
  pass-through and maps only their content/usage/outcome into its existing result
  handler. It does not add a provider SDK, direct HTTP client, or credential logic.

[verify_passthrough.py](verify_passthrough.py) executes the actual pinned route
and credential-selector functions with offline dependencies. It verifies create,
retrieve, results and cancel forwarding, plus credential lookup **by name only**.
It imports no upstream SDK, reads no real credential and makes no network calls.
[Audit output](passthrough-audit.txt).

## What changed (file and line)

| File | Line | Change |
| --- | --- | --- |
| `tank/batch_providers.py` | 12 | Explicit supported-provider charge multipliers; unsupported providers do not inherit a discount. |
| `tank/batch_providers.py` | 31 | Native Anthropic compatibility check; retains normal LiteLLM routing for unsupported generation options instead of dropping them. |
| `tank/batch_providers.py` | 43 | Moves system messages into the native system field and keeps native model, content, max tokens and item IDs. |
| `tank/batch_providers.py` | 58 | One Anthropic pass-through submission; OpenAI/Vertex reuse existing file-plus-batch calls. |
| `tank/batch_providers.py` | 77 | Provider status and cancellation adapters; only Anthropic `ended` permits result handling/fallback. |
| `tank/batch_providers.py` | 98 | Maps native Anthropic success/error/canceled/expired rows into Tank's existing handler shape. Never follows an upstream `results_url`. |
| `tank/main.py` | 2344 | Selects the explicit rate from the new module. |
| `tank/main.py` | 2359 | Adds only the Anthropic API version header for pass-through; keeps existing LiteLLM authentication. |
| `tank/main.py` | 2402 | Replaces OpenAI-only eligibility with the supported-provider/compatible-payload check. |
| `tank/main.py` | 2565 | Calls the submission/status/cancel/results helpers from the existing durable batch worker. |
| `tank/Dockerfile` | 5 | Adds the new module to the existing COPY list, per standing repository instructions. |
| `tests/test_tank_batch_providers.py` | 105 | Fifty requests create one batch per provider; real SQL verifies the discounted ledger, order, idempotency and tenant isolation. |
| `tests/test_tank_batch_providers.py` | 141 | Partial failures and reservation preservation; caps, exclusions, cancellation, authentication boundary and uncertain-submission tests follow. |
| `tests/test_tank_batches.py` | 195 | Existing unsupported-provider regression now uses standalone Gemini instead of newly supported Anthropic. |
| `tests/tank_batch_providers/` | — | Source audits, exact command outputs and this proof file. |

`_call_upper`, reservation calculations/storage, `_batch_result` ledger writes,
`_batch_fallback`, policy revalidation, retry claims, tenant scoping and locks are
unchanged. Interactive, MoA, ineligible-policy and below-`TANK_BATCH_MIN` work retain
the existing route. A fallback is still a full-price single call, with zero batch
discount, only inside the remaining cap after the original reservation.

## Exact verification commands and results

All commands ran in `/workspace/tervory-tank` on the managed cloud machine.
The database URL below is a credential-free, local test Postgres. Each SQL test
creates and drops its own isolated test database. No production SQL was executed.

### Pinned source verification

The earlier source checkout and initial audit commands are recorded in
[initial-blocker.md](initial-blocker.md). This step extended that same sparse checkout:

```sh
cd /workspace/litellm-batch-reference
git sparse-checkout add litellm/proxy/pass_through_endpoints litellm/proxy/anthropic_endpoints
git sparse-checkout add litellm/files
cd /workspace/tervory-tank
/workspace/worker-venv/bin/python tests/tank_batch_providers/verify_passthrough.py /workspace/litellm-batch-reference > tests/tank_batch_providers/passthrough-audit.txt 2>&1
```

Passed: all four native operations and existing credential selection by name.
One earlier sparse-checkout invocation also named the file
`litellm/proxy/proxy_server.py`; git rejected that file as a directory argument.
The corrected directory-only command above succeeded. No upstream code changed.

### Batch lifecycle and ledger

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_batch_providers.py tests/test_tank_batches.py > tests/tank_batch_providers/batch-tests.txt 2>&1
```

**48 passed in 36.30s**, five existing FastAPI deprecation warnings.
[Complete output](batch-tests.txt).

The 50-request test runs at the actual default `TANK_BATCH_MIN=50`, separately for
OpenAI, Vertex and Anthropic. Its stubbed usage is 100 input/50 output tokens and
stubbed rates are $0.000002/input and $0.00001/output token. For all 50 real local
ledger rows in each test it asserts:

- `batch=true`, one provider submission, no foreground calls;
- full-price baseline $0.000700, actual $0.000350, discount $0.000350;
- duplicate polls do not add receipts or submissions;
- final total reservation is $0.017500 for that completed batch;
- the other tenant cannot read the batch.

The suite also checks explicit/expired/canceled/missing item fallback, one retry,
reservation preservation, cost-cap refusal before submission and before fallback,
interactive/small/MoA exclusions, unsupported standalone Gemini, deadline
cancellation, all requests staying inside the LiteLLM URL/authentication boundary,
and uncertain submissions never being purchased a second time.

The first development run had **40 passed, 4 failed** because the test stub
assigned failures by uploaded array order; Tank uploads in UUID order and returns
in request position order. The stub now selects the failed item by the original
request position, while still returning results in reverse order. Product code
was not changed to satisfy the incorrect ordering assumption.
[Original failed output](batch-tests-initial.txt) is retained. Four additional
checks for authentication and uncertain submissions were added before the final run.

### Existing routing and CI checks

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres PYTHONPATH=tank /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_ladder.py tests/test_tank_tenant_boundaries.py tests/test_secrets.py tests/test_tank_boots.py > tests/tank_batch_providers/routing-ci-tests.txt 2>&1
/workspace/worker-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401' > tests/tank_batch_providers/lint.txt 2>&1
git diff --check
```

**19 passed in 22.37s** ([output](routing-ci-tests.txt)), including the existing
secret scan and Tank starting twice against a new local database. Lint passed
([output](lint.txt)); whitespace checks passed. No hosted CI result is claimed.
No frontend source changed, so no frontend build or fabricated screenshot is offered.

## Branch and pushes

Continued the requested `codex/tank-batch-providers` branch, originally based on
main `a99f3cb`. Pushed after each implementation step:

```sh
git commit -m 'Enable pinned LiteLLM Vertex Gemini batches at the documented rate'
git push -u origin codex/tank-batch-providers
# b64aac5
git commit -m 'Submit Anthropic batches through existing LiteLLM pass-through and verify provider lifecycle'
git push -u origin codex/tank-batch-providers
# d09df37
```

The final proof checkpoint is committed and pushed on this same branch. Git was
used for fetch/clone/push; no GitHub API, merge, deployment or live provider call.

## Decisions I made / acceptance still pending

- Keep this amendment limited to OpenAI, Vertex Gemini and direct Anthropic via
  LiteLLM. Standalone Gemini remains unsupported, as explicitly requested.
- Native Anthropic payload shaping is confined to the approved pass-through route.
  Unsupported native generation options retain the existing capped foreground
  path. Provider errors are not copied into stored operational error text.
- Keep every request inside the existing `LITELLM_URL` gateway. Tank never calls
  Anthropic directly or receives its key. Pass-through results URLs are ignored;
  the known batch ID determines the LiteLLM result path.
- The audit confirms the pinned code and existing setting names, not the live
  credential values, provider balance, deployed model availability or live health.
- Founder acceptance remains pending after merge/deployment: submit 50 eligible,
  non-interactive requests under an Anthropic policy and verify one provider
  batch plus discounted ledger entries in the founder's own browser. The offline
  test proves that flow against the stub, not against a paid live service.

There is no founder-test screenshot or live provider receipt in this task. No such
proof is claimed or invented.
