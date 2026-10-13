# C3 — Data page: filters, search, record drawer

**Goal:** the founder can work through 77,438 enriched FFL records: filter, search, open one record and see every field with its source and confidence.

**Files you may change:** `workspace/app/data/*` (split into components as you like), `workspace/app/api/base/route.ts`, `workspace/lib/tank.ts`, and in `tank/main.py` only the function `base_records` and its decorator.

**Tank (`GET /v1/base/records`) — add optional query params, all still scoped by `tenant_id`:**
- `q` — case-insensitive match on `profile->'name'->>'value'` or `raw` business/licence name (use `ILIKE`, parameterised).
- `tier` — one of `ready|use_with_awareness|review|requeue` (matches `profile->'tier'->>'value'`).
- `flag` — matches `profile->'flags'->'value' ? $flag`.
- `has` — `website` or `email` (non-empty value).
- `state` — two-letter code, matches `profile->'state'->>'value'`.
- `sort` — `confidence_desc` (default `created_at desc`).
- Return a `total` count alongside rows: change the response to `{ "rows": [...], "total": n }` **only** when a new `paged=1` param is set, so existing callers keep working.

**Workspace:**
- A filter bar above the table: search box (debounced 300 ms), tier select, flag select (no_website, no_registry_match, phone_mismatch, renewal_window, licence_lapsed, site_thin_or_stale, email_domain_differs), "has website", "has email", state select. Filters live in the URL query string.
- Paging: 100 rows per page, "Showing 1–100 of 12,406".
- Clicking a row opens a right-hand drawer (not inline expansion) with: header (name, city/state, tier chip, score), sections "Contact" (website, emails, phones, decision maker, contacts list with email source), "Licence" (all `ffl_*` fields), "Business" (size, revenue, model, NAICS — labelled "estimate"), "Socials", "Checks & flags" (pass 7 layers and checks), and a collapsed "Raw record". Every value shows its source and confidence as a small mono caption.
- Export CSV keeps exporting the whole batch (unchanged).

**Done when:** PR with screenshots of the filter bar, a filtered result count, and the drawer for one record; a unit test for the SQL builder in `tests/`.
