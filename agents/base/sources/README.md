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

## Running a trial

After deployment, set `CONTEXT_DEV_API_KEY` in Base's environment. Claude can
submit selected public businesses to Base's internal `POST /context-dev/trial`
with its room key in `X-Tank-Key`. The body contains `tenant_id`, `run_id` (a
completed Base batch UUID), and `records`, an array of up to 50 entries:

```json
{
  "record_id": "the selected completed record UUID",
  "public": true,
  "domain": "stripe.com",
  "checked_answers": {"website": "https://stripe.com"}
}
```

Each entry requires `public: true`; supply `domain`, `url`, or `name`.
Checked answers are optional and independently checked, never provider output.
Neither environment setting starts calls automatically.

## Accounting and recovery

Base durably reserves 10 credits in its own `context_dev_calls` table before
each provider request. A batch lock and persisted reservations enforce the cap
across processes and restarts. Failed attempts retain their reservation.

Every attempted lookup is delivered through Tank's `POST /v1/ledger/vendor`,
with agent `base`, task type `base.context_dev`, vendor `context.dev`, actual
reported credit units and zero dollars. Missing charges remain NULL with an
unverified outcome. Tank scopes these events to PLATFORM_TENANT. The Base key can
write only for Base; the Workspace key cannot use this route. Stable call IDs
make delivery retries append-only and idempotent.

Base's durable outbox retries ledger delivery on its heartbeat or the next trial.
A crash without a stored response becomes an unknown-charge event, not another
paid request. Candidates are saved in `passes.context_dev` after Tank acknowledges
the ledger entry, alongside Base's unchanged profile. The Base page reads this
slot for comparisons across its latest 200 displayed records.
Checked answers belong in `passes.context_dev_checked` as
`{"checked": true, "expected": {"website": "...", "name": "..."}}`, written by a
trusted review process, never copied from provider output or raw upload fields.

The Docker image includes this module and reads the two Base-only settings.
Neither setting enables a trial by itself.

## Fixtures

`tests/fixtures/context-dev/brand-documented.json` is a labelled documented
example, not a capture or accuracy evidence. Other protocol samples are synthetic.
CI uses no live vendor calls. There are **no captured real responses** yet.
After the key is set, Claude captures sanitized public-business responses,
retaining credit headers and provenance.
