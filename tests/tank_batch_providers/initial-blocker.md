# Tank provider batches — blocked by pinned LiteLLM Anthropic support

**Stopped under rule 9. No Tank implementation changes.** The requested completion
condition requires one Anthropic provider batch for 50 non-interactive requests.
The repository pins LiteLLM **v1.106.4**, which cannot create that batch through
`/v1/batches`. It has Anthropic retrieval/result support, but its creation methods
are unimplemented. The missing capability is upstream Anthropic batch submission
in the pinned release. Changing the pin or adding a provider client would depart
from this brief; neither was done.

Started fresh from main `a99f3cb`, branch `codex/tank-batch-providers`.
Read `AGENTS.md`, `docs/cursor/CONTEXT.md`, the milestone rules block and Tank's
existing batch routing/submission/polling/fallback paths. No questions, GitHub API,
secrets, paid model calls, live SQL, production changes or founder-laptop access.
Claude opens the PR; founder merges. This branch contains evidence only.

## Exact version and support evidence

Repository pin: [`litellm/Dockerfile:7`](../../litellm/Dockerfile).
Upstream tag `v1.106.4` resolved via git to
`ea7ca16dbc3904d9e59a9505f379a2ca3091821f`.

Pinned upstream source:

- [Batch submission dispatcher](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/batches/main.py#L249)
  admits OpenAI-compatible adapters, Azure, Vertex, xAI and configured generic
  batch adapters. There is no Anthropic or `gemini` create branch.
- [Generic provider batch configurations](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/utils.py#L9681)
  return only Bedrock and Mistral adapters.
- [OpenAI-compatible batch providers](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/types/utils.py#L4308)
  are `openai`, `hosted_vllm`, and `litellm_proxy`.
- [Anthropic creation placeholders](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/llms/anthropic/batches/transformation.py#L114)
  raise `NotImplementedError`. The audit below executes both isolated methods
  without loading the SDK, looking up credentials or contacting any service.
- [Proxy create endpoint](https://github.com/BerriAI/litellm/blob/ea7ca16dbc3904d9e59a9505f379a2ca3091821f/litellm/proxy/batches_endpoints/endpoints.py#L342)
  delegates model-aware/encoded-file submission to the same batch dispatcher.
  The managed-file route does not supply a missing Anthropic adapter.

| Provider/adapter | Submission in this pin |
| --- | --- |
| `openai` | Supported |
| `azure` | Supported |
| `vertex_ai` (including its Gemini batch implementation) | Supported |
| `bedrock` | Supported via generic configuration |
| `mistral` | Supported via generic configuration |
| `xai` | Supported |
| `hosted_vllm` | Supported adapter / LiteLLM-executed batches; no universal provider discount inferred |
| `litellm_proxy` | Forwarding adapter; downstream support/discount is not universal |
| `anthropic` | **No creation support**; retrieval/results do not establish submission support |
| `gemini` (AI Studio, separate from Vertex) | **No submission adapter** in the batch dispatcher/configuration |

This is a source-level submission inventory, not evidence that any deployed
account/model is batch-ready. Provider discounts and end-to-end capability were
not implemented or guessed after discovering the blocker.

The current [LiteLLM batch documentation](https://docs.litellm.ai/docs/batches)
was also checked, but the immutable pinned source above determines the finding.

## What changed (file and line)

- `tests/tank_batch_providers/verify_pinned_support.py:1`: standalone read-only
  audit of the pin, dispatcher and isolated Anthropic creation methods.
- `tests/tank_batch_providers/pinned-support.txt:1`: exact audit output.
- `tests/tank_batch_providers/PR.md:1`: this blocker report and proof.

No `tank/`, LiteLLM pin, pricing, reservation, fallback, configuration, UI or
production source was changed. Existing caps, exclusions and full-price fallback
therefore remain exactly as they were.

## Commands and results

All commands ran in the managed cloud. Main/branch setup:

```sh
cd /workspace/tervory-tank
git status --short
git fetch origin main
git switch -c codex/tank-batch-providers origin/main
```

Clean starting tree; fetched `a99f3cb`; branch created successfully.
The scope was committed early as `44597ee` and pushed with:

```sh
git add tests/tank_batch_providers/PR.md
git commit -m 'Record provider batch scope and pinned LiteLLM verification plan'
git push -u origin codex/tank-batch-providers
```

Success. Upstream inspection used git, never the GitHub API:

```sh
cd /workspace
git clone --depth 1 --branch v1.106.4 --filter=blob:none --sparse https://github.com/BerriAI/litellm.git /workspace/litellm-batch-reference
git -C /workspace/litellm-batch-reference sparse-checkout set litellm/batches litellm/llms litellm/proxy/batches_endpoints litellm/types tests/local_testing/test_batches.py docs/my-website/docs/batches.md
git -C /workspace/litellm-batch-reference rev-parse HEAD
```

Exit 0; revision `ea7ca16dbc3904d9e59a9505f379a2ca3091821f`.
The requested docs path was absent in that checkout; source inspection used
`litellm/batches/main.py`, `litellm/utils.py`, `litellm/types/utils.py`,
`litellm/proxy/batches_endpoints/endpoints.py` and the Anthropic batch handlers.
No upstream code was installed or imported.

```sh
cd /workspace/tervory-tank
/workspace/worker-venv/bin/python tests/tank_batch_providers/verify_pinned_support.py /workspace/litellm-batch-reference > tests/tank_batch_providers/pinned-support.txt 2>&1
/workspace/worker-venv/bin/ruff check tests/tank_batch_providers/verify_pinned_support.py --select E9,F
git diff --check
```

Audit exit **0**: confirms the missing submission dispatch and both actual
Anthropic creation methods raising `NotImplementedError`.
[Complete output](pinned-support.txt). Ruff and whitespace checks passed.
This passing audit proves the blocker; it is not a successful batch test.

Evidence checkpoint:

```sh
git add tests/tank_batch_providers
git commit -m 'Document pinned LiteLLM Anthropic batch submission blocker'
git push -u origin codex/tank-batch-providers
```

## Acceptance not performed

No provider integration was changed, so the requested submit/poll/complete,
partial-failure fallback, cost-cap and discounted-ledger regression suite has not
been built or claimed. No 50-request live Anthropic batch was sent. No founder
browser screenshot or paid-call proof exists. Work stopped at the confirmed
upstream capability blocker as rule 9 requires.
