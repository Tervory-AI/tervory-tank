# Market Lab founder acceptance

Branch `codex/market-lab-acceptance`, from `origin/main` at
`475597ed` (ML5, ML6 and Wave 4 included). Sign in as founder and select the
intended workspace. All /chats commands below are entered at
https://app.tervory.com/chats. Click the proposed card's **Confirm** where stated.
Use a disposable acceptance workspace for uploads, removals and alert opt-ins.

Settings names are copied from `docs/ops/FOUNDER-SETTINGS.md` in
`origin/claude/founder-settings` (PR #657); values never belong in this sheet.
"none" means no additional founder setting for that row. Existing deployment
identity/corridor configuration is assumed; no new setting is introduced here.
Mail rows use the Market Lab mail settings, including the existing tenant to
recipient mapping in MARKET_LAB_SMTP_ALERT_ADDRESSES.

Each Rxx row has exactly one `test_Rxx` in
`tests/acceptance/test_market_lab.py`. Fixtures have stable expected numbers;
live publisher data, UUIDs, counts and dates vary. Compare real results with
the opened stored source, rather than expecting fixture numbers in production.
Where fixtures or report jobs are required, prepare the described inputs through
the existing upload/job path; do not inject fixture data into a real tenant.
Offline tests prove the shipped handler/model paths; they do not claim deployed
browser clicks, a real founder email or production publisher availability.

| Row | Where | What he does | What he should see | Setting it needs |
| --- | --- | --- | --- | --- |
| R01 | https://app.tervory.com/market-lab | Open Overview with no successful stored checks. | On count 0; no invented feed cards; Not refreshed yet. | none |
| R02 | https://app.tervory.com/market-lab | Click Refresh feeds; wait, reload. Open each successful source. | Each successful feed has stored rows and a document; only own tenant rows appear. Offline: every engine feed has rows; fixture records are excluded from normal reads. | none |
| R03 | https://app.tervory.com/market-lab | Leave EIA_API_KEY unset; refresh the EIA feed. | Off, needs key; no request for the keyed feed. Setting a key alone must not count as a successful fetch. | none |
| R04 | https://app.tervory.com/market-lab | After a successful source check, simulate a failed next check; refresh. | Feed becomes Off; old source document remains available; old figures are not reused in answers. | none |
| R05 | https://app.tervory.com/market-lab#linked | Open Linked pages after checks. | Checked pages show their saved check/change counts. Fixture UPS Not checked yet; FedEx Checked 14 Oct 2026; USPS Checked 2 Oct 2026; Port of Long Beach Opens polb.com. | none |
| R06 | https://app.tervory.com/market-lab | In Ask Market Lab enter What are the latest population figures?; follow each reference. | Each fact names its saved geography, reporting date and exact number; reference opens the same immutable row. An unrelated avocado harvest question returns no facts. | none |
| R07 | https://app.tervory.com/market-lab/sources/<document-id>?row=<row>#point-<row> | Follow a numeric citation; use source pagination. Replace placeholders with the actual citation URL. | Rows are newest first; cited original row index remains stable when opening or paging. | none |
| R08 | https://app.tervory.com/market-lab | Open Plugins → Files → Choose files; upload report.pdf containing the fixture page-2 inventory statement. Ask What was warehouse inventory?; open its citation. | 14,474 cartons / 14474 in the saved text; report.pdf · Page 2; another workspace cannot open it. | none |
| R09 | https://app.tervory.com/market-lab | Plugins → Files → Choose files; upload history.csv with date,value,unit,series and rows 2026-09-01,100,cartons,inventory and 2026-09-08,110,cartons,inventory. | Dated 100 and 110 carton source rows go through the data guard; source links open their original rows. | none |
| R10 | https://app.tervory.com/market-lab | Upload the same two rows as history.xlsx through Plugins → Files → Choose files. | The same 100 and 110 carton rows and dates as CSV; no spreadsheet serial date is shown as a market number. | none |
| R11 | https://app.tervory.com/market-lab | In Plugins → Files remove report.pdf; ask its inventory question again and revisit its old source URL. | Removed report contributes no facts; old document is unavailable. Removing a file in a different workspace changes nothing here. | none |
| R12 | https://app.tervory.com/market-lab | Open Plugins → Keys; save an existing registered supplier key; inspect the list, then reload. | Only configured/status booleans reach the browser; saved secret text is never returned. This is a status test, not proof the publisher accepted a key. | none |
| R13 | https://app.tervory.com/market-lab | Select a workspace where Market Lab vault access is disabled; open /market-lab → Plugins. | Plugins are not available yet. Ask your workspace administrator to enable them. Then keys from that vault no longer enable a feed. No secret is included in the client state. | none |
| R14 | /chats: market_lab.research | Request research on the fixture topic through the existing research action and Confirm. Open every returned citation. | Saved research claims have openable sources; made-up source links are excluded. No unsourced prose is accepted. | none |
| R15 | /chats: market_lab.warnings | Send exactly market_lab.warnings; Confirm the read card. | Warnings are own-tenant source-linked records; read receipt is model code, rung 3, $0. Offline fixture checks the exact read and tenant isolation. | none |
| R16 | /chats: market_lab.predictions | After a qualifying warning, send market_lab.predictions; Confirm. | Prediction includes frozen historical Wilson lower-bound confidence. Offline: 3/3 history yields exactly base_reliability.wilson_lower(3,3) = 0.43850296824495466, below 0.5; it is not 100%. | none |
| R17 | /chats: market_lab.predictions | Run the same qualifying warning with the Tank series/confidence connection unconfigured; read predictions. | Warning still saves; confidence is null/unknown rather than invented or an exception. | none |
| R18 | /chats: market_lab.calibration | Send market_lab.calibration; Confirm. | Hit/miss counts and measured calibration exclude unresolved, unmeasurable, duplicate and other-tenant outcomes. Offline measured curve count is exactly 1; an unresolved-only cohort has no curve. | none |
| R19 | /chats: market_lab.patterns | Send market_lab.patterns; Confirm; compare own and founder-published pair. | Only own plus same-pair published records. Fixture total 2; status client/platform; pair placeholder_pair; count 3; total hits 2; $0 receipt; no planner. | none |
| R20 | /chats: market_lab.gate | Send market_lab.gate; Confirm; compare a cohort just before and at its 90-day opening. | Fixture count 1; opening 2026-11-03T00:00:00+00:00; closed one microsecond before, open at/after; $0 receipt and no planner. | none |
| R21 | /chats: market_lab.calibration.curve | Send exactly market_lab.calibration.curve; Confirm. | Structured bins contain mean confidence, realised rate and count; fixture bins (0.1,0,1) and (0.8,1,1); tenant-scoped $0 code read. Dedicated chart awaits Figma. | none |
| R22 | /chats: market_lab.feeds | Send market_lab.feeds; Confirm; inspect an unconfigured keyed feed. | Registered key name only (fixture EIA_API_KEY), state off, rows 0; never its value. | none |
| R23 | /chats: market_lab.alerts.email | Send market_lab.alerts.email; Confirm. | Status email and cost_usd 0; tenant email_enabled true only after Confirm. | MARKET_LAB_SMTP_HOST, MARKET_LAB_SMTP_PORT, MARKET_LAB_SMTP_USER, MARKET_LAB_SMTP_PASSWORD, MARKET_LAB_SMTP_FROM, MARKET_LAB_SMTP_ALERT_ADDRESSES |
| R24 | /chats: market_lab.alerts.webhook {"url":"https://<your-public-receiver>/hooks"} | Replace receiver with your HTTPS endpoint; send; Confirm once; save the returned one-time value privately. Confirm the same card again. | The one-time value appears only on first Confirm, never thread history/logs. Repeating Confirm does not reveal the value again; delivery is tested in R26. | none |
| R25 | /chats: market_lab.alerts.off | Send market_lab.alerts.off; Confirm; run opportunities with alerts disabled. | Status off, cost_usd 0; email disabled and webhook cleared. Neither channel sends a brief. | none |
| R26 | /chats: market_lab.briefs; founder email and configured webhook receiver | Enable both alert channels first. Run/wait for the existing opportunities job; retry delivery, then read briefs. | One email and one signed webhook per report. Email subject is saved title; body only saved text and citation values; retry adds no delivery. Fixture title placeholder saved report title. | MARKET_LAB_SMTP_HOST, MARKET_LAB_SMTP_PORT, MARKET_LAB_SMTP_USER, MARKET_LAB_SMTP_PASSWORD, MARKET_LAB_SMTP_FROM, MARKET_LAB_SMTP_ALERT_ADDRESSES |
| R27 | /chats: market_lab.briefs | Run opportunities with a prediction citation from a cohort aged 89 days. Read the brief. | Both delivery channels held with a nonempty reason; no pending email. | none |
| R28 | /chats: market_lab.briefs | Send market_lab.briefs; Confirm after more than 12 saved briefs. | Only own last 12 briefs, newest first, with per-channel statuses and a $0 code receipt; no other tenant report. | none |
| R29 | /chats: market_lab.briefs; citation links in received brief | Open every citation in the next brief; compare each sentence to its source row/page/prediction. | Every saved sentence has at least one real source URL; unsupported recommendations omitted. No invented citation. | none |
| R30 | /chats: market_lab.warnings | With LegiScan configured and qualifying supply-state history, run/wait for warning evaluation. | Engrossed is an event signal; Not Engrossed and outside-region events are excluded. Duplicate snapshots do not inflate counts. Fixture CA AB 1 Engrossed count 1; measured lag history independent from weather. | LEGISCAN_API_KEY |
| R31 | /chats: market_lab.warnings | With NOAA configured and qualifying supply-state history, run/wait for warning evaluation. | Only events in observed supply states enter scoring. Fixture CA weather count 1; TX event excluded; own measured lag history, no guessed region. | NOAA_TOKEN |
| R32 | /chats: market_lab.warnings | Leave LEGISCAN_API_KEY and NOAA_TOKEN unset; run/wait for warnings. | Those two inputs produce no scored series; other warning inputs keep working; no configuration exception. | none |
| R33 | https://app.tervory.com/market-lab#quarantine | As founder open a held batch; click Release. | Only that batch is released through the room corridor; it is not retired as removed. Non-founder cannot perform the action. | none |
| R34 | https://app.tervory.com/market-lab#quarantine | As founder click Remove on a batch, then ask a question using its observations. | Removal retires lineage only after room acceptance; removed observations no longer answer questions. | none |
| R35 | https://app.tervory.com/market-lab | Open a FRED reading with FRED_API_KEY configured. Refresh and compare to the returned source. | FRED numbers are read live and never stored in the room database. No database copy of FRED observations. | FRED_API_KEY |
| R36 | https://app.tervory.com/market-lab | Leave FRED_API_KEY unset and refresh. | FRED off; needs key FRED_API_KEY; zero stored points and no fetch. Other inputs continue. | none |
| R37 | https://app.tervory.com/market-lab | Use the feed search field to search a fixture source title, then a linked page title. | Matching feeds and linked pages appear; an unrelated question has no fabricated reading. | none |
| R38 | https://app.tervory.com/market-lab | Plugins → Source links: add https://www.census.gov/data.html with a label and Weekly; use Remove to delete it. Try a private HTTP link. | Public HTTPS URL is retained exactly, listed as Weekly / Not checked yet (stored status not_checked), and disappears after Remove; a private HTTP URL is rejected. Saving a link is not a successful feed fetch. | none |
| R39 | https://app.tervory.com/market-lab | Plugins → Connections → Add connection: name placeholder connection, Server address https://placeholder.example/mcp, choose Sign in with the provider; click Add connection, then Remove. Try http://localhost/private as the next address. | Public connection metadata is listed with its exact name and URL and has_token false; Sign-in needed (stored status needs_auth) means sign-in is still needed, not a connected server. Remove succeeds. Private address rejected; no local/private connection is saved. Use your own approved public MCP server in production; the fixture does not claim it is reachable. Credentials must be in the separate sealed field, not URL text. | none |
| R40 | https://app.tervory.com/market-lab/sources/<document-id> | Open an earlier and a revised document; ask for that series. | Revision labels identify changes; only current pooled revision contributes to answers; old saved evidence is not overwritten. | none |
| R41 | https://app.tervory.com/market-lab/sources/<document-id> | Open a stored notice citation in a source that also contains figures. | Notice anchor selects its original notice row, not a numeric point with the same index; checked notice wording remains distinct from a measured change. | none |
| R42 | /chats: market_lab.briefs | Run opportunities when there is no source-backed claim; read briefs. | Empty brief held with reason no_cited_claims; unsupported product recommendation text omitted; nothing is sent. | none |
| R43 | https://app.tervory.com/market-lab | Set the registered EIA and Census keys; click Refresh feeds; open their stored source cards. | Only a successful read counts as On. Offline fixture EIA value 3.86 and Census revision value 110; exactly 2 On feeds, each with rows and its document. Live values must match the opened source. | EIA_API_KEY, CENSUS_API_KEY |

| R44 | https://app.tervory.com/market-lab/briefs/<report-id>; /chats: market_lab.briefs {"report_id":"<report-id>"} | Use your saved report id. Open detail; click Open stored source. | Saved title, text, delivery status and citations; exact stored passage opens. Removed sources cannot open; foreign report 404. Structured read includes confidence (fixture 0.75) and recorded pending → sending → sent history. | none |
| R45 | https://app.tervory.com/market-lab/calibration | Select signal kind and period. | Resolved originals only; fixture confidence 45.0%, actual 50.0%, samples 2. Separate 7-day and 30-day cohorts; curve uses returned bins. Live values follow saved outcomes. | none |
| R46 | Both H7 URLs above | Open while loading, without data, and with a failed read; retry. | Loading…; No brief selected. / No resolved predictions yet.; Brief detail could not be loaded. / Calibration could not be loaded.; Try again. Unknown metrics —, no invented zero or private error. | none |
| R47 | Both H7 URLs above, 1440px and 375px | Open a source; return; change cohort; open mobile Menu and press Escape. | Stored passage opens; curve follows selected cohort (fixture confidence 75% → 25%). No horizontal overflow; Menu closes and focus returns. | none |
| R48 | Market Lab → Plugins → Files | Upload a DOCX report and a DOCX date/value/unit table after the pending shared upload patch is synced. | Paragraph/table citations retain the original file, tables pass the guard, and no guessed Word page number appears. Foreign workspaces cannot read it; Remove removes its passages and series. | none |
| R49 | Existing private room file endpoint | Retry the same upload id and original; then send different bytes under that id. | The exact retry reuses its saved result without duplicate writes. Replacement is refused; the original and its learned evidence remain unchanged. | none |
| R50 | Market Lab → Plugins → Files | Upload an unreadable report and reload the file list. | Failed status and its existing safe reason persist; no passages from that failed file can answer a question. | none |
| R51 | Refresh feeds / existing scheduled refresh | Refresh with newly accepted demand or supply observations, then repeat without changed observations. | New pooled data recomputes opportunities and append-only predictions. An unchanged refresh does not create a second opportunity run. Held observations are not counted as new usable data. | none |
| R52 | Existing upload and prediction-resolution job | Upload a date/value/unit/series CSV whose explicit series is response:<area>:<segment> and unit is percent. Run resolution after the frozen horizon. | A unique own-tenant measured metric resolves the matching prediction; its original is unchanged and the observed series/date are retained. Ambiguous, foreign or wrong-unit metrics remain unresolved. | none |
| R53 | Existing scheduled refresh | Exercise a missing, failed, empty or denied FRED response alongside other sources. | Each configured series has an honest On/Off receipt. A host denial stops further requests to that host; other source results survive. FRED observations are never stored. | FRED_API_KEY |
| R54 | Runtime series reader | Request a listing without explicit fixture input or a live runner. | It refuses the request rather than silently substituting bundled sample data. Published skill implementation bytes remain unchanged. | none |
| R55 | Ask Market Lab / existing research job | Ask a question that needs web research, then inspect its saved report and original Tank receipts. Repeat with memory unavailable. | Claims retain their source, fetch time and quote; ledger ids, token counts and actual/unknown costs persist with the report. The DB connection is released during research and memory I/O. A memory outage does not erase the saved report. | none |
| R56 | Normal room startup | Upgrade an existing reports table and restart again. | The additive receipts column preserves legacy rows, applies idempotently, and retains private per-tenant report receipts. | none |
| R57 | Offline publisher proof / existing refresh job | Run tests/test_market_lab_finish_receipts.py::test_scheduled_live_refresh_uses_recorded_publishers_and_private_postgres. | The actual live-mode collector consumes recorded official responses, retains two download hashes and exact source citations in private PostgreSQL, and repeats without inflating the On count. This is an offline proof, not production access. | none |

Deferred features: USPTO ML7 stays parked even though USPTO_API_KEY is in the
register. H3 classifier waits for 90 days of outcomes. H7 implements the proposed wave-5 frames; founder approval and deployed acceptance remain pending. R21 tests the structured $0 read.
No acceptance claim is made for those unshipped views/features.

Offline command (no outside network; local PostgreSQL/SMTP/ASGI fixtures only):

```sh
TMPDIR=/workspace/codex-market-lab-w3/.tmp PYTHONPATH=tank .venv/bin/python -m pytest -q tests/acceptance/test_market_lab.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --timeout=180
```

CI lint before every push:

```sh
ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
```

Offline result: **43 passed, 0 skipped** (90.35 seconds). The revised R39
provider-sign-in case also passed separately (1 passed, 42 deselected).
All 43 row IDs map to exactly 43 test functions, with no duplicates or omissions.
Outside sockets are disabled; tests use local SQL, fake SMTP, ASGI endpoints and
recorded publisher data. MCP discovery and room metadata transport are fixture
boundaries; no production credential, model or real recipient is used.
The 15 warnings are existing Pydantic field-shadow and FastAPI lifecycle warnings.

Initial test-only issues corrected before this result: generated indentation,
a same-basename import collision (resolved with the acceptance package marker),
missing collector arguments, and the fixture's normalized EIA decimal spelling
(3.86). No production source was changed to make acceptance pass.

The settings register was read, without merging, from commit `272454b69c74982b8f0c8439f1a760d267a073a3`.
No deployment, real founder delivery or live UI acceptance is claimed here.

H7 adds R44–R47 (47 rows total). Earlier results predate H7. H7 needs no new setting. Dedicated brief confidence/history sections await frame slots; the structured read returns both. Browser evidence uses local fixtures, not a deployed founder session.

## Paid ladder approval

Use a disposable test tenant and the cloud-side authenticated Tank client; do not put service keys into a browser. Configure an existing paid model on `market.research` for this fixture. The screen switches await the frames listed in `docs/paid-steps/FRAMES.md`; the authenticated settings API is available now.

| Row | Where | What the founder does | Expected result | Setting it needs | Offline case |
| --- | --- | --- | --- | --- | --- |
| PAID-MARKET_LAB | Tank `POST /v1/route`, task_type `market.research`; existing `/chats` confirmation card | Send a test request in Ask mode. Confirm its pending paid-step card, then repeat the same run. Set that exact step to Auto and start a new run. Enable Pause all paid work and start another run. | Ask returns 409 with `paid_step_approval_required` before dispatch. Approval resumes with HTTP 200 and receipt `paid_step_mode=approved`; repeating the run does not dispatch again. Auto returns 200 with `paid_step_mode=automatic`. Master pause returns 503 and sends no paid call. | `paid_step_settings.mode`; `paid_paused`; existing configured model and room credentials | `tests/acceptance/test_paid_steps.py`, `market_lab` |
