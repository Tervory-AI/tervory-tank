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

## Planned proof

Offline tests with an isolated local PostgreSQL database: deterministic selection,
saved evidence, CSV round trip, known accuracy/interval, campaign and tenant
isolation, founder authorization, malformed imports, histogram boundaries, and
idempotent schema startup. Commands and actual results will replace this plan.

Claude opens the draft PR. Live acceptance and independent review remain pending;
no founder screenshot is claimed for this API-only work.
