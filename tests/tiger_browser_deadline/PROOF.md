# Tiger audit and browser deadline proof — 30 October 2026

As of 15:12:46 PDT / 22:12:46 UTC. Branch `codex/tiger-rig-discovery-20261030`, PR #458. Source reviewed at `0df8ba6bc735906bb12db586c13cb8aaf8d3b433`; later evidence-only commits do not alter source.

## Actual operational state

AmmoSync identity was independently verified through the installed Workspace server's Clerk organisation directory and the existing `workspace/lib/tenant.ts` UUIDv5/alias algorithm: organisation `org_3KtFUVOxBSh3P2JDYh23RC8e75u` named AmmoSync maps to `137bd08c-4a37-51a0-bce7-d636a196b814`. Service authentication stayed inside the installed process; no secret values were displayed or copied.

The founder explicitly authorized choosing any real public products and configuring watches. Fourteen real Pololu product watches were created with the existing API, after checking for duplicates. Each is enabled hourly, price/stock alerts on, G5 types off for this cohort; existing organisation email routing was not changed. Labels came from actual product pages, not invented copy. Pololu robots permits `/product/`; actual Tiger browser reads returned HTTP 200 without challenge. Adafruit returned 403 and Pimoroni challenged the browser, so neither was bypassed or used for watches. Remaining Pololu pages were validated with public HTTP 200 reads at ten-second spacing and read normally by the scheduler, without extra jobs.

At the snapshot: **14 watches, 13 with genuine readings, zero alerts**. See [machine-readable snapshot](live-audit-20261030.json), including observed prices/currencies/methods and the retained first failed job. No email delivery/retry/deduplication success can be inferred from zero alerts.

Creation stopped immediately on the coordinator's instruction. His earlier nine-watch count was an older snapshot: fourteen had already been created when that instruction arrived. The configuration exec alone was terminated (exit 143); no service, watch, queued job or historical failure was killed, disabled or cleared.

**The 20-page/48-hour run has not started.** There is no valid 20-page cohort start/end to report. Existing hourly watches continue under their normal scheduler. The five-page live milestone has real configured targets, but still awaits a real changed-price/stock email and founder acceptance. The table's next times are derived as latest observation + 1 hour from existing dispatch logic, not an independently stored scheduler timestamp; the minute dispatch and queue can run later.

| Watch ID | Pololu product | Configured UTC | Latest observation UTC | Next due, derived UTC |
|---|---|---|---|---|
| 484fb656-81e4-4278-8112-78d67b1caa6e | 3036 | 2026-10-30T21:57:39.952408+00:00 | 2026-10-30T22:03:57.064251+00:00 | 2026-10-30T23:03:57.064251+00:00 |
| c67d0ac0-10b1-4291-849b-8d619bef8313 | 3037 | 2026-10-30T22:01:03.118413+00:00 | 2026-10-30T22:04:35.170983+00:00 | 2026-10-30T23:04:35.170983+00:00 |
| 41ef2547-e50d-45c2-8233-b29209d440da | 3038 | 2026-10-30T22:02:28.024888+00:00 | 2026-10-30T22:09:12.280024+00:00 | 2026-10-30T23:09:12.280024+00:00 |
| 4d75308e-66c4-4e76-bc5c-d58d68b83949 | 3047 | 2026-10-30T21:58:15.447706+00:00 | 2026-10-30T22:02:36.536687+00:00 | 2026-10-30T23:02:36.536687+00:00 |
| 57d1005c-216e-41f7-aaa6-0be5343b75d5 | 3048 | 2026-10-30T22:01:13.881853+00:00 | 2026-10-30T22:05:10.836730+00:00 | 2026-10-30T23:05:10.836730+00:00 |
| 388c7eed-0125-41e8-8dff-c9912e6e1a6e | 3049 | 2026-10-30T22:02:38.583334+00:00 | No reading yet | Not established |
| fea0279c-9191-4b6b-8feb-bb164a33c7ca | 4788 | 2026-10-30T22:01:45.710562+00:00 | 2026-10-30T22:05:48.651318+00:00 | 2026-10-30T23:05:48.651318+00:00 |
| ce71b413-f757-4290-82fc-718072a9b682 | 4789 | 2026-10-30T22:01:56.117923+00:00 | 2026-10-30T22:06:23.148962+00:00 | 2026-10-30T23:06:23.148962+00:00 |
| b011f969-bfe4-4bf5-b55d-46180b7b1678 | 5204 | 2026-10-30T22:00:41.333202+00:00 | 2026-10-30T22:03:09.476166+00:00 | 2026-10-30T23:03:09.476166+00:00 |
| 533912ea-7258-4283-b651-005531c44f3b | 5205 | 2026-10-30T22:00:51.998384+00:00 | 2026-10-30T22:06:59.960624+00:00 | 2026-10-30T23:06:59.960624+00:00 |
| 24b9d960-b920-4ae6-94f1-5441e982e7fc | 5206 | 2026-10-30T22:01:24.500929+00:00 | 2026-10-30T22:07:34.283310+00:00 | 2026-10-30T23:07:34.283310+00:00 |
| 2a31f68d-cfdb-4b5d-9645-a00f1c31eb5c | 5207 | 2026-10-30T22:01:35.174805+00:00 | 2026-10-30T22:08:09.981532+00:00 | 2026-10-30T23:08:09.981532+00:00 |
| 4591f281-883f-446a-9052-50f2411443f3 | 5208 | 2026-10-30T22:02:06.794210+00:00 | 2026-10-30T22:09:45.811237+00:00 | 2026-10-30T23:09:45.811237+00:00 |
| f1f1e516-216b-4a4e-810c-f5d28a16b9e3 | 5209 | 2026-10-30T22:02:17.420915+00:00 | 2026-10-30T22:09:55.819295+00:00 | 2026-10-30T23:09:55.819295+00:00 |

