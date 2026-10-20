# Base gold candidates

`GET /gold/candidates?limit=N` requires `X-Tank-Key` equal to the Base room's
`TANK_KEY`. The endpoint is internal, returns at most 200 candidates and never
accepts a tenant or region from the request. The current Base compose is US-only.
The generic reader also supports `za`; no US source can produce ZA candidates.

## Evidence input

The room reads `/data/gold/<TANK_REGION>/official-matches.jsonl`. Missing evidence
returns an empty list. Nothing is fabricated and this endpoint does not crawl,
run a model, approve a skill or mark gold as checked.

Each line is a matched pair of **independent** saved observations:

- `tenant_id`: the platform tenant UUID, `region`, `public: true`,
  `record_kind: "business"`, `entity_type` (corporation, LLC or registered company),
  `source_id` matching a checked-in engine catalogue entry.
- `official`: `id`, `source_url`, `observed_on` (ISO date), `valid_until` (ISO date),
  `active: true`, `name`, `address`, `city`, two-letter `state`, five-digit `zip`,
  `phone`, and optionally `website`.
- `site`: `source_url`, `website`, `observed_on`, `status: 200`, `blocked: false`,
  and independently extracted `name`, `address`, `city`, `state`, `zip`, `phone`.

Only the trusted ingestion process/operator may write this file; it is not an
upload format or an API parameter. Publish with an atomic file replacement.
Keep the original official-list download and website evidence beside it for
review. Never fill the website observation by copying official-list fields.
The schema is demonstrated with **synthetic** evidence in the tests, not asserted
to be a real record. The legacy Base profile is not sufficient evidence: its
address can originate from the input, and it does not retain an independent
website address. No existing tenant upload is automatically relabelled.

The endpoint rejects private/client rows and individual licence holders. Only
explicitly public business evidence enters this first export. It projects a
small business-field allowlist, dropping arbitrary fields and people data.
Official evidence must still be active, unexpired and no older than 90 days;
the website observation must be no older than 30 days and have the same host.
Names and full addresses must agree after whitespace/case normalization; phone
formatting can differ. This deliberately rejects uncertain abbreviation matches.
ATF and state-registry source names/host rules live in the FFL engine catalogue.
A state registry without a phone cannot qualify by itself.

## Labels

Each eligible pair yields `base.find_site`, `base.verify`, `base.normalize`,
and `base.resolve`, subject to the requested limit. The official source name,
URL and observation date are retained in `label_source`. Duplicate examples are
removed. All labels remain **candidates** for Tank's spot-check workflow.

These are positive site-hint, phone-verification, normalization-key and
single-entry resolution examples. They do not prove open-web discovery accuracy,
fuzzy-address matching or ambiguous entity resolution. Human-reviewed negatives
and trap cases remain necessary.

## Operational follow-up

No valid real evidence snapshots are shipped in this repository. Claude must
populate the local evidence file from official lists and independent website
observations before the endpoint returns real candidates. It is empty until
then. The shared nightly collector must call this endpoint with Base's room key;
adding/changing that collector is outside this task's file list.
