# Context.dev trial

`context_dev.py` uses the company Brand endpoint only. A URL is reduced to its
domain; query strings, credentials, fragments and IP addresses are refused.
Callers must supply only a business's public identity. No people, email,
transaction, scrape or challenge-bypass endpoint is used.

API contract checked on 20 October 2026:
- https://docs.context.dev/brand/overview
- https://docs.context.dev/brand/lookup-by-name
- https://docs.context.dev/account/credits

A Brand lookup reserves 10 credits. `CONTEXT_DEV_MAX_CREDITS` defaults to 500.
Actual reported credits are kept separately; an unreported charge stays unknown,
holds its reservation and stops the trial. Credits are never treated as dollars.
Failures are settled too. No automatic retry or redirect is followed.

## Integration required before enabling

Tank has no external-credit ledger API. Implementing it requires a separate
authorized change in `tank/` (an authenticated reservation/settlement API and
additive storage for credit units). The `Ledger` contract must atomically reserve
against `(tenant_id, run_id)` in Tank, enforce the supplied limit across processes
and restarts, persist pending attempts before network calls, and settle by
reservation id idempotently. Failed or unknown attempts retain their reservation.
Never replace this contract with an in-memory logger in production.

The adapter refuses all live calls without that ledger. It is deliberately not
wired into the batch worker yet. `trial.store_trial_candidate` locks and scopes
the selected record, keeps an existing candidate, and writes only the candidate
slot. After that API is available, instantiate one
adapter per persisted batch/run, call it only for explicitly selected public
business records, and store its result in `passes.context_dev`, alongside Base's
profile, never merged into it. The Base page reads this slot for comparisons.
Checked answers belong in `passes.context_dev_checked` as
`{"checked": true, "expected": {"website": "...", "name": "..."}}`, written by a
trusted review process, never copied from provider output or raw upload fields.

The Docker image includes this module and reads the two Base-only settings.
Neither setting enables a trial by itself.

## Fixtures

Tests use explicitly synthetic protocol samples and HTTP mocks. No provider
credential is available in this build environment, so there are **no captured
real responses**. Capture sanitized business-only responses after ledger support
is deployed, retaining credit headers and capture provenance. Do not describe
the synthetic samples as evidence of provider accuracy.