## Distinct failures and recovery

1. Discovery originally failed because Tank's `TANK_KEY_TIGER` was empty; direct existing discovery GET returned 401. Repository forwarding/authentication were correct. Founder reported binding Tank to the existing shared project key and redeploying at 10:27 PDT / 17:27 UTC, without exposing values. Independent bounded samples confirmed all ten jobs created 10:27–10:36 PDT done with `tenants: 5`, and ten consecutive jobs at 11:31–11:40 PDT likewise done (nine attempts 1; one attempts 2). This proves returned tenant count, not the identity of those five tenants or email delivery. The approximately 2,800 historical failures remain founder-reported, not independently counted. The short DNS interruption during a separate stack rollout is distinct.
2. SMTP configuration/authentication/healthy redeploy are founder-verified. An earlier nonempty runtime `TIGER_SMTP_PORT` boolean reflected a default/runtime value, not proof that Coolify's field was filled; founder corrected that field too. No credentials were retested and no test email was sent.
3. Browser preflights overlapped normal checks. Tiger waits 50 seconds; browser `max_ms` only bounds navigation, not the tenant/site lock, extraction, evidence or cleanup; the gateway can wait 300 seconds. Browser history showed task `0140a609-7a83-48da-9956-e1aeae29a74d` succeeding at 21:58:54 UTC after its caller timed out at 21:58:37, and its retry succeeding at 22:00:19 after the caller timed out at 21:59:43. This demonstrates late work ahead of retries. Independent preflights were stopped; subsequent normal checks saved actual JSON-LD readings. The initial job still shows failed after three ReadTimeout attempts; its later successful normal reading does not erase it.

## Source change and regression

- `agents/tiger/app.py:66` and `:82`: send an optional 45,000 ms browser request budget on both requests, retaining the 50-second HTTP client timeout.
- `agents/_brain/browser.py`: Page request budget; scoped request expiry includes tenant/site admission and visit. Expired queued work never starts later. Cancellation unwinds the active visit instead of leaving it ahead of retries. Existing 503 wording is reused; there is no new UI copy or successful reading manufactured from a timeout.
- `cleanup_visit`: budgeted cleanup skips cookie persistence after cancellation, limits each of storage/browser close/driver exit to one second, and attempts later cleanup in nested finally blocks even after failure. Manager entry is inside protected startup; admission and politeness timestamps unwind on interrupted entry/launch too. No detached cleanup-step tasks are created. Unbudgeted clients retain existing step timing.
- `tests/test_tiger_browser_deadline.py`: queued expiry, active expiry, cancellation, independent tenant, unchanged successful result, public/private request forwarding; then actual visit/_visit resource doubles for stalled storage/close/driver exit and interrupted manager entry/browser launch/read.

Reviewer independently reproduced the original cleanup gap, then cleared the corrected source after 12 tests passed in 5.76 seconds. **Limit:** timeouts rely on cooperative asynchronous operations; resource teardown is best effort, not a hard OS process-kill guarantee or proof against a blocked event loop. Existing intentional human-held sessions are unchanged. No global timeout increase, retry-policy change, site-limit bypass or live source patch occurred. Both Tiger agent and Tiger browser require normal deployment of this PR after founder merge; branch tests are not live deployment proof.

## Exact verification commands and results

Working directory `/tmp/tervory-tiger-discovery-20261030` on Boston:

