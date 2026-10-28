# Base campaign audit and confidence histogram

Branch: `codex/base-audit`, from `origin/main` at `1c78aaa`.

## Scope

Add API-only founder access, scoped to an explicit tenant and campaign, for a
persisted seeded sample of exactly 200 verified records, CSV download and checked
CSV import, measured accuracy with a 95% Wilson interval, and confidence counts
using Base's existing score bands. No page, page wording, model call, external
service, live-data change or production check is included.

Use the existing verified-contact export and founder guard. Save the sampled
record evidence so reopening the audit cannot silently substitute newer results.
Reject unfinished campaigns and populations smaller than 200. Report unsure
verdicts separately and make the accuracy denominator explicit.

## Implementation checkpoint

Implemented in `tank/base_audit.py`, the new routes in `tank/base_product.py`, and
the additive `tank.base_audits` table in `tank/schema.sql`.

The API stores seed, population count/digest, 200 evidence snapshots, creator,
reviewer, per-record verdicts and review date. All five endpoints require the
existing founder identity and Workspace key; all reads/writes require tenant and
campaign. A seed retry reopens the existing audit. Checked uploads are atomic,
idempotent and cannot edit the sampled evidence or silently replace saved verdicts.

First proof command (isolated local PostgreSQL, no model or outbound HTTP):

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55441/postgres \
  /tmp/command-repo-venv/bin/python -m pytest -q tests/test_base_audit.py \
  tests/test_base_product.py tests/test_base_database.py --tb=short
```

Result: **53 passed in 15.34s**, saved in `step-1-tests.txt`. This includes
deterministic selection, saved evidence, CSV round trip, known accuracy/interval,
campaign and tenant isolation, founder authorization, malformed imports,
histogram boundaries, concurrent seed retries and idempotent schema application.

Remaining: final edge-case proof, complete command/result handoff, and startup,
lint and secret checks. No production checks.

Claude opens the draft PR. Live acceptance and independent review remain pending;
no founder screenshot is claimed for this API-only work.
