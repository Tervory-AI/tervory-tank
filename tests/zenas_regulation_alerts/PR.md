# Daily civil-law changes and approved tenant email alerts

Zenas already refreshes its law pool nightly but did not compare tenant watches or deliver changes. This branch adds durable watch baselines, change records, Tank summaries and a claimed SMTP outbox to the existing regional nightly job. The saved Federal Register response produces exactly one email in the local test mailbox.

**Draft; the complete brief is blocked on LegiScan authentication.** The available repository client places its credential in a URL. The official API and manual returned HTTP 403 (`error code: 1010`) from this cloud environment. A documented header/body authentication method is still missing. No authentication scheme was guessed: this connector stays `not_configured`, including when its setting is present. Setting the key alone will not enable LegiScan in this version. The other connectors and delivery path are implemented. Founder live acceptance has not happened.

Branch: `codex/zenas-regulation-alerts`. Latest main merged: `93134ec`. Application/test code tested: `76b143a`; subsequent commits add the already-tested dependency pin, evidence and this description. Claude opens the draft PR; the founder merges. No GitHub API, Actions rerun, deployment, live email, production SQL, page change or model inference was used during this work.

## What changed (file and line)

| File / starting line | Change |
| --- | --- |
| `agents/zenas/core/regulation_store.py:11`, `:73` | Additive/idempotent tables for tenant watches and changes; atomic snapshot/record transaction, regional job lock, persistent mail claims, rejection backoff, sent/uncertain receipts. Memory double is test-only. |
| `agents/zenas/core/regulation_sources.py:143`, `:367` | Current Federal Register listings, whole eCFR parts, Congress bill updates, public EUR-Lex SPARQL, and completed regional Laws.Africa versions including the minimum Acts. Follow and validate paging; source outages never commit partial snapshots. |
| `agents/zenas/core/regulations.py:34`, `:53`, `:69`, `:102`, `:179` | Civil scope checks, the approved email formatter, tenant-scoped `zenas.plain_language` Tank route, daily change comparison, summary persistence and mail dispatch. Reuses the #372 notice constant. |
| `agents/zenas/core/regulation_api.py:35`; `agents/zenas/app.py:285` | Internal watch creation/listing/enabling and change-list routes. Check the room key, stored tenant home and this box's region before reading/writing. |
| `tank/main.py:3241`, `:3409` | Allow the watch/change paths in the existing regional proxy and supply the existing Zenas room credential by name. No run-route, queue, cache or policy changes. |
| `agents/zenas/pool/nightly.py:590` | Run alerts after source updates in the existing scheduled command. Fixture mode never dispatches production alerts. |
| `agents/tiger/alert_email.py:45`, `:126` | Permit `ZENAS` settings and message IDs in the existing mail implementation. Tiger remains the default and retains its wording and behavior. |
| `agents/zenas/Dockerfile:20`; `agents/zenas/pool/Dockerfile:17` | Include the existing Tiger dispatcher, Rig SMTP transport and chassis client. No new SMTP implementation. |
| `agents/zenas/docker-compose.yml:25`; `agents/zenas/docker-compose.za.yml:32`; `.env.example:425` | Named SMTP settings; Congress/LegiScan settings only in Boston. No values supplied. |
| `tank/requirements-dev.txt` (final two lines) | Pin `pgserver==0.1.4` for temporary local Postgres transaction/API tests without a production DSN or key. Test dependency only; absent optional binary is reported as a skip. |
| `tests/zenas_regulation_alerts/test_alerts.py:96`, `:523`, `:568`; `test_integrations.py:17` | Actual source parsers, Tank boundary, SMTP catcher, Postgres restart/claim behavior, real room routes, real Tank proxy, nightly hook and Laws.Africa sync integration. |
| `agents/zenas/pool/fixtures/saved/eur-lex/consumer-rights.json` | Real public SPARQL response recorded for offline replay. Existing Federal Register/eCFR pool responses and #382 recordings are reused. |

## Source behavior and references

