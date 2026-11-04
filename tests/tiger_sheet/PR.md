# Tiger: finish the approved views and add founder acceptance coverage

## Product fixes first

The saved-page gold scorer now captures the external event publisher. After the
event-bus integration it constructed a real HTTP/TLS client inside a code-only
2 ms benchmark, breaking both the offline promise and timing check. The reader,
watch check, observation, alert and event facts still execute; only delivery is
faked. The threshold is unchanged, with no security/test exception.

The approved price-position implementation was still on `codex/tiger-w4`, not
main. This branch brings it forward without merging: tenant-scoped match review,
confirmed Undo, real site-check summaries, and the three approved responsive
views. Newer main-branch Command registrations are retained. A rejected match
can be restored to suggested; a confirmed match remains final. Reads write $0
Tiger receipts. Decisions use the existing durable confirmation cards.

The views use actual tenant catalogue names, confirmed matches, saved prices and
vault sites. Paused, stale, missing, future and cross-currency readings cannot
claim a price rank. Site counters come from immutable sightings in that tenant's
latest discovery run; missing evidence stays unknown. No frame example is
production data. No provider/model caller or new visible wording is added.

## Inventory of the shipped product

Inventory checked against main `d5d3ea2e` and the merged implementation history;
the approved views above complete the outstanding TG2 work. The acceptance sheet
and its executable cases accompany this inventory in the next two steps.

| Feature | Merged history / implementation | Offline proof paths |
| --- | --- | --- |
| Product watches, five allowed intervals, public URL validation, tenant sessions, price/stock observations, dispatch, strict percentage threshold, paused/removed watches | Initial Tiger watches; `agents/tiger/app.py`, `watch.py`, `browser.py`; #629 `tank/tiger_watch_commands.py` | `tests/test_tiger.py`, `test_tg2_tiger_watchlist.py`, `test_tiger_watch_commands.py` |
| Real page price reading: JSON-LD, microdata, visible DOM, structured extraction and OCR fallback; missing/blocked reads never invent prices | Tiger price-reader waves; `tank/skills/tiger.price_extract/`, `tiger.price_structured/`, `tiger.price_ocr/` | `tests/test_tiger_works.py`, `tiger_price_read/`, `tiger_alert_page/`; saved Adafruit page HTML goes through the actual code reader |
| All five alerts: price, stock, new product, below own cost, market gap; preferences, durable deduplication, tenant-bound SMTP | G5 #418; email delivery; #614 `tank/tiger_alerts.py` | `tests/tiger_g5/`, `test_tiger_alert_email.py`, `test_tiger_alerts_read.py`; actual agent job → saved HTML → SQL → local SMTP |
| Chat watch/read, list/pause/resume/remove, five-URL bulk, paid new-URL count, confirmation and zero-cost reads | #614, #629; `tank/command.py`, `tiger_watch_commands.py`, `tiger_alerts.py` | `tests/test_tiger_watch_commands.py`, `test_tiger_alerts_read.py`, actual durable-card confirmation cases |
| Saved competitor sites, bounded anonymous discovery, exact GTIN auto-match, brand/MPN review, reject/confirm/Undo, evidence and tenant isolation | #599; approved TG2 brought forward here; `agents/tiger/matching.py`, `tank/access.py` | `tests/test_tiger_competitors.py`, including real discovery jobs and durable cards |
| Price position, Matches to review, Competitor sites; desktop/mobile and framed empty states; existing overview/history/alerts | #596 approved register and the completed TG2 implementation; `workspace/app/tiger/` | `tests/tiger_position/workspace.test.cjs`, `browser.cjs`, ten independent frame exports; `tests/tiger_works/workspace.test.cjs` |
| Rig's eligible product watches, price/stock delivery, idempotent retries, shared URLs, cancellation, read-only check-now | #458 and Rig/Tiger handoff waves; `agents/tiger/rig_watch.py` | `tests/rig_tiger_prices/` |
| Tenant-private official feeds/portal prices; approved browser credentials and handback, revocation, archive rules; vault keys/files/links/MCP | ACCESS1; `tank/access.py`, `agents/_browser/`, Tiger Plugins/server actions | `tests/test_access1.py`, `test_access1_sources.py`, `test_tiger_works.py`, Workspace tests |
| Code-only public layout playbooks with independent-page promotion/retirement; reader evaluation and unverified correction inbox | #403 and reader waves; `agents/tiger/domain_playbooks.py`, `gold_feedback.py` | `tests/tiger_playbooks/`, `tiger_price_read/`, `tiger_alert_page/` |
| Optional sealed Tiger brain/sandbox, profile off, no caller, owning-key Tank accounting, wrong-room rejection before SQL | #638; `agents/tiger/docker-compose.yml`, `tank/agent_skills.py`, isolation/seal scripts | `tests/tiger_brain/test_tg3.py`, `test_room_seal.py`, `test_ledger_sql_param.py` |

## Validation and limits

All verification uses disposable local PostgreSQL, ASGI/MockTransport services,
saved public page HTML and local SMTP. No tenant data, provider call, deployment
or live founder sign-in is used. Founder checks in the sheet remain the live
acceptance step after deployment. Hosted CI status is reported separately from
local checks; this file does not claim an unobserved green CI run.

Unframed states remain listed, not built: loading/read failure/decision failure,
unavailable site-check metadata, no catalogue products in Price position, and
GTIN auto-match wording in review. Watch interval, threshold, enabled state and
alert-kind controls need their own card/page frames. The existing cards retain
these fields as data; the five alert kinds are readable through `/chats` and
deliver through email. No additional page labels are invented.
