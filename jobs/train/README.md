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

## BUCKET-1 storage commands

These commands run in a managed cloud worker in the owning room. They do not
run on a founder laptop. `R2_ACCOUNT_ID` and only that room's exact
`R2_ACCESS_KEY_ID_<ROOM>` / `R2_SECRET_ACCESS_KEY_<ROOM>` pair must be present.
`market_lab` maps to `MARKET_LAB` and `tervory-market-lab`. Tank's owner is
`uploads`, using only UPLOADS. There is no generic key or bucket override.

```sh
python jobs/train/r2_archive.py --room base --category datasets --public /data/atf-snapshot.csv
python jobs/train/r2_archive.py --room zenas --category datasets --public /data/judgment.pdf
python jobs/train/r2_archive.py --room tiger --category screenshots --tenant-id "$TENANT_ID" /data/page.png
python jobs/train/r2_archive.py --room radix --category bench --public /data/bench.jsonl
python jobs/train/export_snapshot.py --room base --day 2026-10-21 /data/training.jsonl
python jobs/train/backup.py --owner uploads --once
python jobs/train/backup.py --owner uploads --nightly
```

The examples name input files; the commands do not download those datasets.
The same archiver accepts gold, bench, working files and screenshots. Objects
have `region/tenant/category/date/run/` prefixes. Each part is at most 32 MiB,
with SHA-256 hashes and a manifest written and listed last. Failed uploads
raise an error; they may leave incomplete parts, which are never a complete
snapshot. There are no automatic retries of uncertain writes and no deletes.
Use `restore_archive` in `r2_archive.py` to reconstruct the source and verify
all hashes before atomically replacing a local destination. For backups this
reconstructs the encrypted `.age` file. Any decryption/restore verification is
a separate founder-controlled operation. No private identity is generated,
mounted or stored in this repository, its containers, or CI.

`export_snapshot.py` validates public platform rows, writes R2 first and only
then commits to an already-private Hugging Face dataset. It sends no R2 keys to
HF. A failed R2 archive prevents any HF call. A failed HF operation can leave
a valid R2 snapshot. This explicit command remains available separately. Tank's
automatic exporter now archives the exact existing payload through its owning
room before any HF request. Tank's own snapshots use UPLOADS. Row selection,
format, schedule and paid routes are unchanged; an archive failure stops that
export. A manifest is written last and read back before contacting HF.

`jobs/train/Dockerfile.backup` builds a dedicated worker image from the repository
root, with PostgreSQL client tools and age installed. It includes no model or
HF dependencies and runs as an unprivileged user. Building that image does not
deploy or schedule it. To check encryption after building the image:

```sh
docker run --rm --network none -i tervory-bucket1-backup-test python - < jobs/train/check_backup_image.py
```

This uses real age encryption with a synthetic dump and the published public
example recipient from age documentation. It never generates or loads a
private key, contacts a database or bucket, or decrypts data. The example
recipient exists only in the test script, never as a worker default.

The backup worker requires `pg_dump`, `age`, `DATABASE_URL`, and the public
`R2_BACKUP_RECIPIENT`. The private age identity must stay outside the worker.
It pipes `pg_dump` directly into age; only ciphertext is written to a private
temporary directory. Passwords are passed through the child environment, never
arguments. `--nightly` waits until 02:00 UTC each day; any failure exits nonzero
and must be surfaced by the cloud supervisor. Configuration is checked before
waiting for the first night. Nothing here deploys or starts that worker. ZA client databases are refused before the dump begins. Public ZA
platform datasets may be archived; ZA client files may not leave their box.

Every chassis room exposes `/storage/usage` and
`/storage/objects/{category}/{name}` (GET/PUT), authenticated with that room's
`X-Tank-Key`. Objects require a `tenant_id` query parameter. Collection GET is
`/storage/objects/{category}`. `public=true` permits only platform data on ZA.
The storage routes are explicit: ordinary file IO and Radix scans remain local.
Usage lists the owning bucket with pagination and returns bytes, count and time.
The 1 TB value is a display reference for the account, not a reserved per-bucket
quota. An unavailable bucket never appears as an empty bucket.

### Founder setup and proof after merge

The main Boston compose declares `r2-backup` behind the `r2-backup` profile.
Normal deployment leaves it off. It uses only the uploads pair, the existing
Boston database login, and an encrypted-only spool volume. The founder must
set the public `R2_BACKUP_RECIPIENT` on the worker after merge, verify the
recipient independently, then explicitly enable/deploy that worker. There is
no private-key setting or mount. No backup service is added to the ZA stack;
ZA backups remain a separate founder decision.

Tank exposes `GET /v1/admin/storage/usage`, requiring both the Workspace
`X-Tank-Key` and a founder `X-Tervory-Admin` identity, matching other admin
routes. It returns nine bucket entries and `reference_capacity_bytes` (1 TB).
A measured entry has `bucket`, `used_bytes`, `objects` and `measured_at`; an
unavailable entry has `bucket` and `error`, without fabricated counts. `complete`
is false if any entry is unavailable. If all are unavailable, the same payload
has status 503. Room keys stay in their rooms: Tank collects usage over local
corridors, using Tank room keys rather than R2 credentials. DASH-1 owns the
storage tile in a small follow-up after both merge. No Workspace file is changed.
Ghost's compose and deployment remain GHOST-1's ownership.

After founder-approved deployment, PUT/GET a public test file through each
room's `/storage/objects` route with its room key and a tenant UUID. List it and
compare `/storage/usage` bytes before/after. Another tenant's list must omit it;
foreign bucket or credential owners must fail. The founder usage route must
show measurements or explicit errors, including Ghost until its room is ready.
Trigger the existing public training export and check the owning bucket's
`training/<day>/<run>/manifest.json` before the HF snapshot appears; exported
content must be identical. Missing R2 configuration must prevent HF export.
Room writes cross-check the source region and never proxy between boxes.

After the public recipient is configured and the founder enables the Boston
worker, run one backup, list its dated `backups/.../manifest.json`, reconstruct
only the encrypted file and verify all SHA-256 hashes. Decryption is outside
this worker and CI. In Radix, test the exact R2 host via the proxy, reject
another account and direct sockets, then scan handed-over code with network
calls trapped. Preserve the internal corridor. No production checks, merge,
or deployment are performed by this PR.

Protocol references: [R2 S3 API](https://developers.cloudflare.com/r2/api/s3/api/)
and [AWS Signature V4](https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html).
