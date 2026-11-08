# Local CPU routing comparison

The founder authorized implementation and local CPU testing. Commercial permission
is **pending counsel review**, not granted; the harness has no automatic licence
approval stop. This extends #786 without changing that queued branch, production
routing, model names, training, memory, OPLI or deployed configuration.

## Reproduce in an isolated cloud checkout

Use Python 3.12 and the hash-pinned CPU stack, in a task-local environment.
Torch 2.15.0+cpu and Transformers 5.22.2 replace the older repository versions
in this isolated worker lock because OSV rejected their known vulnerabilities.
Production requirements stay unchanged:

```sh
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python --require-hashes --no-deps --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match -r tools/router_cpu/requirements.lock
python scripts/compare_router_cpu.py --run-cpu --download --python .venv/bin/python --tenant placeholder-tenant-a
```

The parent command requires the existing Tank development dependencies (including
RouteLLM configuration abstractions), while `.venv` supplies only the worker's
CPU stack. `--no-deps` is deliberate: the lock contains the complete resolved CPU
closure plus the existing hash-pinned RouteLLM wheel, whose unrelated provider
routers are not imported. The worker reuses `routellm_build.extract`: original
BERT class bytes are selected only after the existing upstream-source checksum
passes. No alternate router implementation, checkpoint or quantization replaces it.

The final report is `.checks/router-cpu/report.json`; task-local worker logs and
raw bounded classifier responses stay under that ignored directory. Omit
`--download` to require already verified local files. No endpoint, API key,
paid provider, GPU process or production server is involved.

## Bounds and integrity

`tools/router_cpu/checkpoints.json` records exact immutable model revisions,
SHA256 hashes and sizes for every permitted asset. Arch weights are
`9395579ce8f703f1812ff56215b5fb8a421dd11040c357c0b371b55ea922e5c9`;
RouteLLM weights retain
`e2a92240bad1c7fb9befbf021a62fad5feb1e2a3990d53a28d160a39bb1cac7b`.
Only reviewed safetensors, tokenizer, config and licence/card files are fetched;
optimizer, scheduler, pickle and training binaries are excluded. Downloads have
a five-GiB manifest budget, eight-GiB free-disk prerequisite, twenty-second I/O
timeouts and thirty-minute per-checkpoint deadline. Range resumes reuse bytes
but never waive the full-file size/hash check. Interrupted transfers remain
untrusted until complete verification. No remote model code is trusted.

Models run sequentially, each in its own CPU-only process with two Torch threads,
six hundred CPU seconds, ten-minute wall deadline and hard twenty-four-GiB
address-space ceiling. A parent watchdog checks RSS every 100 ms and kills its
own worker if observed RSS exceeds twelve GiB; this is an observed-memory bound,
not a claim of kernel-enforced RSS control. The process is always reaped.
Arch input is capped at 1,024 tokens and generation at 32 tokens, deterministic;
RouteLLM retains its existing BERT tokenization/truncation behavior. Both loaders
use local files; offline flags and a worker socket-connect refusal prevent
network inference. Model loading is timed separately from classification.

## Frozen sample and measurements

The command validates #786's frozen authored synthetic manifest, selects one
tenant and at most eight examples, and sends only IDs and messages to workers.
Reference labels, provenance and split labels never enter classifier inputs.
Descriptions and RouteLLM threshold are fixed before development or holdout
execution, with no tuning between them. Full data bytes, selected records,
configuration, checkpoint manifest, dependency lock, runtime environment and
source files are hashed in the report.

Measured reports distinguish development and holdout reference agreement,
abstention and strong-model escalation counts. Unknown/malformed Arch output
and invalid RouteLLM scores abstain and choose the strong fallback through the
existing contract adapters. Latencies include load time, first-after-load
classification and later warm classifications; per-example times and process
CPU seconds/peak RSS remain separate. Fixture timings from the older dry-run
command are never mixed with actual model measurements.

These four selected examples are a plumbing sample, not a statistically useful
benchmark. Their authored preference labels are not independently validated
answer-quality gold. The weak/strong names are placeholders, not a calibrated
pair of downstream generators: Arch preference matching and RouteLLM's learned
strong-win probability have different objectives. No downstream model generates
an answer here. `downstream_answer_quality`, dollar inference cost and savings
remain unknown; process CPU seconds are not a billing receipt. The PR records
actual execution results or a concrete technical blocker, never fixture accuracy
as measured model quality. A larger independently reviewed holdout, calibrated
pair/threshold and downstream answer/billing evidence are required before any
routing or savings conclusion. No production activation is part of this work.

## Evidence for counsel

The Arch model remains `katanemo/Arch-Router-1.5B` at
`5b156890a91b1035a86f82faf1a651debf309009`. Its pinned
[LICENSE](https://huggingface.co/katanemo/Arch-Router-1.5B/blob/5b156890a91b1035a86f82faf1a651debf309009/LICENSE)
has SHA256 `9db8f114ce84e3eba181a98edb3034cef64ee09de8b1b2af765c7433554491c9`.
The current Katanemo Community License Agreement is dated April 2, 2026; section
4 discusses a separate commercial licence. The model card labels it
`katanemo-research`. The linked proxy repository's Apache-2.0 licence does not
replace the model's licence. Counsel decides which uses must be blocked.

Bring these provisions to counsel with the pinned text, without treating this
list as a grant of rights or an agent approval requirement:

- Section 3.b.i: provide the agreement with covered redistribution; display
  “Built with DigitalOcean” for a product/service containing covered materials.
- Section 3.b.i: the stated naming provision for an AI model improved using
  covered materials or outputs includes “DigitalOcean” at the beginning of its
  name. This job creates no new model family or product name.
- Section 3.b.iii: retain the notice: “Katanemo Models are licensed under the
  DigitalOcean Community License, Copyright 2026 DigitalOcean, LLC. All Rights Reserved.”
- Sections 3.b.iv, 4 and 7: incorporated acceptable-use terms, commercial terms
  and trademark provisions. Applicability and any required action belong to counsel.
