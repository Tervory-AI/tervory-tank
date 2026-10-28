# Automatic product case-study reports from existing client proof

Clients previously had no complete, fixed case-study contract across products. This adds version-1 API reports for the founder's nine products, each with all six shared Tank figures. Every figure has its fixed `id`, `unit`, `type` and `value`; missing sources produce zero, zero-filled histogram bins, an empty ranked list, or one zero per UTC day for a series. Values come from existing evidence; only report identities are persisted.

Branch: `codex/case-study-reports`, started from `origin/main` at `9769998`. Claude opens the draft PR. No GitHub API, deployment, production SQL, model calls, new settings, page files or page wording. Independent review, CI on the eventual PR, and the founder's live acceptance are pending.

## Changes by file and line

| File | Change |
| --- | --- |
| [tank/case_study_templates.py:10](../../tank/case_study_templates.py#L10) | Fixed types, units, bins and the exact 44 figures: 38 product figures plus six shared figures. Zero initialization at line 86. |
| [tank/proof.py:82](../../tank/proof.py#L82) | Tenant/product projection reusing CORE-1 `TOTALS`, `receipt_source` and conservative `savings_cte`; no parallel receipt or money store. |
| [tank/case_study_sources.py:31](../../tank/case_study_sources.py#L31) | Tenant-bound product readers, reusing Base arithmetic and optional audit measurement. Missing tables leave zeros; query failures are not disguised as zero. |
| [tank/schema.sql:1971](../../tank/schema.sql#L1971) | Additive, idempotent report identities, product-grant/use triggers and existing-client backfill. No access grants added. |
| [tank/case_studies.py:19](../../tank/case_studies.py#L19) | Registration reconciliation, period validation, founder/client access and complete report API. |
| [tank/main.py:3843](../../tank/main.py#L3843) | Mount the report router. |
| [workspace/lib/tenant.ts:17](../../workspace/lib/tenant.ts#L17) | Existing tenant creation/selection calls idempotent registration. No new sign-in flow. |
| [workspace/lib/tank.ts:7](../../workspace/lib/tank.ts#L7) | Server-side allowlisted requests, server-owned identity and registration helper. |
| [workspace/app/api/case-studies/[[...path]]/route.ts:12](../../workspace/app/api/case-studies/[[...path]]/route.ts#L12) | Authenticated GET API; clients cannot override tenant/caller identity; founder can select clients. Empty error bodies and private/no-store responses. |
| [tests/test_case_study_reports.py:93](../test_case_study_reports.py#L93) | 21 offline checks, including real PostgreSQL calculations, optional audit contract, late provisioning and restricted room roles. |
| [workspace.cjs:1](workspace.cjs#L1), [local_proof.py:1](local_proof.py#L1) | Execute actual Workspace modules with offline authentication stubs; start real Tank and exercise HTTP against disposable PostgreSQL. |

## Registration and API

The existing Clerk organization creation path registers the tenant before returning it. Existing organizations are reconciled on tenant selection. Products in `tank.tenant_squad` get identities with `ON CONFLICT DO NOTHING`; adding a product through the existing founder squad endpoint inserts its report in the same database transaction. Reapplying schema and repeating registration do not duplicate reports. A report never grants product access.

Trigger uses its saved voice as provisioning evidence. When its table exists at Tank startup, a trigger registers immediately. If the room creates its table later, Tank reconciles voices every 30 seconds; tenant selection also reconciles immediately. The room still cannot read/write Tank tables directly. The narrow trigger runs under its owner with a fixed search path and only inserts identities from the triggering row.

**Autumbra provisioning limit:** there is no squad-grant or real client deployment registry on this main. Its template exists, and existing/new `ghost` or `autumbra` Tank activity registers its report; its product figures remain zero. A provisioned-but-unused Autumbra client cannot be discovered before the product has a durable provisioning source. No fixture deployment is treated as a client entitlement.

Tank endpoints use the existing authenticated Workspace identity:

- `POST /v1/case-studies/ensure`: reconcile the caller's tenant; called server-side by signup/selection.
- `GET /v1/case-studies`: registered product identities for the caller's tenant.
- `GET /v1/case-studies/{product}`: all shared and product figures.
- `GET /v1/case-studies/clients?offset=0&limit=100`: founder-only paginated index, including clients without products; `has_more` indicates another page.
- Founder reads may supply `tenant_id`; another tenant receives 403. Reads do not create arbitrary client identities.

Browser equivalents are `/api/case-studies` GET routes. The browser cannot invoke `ensure` or supply Tank credentials/caller headers. Reports accept inclusive `start=YYYY-MM-DD&end=YYYY-MM-DD` UTC dates, default to the last 30 days, and permit up to 366 days. Reversed/future-ending periods are refused. Report reads use a repeatable-read transaction. Model identities, prompts and source documents are not returned.

## Fixed figures and sources

Exact IDs, units, types and bins are defined in [tank/case_study_templates.py:18](../../tank/case_study_templates.py#L18). The table below covers the entire founder list; there are no additional figures. Missing-source figures are still present.

| Section | Figures | Source and meaning |
| --- | --- | --- |
| Tank | Spend; savings vs baseline; cost per task; cache hits; work by code/cache/model; graduation progress | CORE proof receipts and conservative eligible savings; tenant-scoped judged shadows. Spend includes known actual costs, with unknown calls separately counted. Tasks are distinct task IDs, with standalone receipts counted when unlinked. Vendor fees are not model calls. Graduation is sample progress against policy target for the most-sampled candidate per task; agreement/threshold are separate metadata, not a claim of promotion. Only judged evidence recorded by cutoff counts. |
| Base | Verified records; cost per verified record; measured accuracy and interval; confidence histogram; records by state; comparison vs Apollo | `tank.base_record_results`, tenant-linked ledger receipts, `agent_base.records.confidence`, Apollo imports. Reuses `base_metrics.latest`, `flags`, `cost_rows`, `compare`. Latest done result per licence with verified contact evidence; known attempted-record cost divided by verified count, unknown costs separately counted. Stale/missing confidence has its own bin. Apollo covers imports in period and preserves saved comparison snapshots. Optional #390 uses the latest reviewed audit and existing `base_audit.measure`, returning percent, lower/upper interval, sample/reviewed/resolved/unsure counts. |
| Tiger | Watched pages; checks; changes; alerts sent; price-change histogram; detection time | Enabled watchlist pages (current snapshot), observations, alerts and mail marked sent in period. Price bands use percentage change from a positive known before-price; invalid values are unmeasured metadata. Detection-time gap below. |
| Market Lab | Questions answered; sources cited; calibration; active feeds | Saved nonempty `agent_market_lab.reports` and citation arrays in period. Calibration/feed ownership gaps below. |
| Rig | Searches; no results; setups built; sent quotes; estimate/invoice conversions; most-searched products | `agent_rig.widget_counts`, generated setups retained in `agent_rig.answers`, `agent_rig.quotes.sent_at`. Setups lack creation timestamps: explicitly `scope=current_retained_setups`, not a historical count of every build. Conversion/product-intent gaps below. |
| Zenas | Questions; cited answers; criminal refusals; sources per answer; drafts | Saved `agent_zenas.documents`: memos/with citations, citation count per memo, contract drafts. Scope explicitly limits counts to saved matter answers/drafts; unsaved conversational answers are not recorded here. |
| Trigger | Drafts; checker issues per draft; acceptance rate; voice-rule hits | Delivered `trigger.write` receipts, accepted/rejected feedback, confirmed write-card checker reports linked to this tenant's receipts. Duplicate cards are deduplicated. Acceptance denominator is reviewed drafts. Checker coverage/truncation are metadata; voice hits count retained findings tagged `voice`. |
| Tisan | Sites; visual-check scores | Distinct successful completed scaffold slugs in `agent_tisan.jobs`; visual-score gap below. |
| Radix | Scans; findings by severity | Completed scan jobs and findings in `agent_radix`, filtered by tenant/period. Unknown severities have their own bin. |
| Autumbra | Checks; incidents; shields | Zero until real client production evidence exists. Platform Watch and fixture-edge Enforce totals excluded. Shared Tank figures still use actual tenant/product receipts. |

Ranked lists are empty until real keys exist. Histograms contain every declared band at zero or its measured value. Tisan's series contains every date in the requested period even without scores. Metadata distinguishes `missing_source` from a recorded zero; this is API data, not page copy.

## Missing sources returning zero

- `base.measured_accuracy`: #390 is not merged in the starting main. Optional reader targets its saved audit/measurement contract. The integration test stubs that contract, not a live audit; no interval is invented.
- `tiger.time_to_detect`: no recorded time at which the seller actually changed the page; scheduled check intervals are not detection latency.
- `market_lab.calibration`: outcomes exist but predicted confidence is not persisted. `market_lab.active_feeds`: global feed sources have no tenant subscription mapping.
- `rig.quotes_converted`: no confirmed estimate/invoice conversion record. `rig.most_searched_products`: saved result IDs identify returned matches, not shopper intent.
- `zenas.criminal_questions_refused`: refusal occurs before a durable question record is saved.
- `tisan.visual_check_scores`: stored checks are pass/fail, with no numeric visual scores.
- All three Autumbra figures: global platform monitoring and per-client `fixture_edge` receipts are not client production evidence.

Other product tables may be absent on a box; those figures still appear at zero. No external service fills reporting gaps. The partial coverage of retained Rig setups, saved Zenas documents and truncated Trigger findings is explicit above and in response metadata.

## Commands and proof

All checks used the cloud workspace and disposable PostgreSQL at `127.0.0.1:55442`. Fixture data stayed in disposable local databases, which tests delete. No production endpoint or GitHub API was called. No model checked this work.

From the repository root:

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55442/postgres /tmp/command-repo-venv/bin/python -m pytest -q tests/test_case_study_reports.py tests/test_secrets.py tests/test_tank_boots.py tests/test_tank_one_door.py tests/test_core1_proof.py --tb=short
```

**76 passed, 6 existing warnings, 45.97 seconds.** [Full output](test-output.txt). Includes 21 report checks: complete zeros, tenant/product/period isolation, added product, repeated migration/registration, actual product schemas, Base/Apollo, Tiger band boundaries/sent mail, Trigger checker results, CORE savings parity, graduation cutoffs, late room provisioning, restricted room role, founder access, optional #390 projection. The real Tank boot check starts the actual application twice on the same empty database.

```sh
/tmp/command-repo-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
node tests/case_study_reports/workspace.cjs
```

Ruff: **All checks passed**; diff: **exit 0**; Workspace executable contract: **PASS: existing signup and membership registration, two tenants, founder access, forged identity/path refusal, no-store and empty error bodies.** The final registration failure path contains no page wording.

From `workspace/`:

```sh
node node_modules/typescript/bin/tsc --noEmit
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy node node_modules/next/dist/bin/next build
```

Typecheck: **exit 0**. Next build: **exit 0**, including `/api/case-studies/[[...path]]`. [Build output](workspace-build.txt). Clerk uses the repository CI's dummy configuration, not real credentials.

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55442/postgres /tmp/command-repo-venv/bin/python tests/case_study_reports/local_proof.py
```

**Exit 0.** [Real HTTP responses and startup/request tail](real-tank.txt): both clients start at zero; a recorded $2 local fixture receipt changes only A; B stays at $0; A requesting B receives 403; founder reads B and sees both identities. This starts `uvicorn main:app`, not a stand-in. Expected notices identify unavailable local Redis/Base-room services; startup, job and shutdown succeed. No model or external service is called by the report job.

There is no report page or screenshot of a live founder test: screens await Figma, and the independent assessor owns live checks. Offline results do not claim live acceptance.

## Exact assessor check after deployment

Use existing real tenant memberships/products; do not upload the local fixtures. Sign in through the existing flow and open **https://app.tervory.com/api/case-studies/clients** as founder. Copy a returned `tenant_id`; open **https://app.tervory.com/api/case-studies?tenant_id=THE_RETURNED_ID**. For a listed product, open **https://app.tervory.com/api/case-studies/base?tenant_id=THE_RETURNED_ID** (replace `base` with the listed product), click the browser's **Reload**, and check every fixed figure, including zeros. Optional dates: `&start=2026-10-01&end=2026-10-28`.

In the client's session, open **https://app.tervory.com/api/case-studies/base** for its own Base report. Set `tenant_id` to another real client's ID and **Reload**: expect an empty 403. Founder may read both. After adding a product through the existing approved product-grant flow, **Reload https://app.tervory.com/api/case-studies**, then that product's report: it must appear once, complete. There is no new page button to click.