- Federal Register: its existing adapter parses paged `/api/v1/documents.json` results. Each watch sends its topic and an inclusive publication-date window; outage recovery starts from the last successful run with a two-day overlap. Proposed-rule status is retained in the summary evidence. [API](https://www.federalregister.gov/developers/documentation/api/v1).
- eCFR: the existing title-date lookup and XML parser supply the watched title/part. Compare the complete part so removals and authority changes count. A new issue date with unchanged text does not create a false change. Links use the official dated `/on/DATE/` representation. [API](https://www.ecfr.gov/developers/documentation/api/v1).
- Congress.gov: `CONGRESS_GOV_API_KEY` is sent in `X-Api-Key`, never in a URL. Follow `pagination.next` with host validation and key-query removal; redirects are disabled. Retain bill/latest-action metadata, without claiming a bill is enacted law. [Header authentication](https://api.data.gov/docs/developer-manual/#http-header), [bill endpoint documentation](https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/BillEndpoint.md).
- EUR-Lex: public [SPARQL endpoint](https://publications.europa.eu/webapi/rdf/sparql), no key. Use the real `expression_belongs_to_work` relationship and `application/sparql-results+json` response type. Compare matching English legal-act metadata and use its CELEX link/date. The final read-only query for `consumer rights` returned one real row, Directive 2011/83/EU, saved in the fixture above. This is a metadata/publication alert, not a claim to have compared the full text of each EU act.
- Laws.Africa: reuse #382's completed sync and official version links/attribution. Read the aggregate and minimum-Act source IDs only on ZA, under the existing sync lock. No token means no read/fetch; a failed/in-progress sync cannot produce a new snapshot. No new API traffic or pacing implementation is added. [Content API](https://developers.laws.africa/content-api/content-api.md).
- LegiScan: blocked as described above. Relevant [official manual](https://legiscan.com/misc/LegiScan_API_User_Manual.pdf) and [API](https://api.legiscan.com/) both returned 403. The test explicitly proves it remains off even with the setting-name marker.

## Approved email, word for word

Subject: `Law change: {title}`

Body, one item per line:
```
{title}
{summary}
Source: {link}
Date: {date}
Zenas provides legal information, not legal advice.
```

The summary is the only generated item. Detection, deduplication, region checks, criminal refusal, URLs, dates, attribution and the notice are code. Runtime summaries use Tank's existing cheapest Zenas plain-language policy, inside the watching tenant. Offline tests substitute a recorded source excerpt; they make no model call.

## Settings and deployment names

Grok's existing resources: `agent-zenas` in Boston; `agent-zenas-za` on ZA. The documented `zenas-pool-nightly` tasks already run `python -c "from agents.zenas.pool.nightly import main; main()"` at `0 2 * * *` on each region. No task was created or changed in Coolify during this work.

Both regional resources need their own `ZENAS_SMTP_HOST`, `ZENAS_SMTP_PORT`, `ZENAS_SMTP_USER`, `ZENAS_SMTP_PASSWORD`, `ZENAS_SMTP_FROM`, `ZENAS_SMTP_ALERT_ADDRESSES`. The last setting is an exact tenant UUID-to-recipient JSON mapping, as in Tiger; there is no wildcard or default recipient. Missing/invalid settings keep the mail pending. TLS verification uses the unchanged Rig transport.

Boston: `CONGRESS_GOV_API_KEY`; `LEGISCAN_API_KEY` remains blocked. ZA only: existing `LAWS_AFRICA_API_TOKEN`. Existing `DATABASE_URL`, `TANK_REGION`, `TANK_URL`, room `TANK_KEY` and Tank's matching `TANK_KEY_ZENAS` are reused. No setting value was read, supplied or printed.

## Exact checks and results

Cloud only: `/workspace/tervory-tank`. The main comparison used a detached worktree at `/workspace/zenas-regulation-alerts-main`, commit `93134ec`. New tests create temporary local Postgres instances and the existing loopback SMTP catcher. The catcher's STARTTLS boundary is stubbed without creating a key/certificate; the unchanged mailer still requests a verifying TLS context. The offline runner rejects all non-loopback socket connections.

Environment dependency command actually run:
```
/workspace/.tervory-cloud/venv/bin/pip install aiosmtpd==1.4.6 pgserver==0.1.4
```
Result: installed successfully. `aiosmtpd` was already pinned in the repository; `pgserver` is now pinned for these tests.

Focused command actually run:
```
PYTHONPATH=.:agents/_chassis:tests ZENAS_ALERT_EVIDENCE_DIR=/tmp/zenas-alerts-evidence /workspace/.tervory-cloud/venv/bin/python tests/zenas_regulation_alerts/offline.py -q tests/zenas_regulation_alerts tests/test_tiger_alert_email.py
```
Result: **64 passed, 1 skipped**. The skip is Tiger's existing external-DSN test; the new Postgres tests ran. Output: `evidence/focused-tests.txt`. This includes one-time detection, complete paging, source failures, disabled keyed feeds, civil/criminal scope, retained notices, mail rejection/uncertainty, tenant isolation, Postgres restart, routing, eCFR removals and the ZA version/date/source integration.

Final branch regression command actually run:
```
PATH=/workspace/.tervory-cloud/node/bin:$PATH PYTHONPATH=.:agents/_chassis:tests /workspace/.tervory-cloud/venv/bin/python tests/zenas_regulation_alerts/offline.py -q tests/test_zenas*.py tests/test_tank_zenas*.py tests/test_tiger_alert_email.py tests/zenas_za_laws_africa tests/zenas_docassemble
```
Result: **675 passed, 5 skipped**. Output: `evidence/branch-tests.txt`.

Main comparison command actually run, from the detached worktree:
```
PATH=/workspace/.tervory-cloud/node/bin:$PATH PYTHONPATH=.:agents/_chassis:tests /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-alerts-offline.py -q tests/test_zenas*.py tests/test_tank_zenas*.py tests/test_tiger_alert_email.py tests/zenas_za_laws_africa tests/zenas_docassemble
```
The temporary runner has the same loopback-only socket guard as committed `offline.py`. Result: **674 passed, 5 skipped, 1 failed**. Output: `evidence/main-tests.txt`.

| Failing test / check | Main `93134ec` | This branch |
| --- | --- | --- |
| `tests/test_tiger_alert_email.py::test_email_copy_matches_actual_workspace_formatter` | Failed because this detached worktree lacks `workspace/node_modules/typescript`. This is an environment difference, not evidence of a main code defect. | Passed with the existing workspace dependency. |
| Other tests in the identical regression selection | No failures | No failures |
| Model boundary and secret checks | 29 passed | 29 passed |
| GitHub `ci / tank`, `tisan-site / gate` | Founder-reported existing failures; full CI not rerun here. | Full CI not run/retried; no claim these checks are green. |

The same boundary command was run in both worktrees:
```
PYTHONPATH=.:agents/_chassis:tests /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-alerts-offline.py -q tests/test_tank_one_door.py tests/test_secrets.py
```
Outputs: `evidence/main-boundaries.txt`, `evidence/branch-boundaries.txt`. Existing main tests/files were not changed to make unrelated failures pass.

`evidence/static-checks.txt` contains the exact `ruff check`, `python -m py_compile` and `git diff --check founder/main...HEAD` invocations and exit codes: all zero. Archived text logs have trailing whitespace removed. The initial focused run exposed the retry timestamp's SQL type; the corrected query passed the real Postgres retry test. The final source/fixture changes also passed the focused suite.

## Decisions I made

- First successful run establishes the watch baseline without emailing old publications. Subsequent successful daily comparisons create durable changes once. A source outage leaves its prior snapshot intact.
- Keep a previous document version in each change so Tank can explain a supported difference. A publication absent from a rolling listing is not treated as a repeal. eCFR compares its complete watched part to detect removed sections.
- Reuse Tiger/Rig mail delivery, settings structure, explicit-rejection retry and uncertain-send behavior. Stable message IDs and claimed receipts prevent routine duplicates; uncertain/sending receipts are not automatically replayed.
- Put watch APIs behind the existing Tank regional proxy. No Workspace or client wording/layout was added. The task's fixture-driven test-mailbox acceptance option supplies the proof without inventing a watch page.
- Reuse the existing `zenas.plain_language` policy and #372 notice; add no model/provider or policy row. Missing Tank output leaves the change waiting for a later scheduled run.
- Add only a test dependency for local Postgres, plus the Docker COPY/settings wiring needed to run the feature on the existing resources.
- `zenas.regulation.changed` publication is not wired: this main has no merged event-publisher interface for the conditional job-2 integration. No substitute event bus was invented.
- Keep LegiScan off until its non-URL authentication method is documented. This is an unresolved brief item, not a completed integration.

## Proof and exact acceptance steps

The committed mailbox receipt is `evidence/local-mailbox.json`, with the actual received MIME message in `evidence/local-mailbox.eml`:

- Tenant: `19e2718c-6811-4d49-ad20-46fbe7e5f15a`
- Watch: `6219230c-db37-436c-860c-a66adb473cbe`
- Change: `a2e36ce8-367d-4852-8b65-cf5d5af75ba4`
- Subject: `Law change: Low-Value Shipments`
- Received messages after the new document and repeated daily runs: **1**; stored mail state: `sent`.
- Source/date: [Low-Value Shipments](https://www.federalregister.gov/documents/2026/10/08/2026-20650/low-value-shipments), `2026-10-08`.

To reproduce the approved offline acceptance: run the focused command above. Open **`tests/zenas_regulation_alerts/evidence/local-mailbox.eml`** in an email viewer, open **“Law change: Low-Value Shipments”**, and click its **Source** link. Check the five body lines against the approved template, including the unchanged notice. The JSON receipt records the same watch/change IDs and the single delivery. This is fixture-driven mailbox proof, not a founder live screenshot.

For Grok/assessor after merge and regional deployment: use the existing authenticated Tank client to POST `/v1/zenas/regulations/watches` with the real `tenant_id`, `home_region`, `source: "federal-register"`, `topic: "customs"`, and `options: {}`. The same client can GET `/v1/zenas/regulations/watches` and `/v1/zenas/regulations/changes` with that tenant/home to verify persistence. The first successful nightly run establishes the baseline; the next matching publication should produce one change and one email. No raw key-bearing command is needed in the PR.

**Founder browser screenshots were not supplied and live acceptance is unverified.** There is no newly approved watch-page frame, so no watch controls were added to a client page. For the live proof, open the configured tenant's existing email inbox, open **“Law change: [the real publication title]”**, and click **Source**; it must open that official publication and the message must end with **“Zenas provides legal information, not legal advice.”** The founder's assessor records that screenshot. Keep this PR a draft.
