# Squad LoRA training

Run on the US cloud box with `HF_TOKEN`, `HF_ORG`, `DATABASE_URL` and optionally
`HF_TRAIN_MAX_USD` (default 50) in its environment. Install requirements.txt in a
job-specific virtual environment. Never pass credentials in command arguments.

```sh
python jobs/train/run.py --minutes 120
python jobs/train/run.py --minutes 120 --day 2026-10-20 --submit
python jobs/train/run.py --receipt /private/path/final-hf-bill.json
```

The first command only quotes live A10G-small pricing. Submission sets a hard
runtime timeout and creates a versioned private model repository. There are no
automatic retries. Submission holds database advisory lock 871228, refuses any
unreconciled platform training job, and saves a pending reservation before
contacting HF. The reservation is replaced with the HF job id after submission.
A second submission is refused until the previous job's actual bill is reconciled.
If submission fails or its outcome is uncertain, the pending reservation remains:
check HF Jobs and reconcile the reservation with the actual HF job before retrying;
do not clear it merely to bypass the spending guard. Qwen3-4B (Apache 2.0) is trained with TRL and LoRA across the
available task types in that day's private `tervory-public-<agent>` snapshots.
Only explicit public platform examples are exported; client, inactive and gold
holdout rows are excluded. Each box exports only its own region: public ZA
examples go to `snapshots/za/`, and public US examples to `snapshots/us-east/`.
The training job reads both snapshots. ZA client matters remain local.

Before using the new exports, check the organisation's legacy `tervory-<agent>`
datasets on Hugging Face and delete them. They may contain rows exported before
these privacy checks. The job reads only `tervory-public-<agent>` datasets; it
does not clean up or read the legacy datasets.

The job checks the privacy of every dataset and the destination, validates every
row before constructing the trainer, deduplicates by input, and reserves a
stable 10% of the exported training inputs for validation loss. This is **not**
the gold held-out score and cannot authorize promotion. Serving is unchanged.

HF's Jobs API exposes timing but not the final billed dollar amount. Do not
pretend a timing estimate is a bill. After completion, copy the final compute
usage charge from HF billing into a local receipt:

```json
{"job_id":"JOB_ID","namespace":"YOUR_ORG","currency":"USD","billed_usd":2.125}
```

Reconciliation checks terminal job status and writes that actual amount once to
the existing ledger as platform `training.lora` spend, in a transaction with its
job record. Repeating the same receipt is a no-op; a conflicting amount fails.
This is a founder-supplied billing receipt, not an API-verified invoice. Failed
jobs also need reconciliation. No database or Tank credential reaches HF.

No paid job was launched while building this change. The first GPU execution,
model quality assessment and actual receipt reconciliation remain runtime steps.

References: [HF Jobs](https://huggingface.co/docs/huggingface_hub/en/guides/jobs),
[pricing and billing](https://huggingface.co/docs/hub/jobs-pricing),
[TRL SFT](https://huggingface.co/docs/trl/sft_trainer),
[model licence](https://huggingface.co/Qwen/Qwen3-4B).