```sh
PYTHONPATH=tank /tmp/tervory-rls-python/bin/python -m pytest -q tests/test_tiger_browser_deadline.py
```

Initial request-deadline reproduction: 2 failed, 2 passed (3.57s). After initial deadline fix: 4 passed (2.38s). Python 3.14 broader tests then hit an incompatible pre-existing selectolax 1.0 environment. An attempted isolated target installation of repo-pinned selectolax 0.3.27 failed because that Python had no wheel/compiler. No shared environment was changed. The first Python 3.12 priority environment then lacked Playwright/PDF/Workspace dependencies (111 passed, 3 failed, 1 setup error), so the already installed compatible merge-test environment was used.

```sh
ln -s /tmp/tervory-tenant-rls/workspace/node_modules workspace/node_modules
PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/google-chrome-stable /tmp/tervory-rls-merge-python/bin/python -m pytest -q tests/test_tiger_browser_deadline.py tests/test_tiger_works.py tests/test_access1.py tests/test_access1_review.py tests/test_agent1_browser.py
rm workspace/node_modules
```

Initial affected suite: 115 passed, also 115 passed after conflict-free merge of main `f0602ad`. After review cleanup fix: **121 passed, 12 existing warnings, 14.03s**, including real local Chromium. Temporary ignored dependency link removed; no source dependency edits.

```sh
PYTHONPATH=tank /tmp/tervory-rls-merge-python/bin/python -m pytest -q tests/test_tiger_browser_deadline.py -k actual_visit
```

Pre-cleanup-fix reproduction: 5 failed, 1 passed (6.78s). Then:

```sh
PYTHONPATH=tank /tmp/tervory-rls-merge-python/bin/python -m pytest -q tests/test_tiger_browser_deadline.py
/tmp/tervory-rls-merge-python/bin/python -m ruff check --select E9,F agents/_brain/browser.py tests/test_tiger_browser_deadline.py
git diff --check
```

12 passed (5.75s); Ruff passed; whitespace passed. Source and evidence files committed/pushed individually on the same branch. Hosted CI and separate review state belong to the current PR checks; no pending check is claimed passed.

Read-only live evidence used existing `GET /watchlist?tenant_id=...`, `GET /observations?tenant_id=...&url=...`, `GET /alerts?tenant_id=...` and `GET /jobs/{id}?tenant_id=...` inside the existing Tiger service, with known tenant scope. Sanitized Docker JSON logs supplied existing job IDs, and the browser's existing tenant history supplied completion timestamps. No SQL or custom production queries were used. A later snapshot refresh failed transiently and wrote no file; the successful 22:12:46 UTC snapshot contains no read errors.

## Remaining Tiger brief items — no blanket completion claim

| Item | Verified implementation/evidence | Still required |
|---|---|---|
| URL watchlist, per-watch schedule/history and price/stock panel | Existing merged #335; normal watch API and genuine observations now exercised | Founder UI walkthrough last; CSV watch import/per-tenant watch-count limit not independently established in this audit |
| Price/stock email #365 | Existing source uses tenant mapping, stable Message-ID, atomic outbox, preference checks, retry/backoff, uncertain-send reconciliation; historical local catcher proof | Real changed-price/stock inbox delivery; live mail retry/dedupe. Ambiguous SMTP acceptance is held, never blindly replayed |
| G5 new product/below cost/market gap #418 | Existing deterministic tenant-scoped source and historical 349 passed, 1 skipped; existing email lines; Workspace filters all three kinds at model.ts:268 | Real tenant-owned product/cost/competitor matches and actual live transitions not exercised; approved Figma treatment remains pending and types stay hidden |
| Gold labels | Existing skipped `test_filled_gold_pages_match_exactly` explicitly requires human labels | 100-page manually labelled gold evidence remains absent; not invented |
| Rig discovery #386 | Configuration root cause resolved; repeated tenant-count successes independently verified | Count of five does not establish real catalogue inputs for each tenant or end-to-end Rig price update acceptance |
| Browser lifecycle defect | PR #458 source reviewed; 121 affected tests pass | Hosted CI, founder merge, normal deployment and post-deploy checks |
| 20-page/48-hour endurance | Fourteen legitimate hourly watches retained; exact IDs/readings in snapshot | Six further watches only after reliability gate; actual 20-page start/end and complete checks/change/failure totals |
| Founder DONE condition | No invented acceptance | Founder sees the real alert/workflow in his own browser/inbox, LAST; no founder screenshots claimed |

No model calls were used to select pages, read prices, create watches or check this work. Extraction and OCR are existing code/Tesseract. No sign-in, pricing, keys, billing, UI, production SQL or secret values were changed.
