# Tiger — founder testing sheet

Scope: shipped Tiger watches, readers, all five alerts, Rig handoff, sources,
Plugins and the sealed optional brain, plus the approved price-position views
finished on `codex/tiger-sheet`. Inventory and fixes: `tests/tiger_sheet/PR.md`.
There are **51 rows**, each with exactly one `test_tgNN_*` offline case in
`tests/acceptance/test_tiger.py`. Cases run the shipped implementation with fake
external services; no production account, paid model or live page is required.

Settings below are names from `docs/ops/FOUNDER-SETTINGS.md`. Existing founder
sign-in, active organization, Tiger squad entitlement, region routing and room
keys are prerequisites. “none” means no additional founder setting. Never paste
credentials in chat or this sheet. `tiger.vault` is the existing vault switch,
not an environment setting. Only the founder enters private plugin/source values.

## Addresses and test inputs

- Browser: **https://tiger.tervory.com/** (the same Tiger view at
  **https://app.tervory.com/tiger**) and **https://app.tervory.com/chats**.
- In chats, use the literal tool command shown, substitute the founder's actual
  public product URL for `<URL>`, and tap the existing **Confirm** card when
  offered. Reads need no Confirm. Keep a dedicated founder test watch/product;
  never mutate a client's catalogue to manufacture a result.
- Use a founder-controlled public HTML page whose displayed product name,
  currency, price and stock can be changed. Keep its initial HTML as evidence.
  Offline positive reads use saved public Adafruit HTML and the actual Tiger
  extractor, not a hard-coded price response. Production pages use their real data.
- `<URL2>` is another owned test watch, `<SITE>` a saved public competitor site,
  `<MATCH>` a returned match UUID, `<TENANT>` the active organization's UUID.
  Five bulk inputs are five distinct real public product URLs, one per line.
  A second isolated tenant provides negative boundary checks.
- `http://tank:8000/...` and `http://agent-tiger:8000/...` are **internal operator
  APIs**, not public browser pages. Use the existing authorized operator session;
  deployment supplies private Workspace/room headers. Operator fixtures below
  are reproducible without making live destructive or paid requests.
- G5 alert preferences currently use the existing internal watch PATCH API:
  `/watchlist/<WATCH>` with `tenant_id` and the chosen `alert_*` boolean. Existing
  page controls cover price/stock; no unapproved page text or control is added.
- Email settings map the exact tenant UUID to the founder's recipient; no global
  fallback recipient. `TIGER_SMTP_ALERT_ADDRESSES` is that JSON mapping.

## Acceptance rows

| Row / offline test | Where | Exact action | Expected result | Setting it needs |
| --- | --- | --- | --- | --- |
| TG01 `test_tg01_*` | https://app.tervory.com/chats → Tiger page | Send `tiger.watch <URL>`, confirm, then allow its scheduled check. Open Overview/History and `tiger.read <URL>`. | One daily watch; the real HTML product name, price, currency and stock appear in its own history. A second tenant's readings never appear. | none |
| TG02 `test_tg02_*` | Chats; internal watch API | Create the test watch without an interval; operator fixtures also submit each of `15m`, `1h`, `6h`, `12h`, `1d`, and invalid `2h`. | Default is `1d` (Every day); only those five values work. Invalid value is refused before a room call. | none |
| TG03 `test_tg03_*` | https://app.tervory.com/chats | Send `tiger.watches`. | Only this tenant's watch names and URLs; total matches them. Extra watch fields remain data. A $0 Tiger code receipt is written; no Confirm. | none |
| TG04 `test_tg04_*` | Chats → Tiger History | Send `tiger.watch.pause <URL>` and Confirm. Wait through a due dispatch. | That exact owned URL is disabled and gets no new scheduled check. A different URL and another tenant's identical URL stay unchanged. | none |
| TG05 `test_tg05_*` | Chats → Tiger History | Resume TG04 using `tiger.watch.resume <URL>` and Confirm. | Same watch is enabled and due dispatch includes it again. A foreign tenant's URL is 404. | none |
| TG06 `test_tg06_*` | Chats → Tiger page | Send `tiger.watch.remove <URL2>` and Confirm. | Only that exact owned watch is removed; a foreign URL is 404. Other watches/history are retained. | none |
| TG07 `test_tg07_*` | Chats → Tiger page | Send `tiger.watch.bulk` followed by five product URLs. Confirm; repeat with an already watched URL. | All five new watches appear with `every=1d`; duplicates count as already watched and do not abort the others. Paid card cost counts only new URLs; confirmed replay creates no duplicate. | none |
| TG08 `test_tg08_*` | Chats; isolated URL fixture | Submit bulk with 51 URLs, an empty list, `file:///tmp/page`, loopback and a hostname resolving to a private address. | Requests are refused; non-http(s)/private destinations never become watches. Valid public destinations still work. | none |
| TG09 `test_tg09_*` | Chats; internal command routes | Prepare pause, resume, remove and bulk cards; dismiss them. In the fixture, also call each changing route without its bound confirmation and with another tenant's binding. | All four changes require Confirm; direct/unbound calls return 409 and make no room change. | none |
| TG10 `test_tg10_*` | Chats → Tiger page | Check two isolated tenants' test pages with different real prices. Read observations/alerts and attempt a cross-tenant removal. | Each tenant sees only its own readings, alerts and watches; mismatched tenant is refused, foreign removal is 404, missing Workspace key is 401. | none |
| TG11 `test_tg11_*` | Tiger Alerts; founder inbox | With price alert on and stock unchanged, lower the controlled page price across its threshold, check twice. | One price alert/email with real before/after values and page link; unchanged repeat sends none. Threshold comparison is strict. | TIGER_SMTP_HOST, TIGER_SMTP_PORT, TIGER_SMTP_USER, TIGER_SMTP_PASSWORD, TIGER_SMTP_FROM, TIGER_SMTP_ALERT_ADDRESSES |
| TG12 `test_tg12_*` | Tiger Alerts; founder inbox | Keep price fixed, change explicit page stock from InStock to OutOfStock with stock alert on; check twice. | One stock alert/email, correct product and URL, no duplicate on unchanged repeat. | TIGER_SMTP_HOST, TIGER_SMTP_PORT, TIGER_SMTP_USER, TIGER_SMTP_PASSWORD, TIGER_SMTP_FROM, TIGER_SMTP_ALERT_ADDRESSES |
| TG13 `test_tg13_*` | Chats; founder inbox | Enable `alert_new_product` on a controlled listing watch. Establish baseline, add a product, run checks, then read `tiger.alerts`. | Exactly one `new_product` alert/email for the newly listed product. Initial baseline and reorder are quiet. | TIGER_SMTP_HOST, TIGER_SMTP_PORT, TIGER_SMTP_USER, TIGER_SMTP_PASSWORD, TIGER_SMTP_FROM, TIGER_SMTP_ALERT_ADDRESSES |
| TG14 `test_tg14_*` | Chats; founder inbox | With the same tenant's matched Rig SKU and supplier cost, enable `alert_below_cost` and check a competitor priced below that cost. | One `below_cost` alert/email based on that tenant's cost and matching currency, never retail price or another tenant's cost. | TIGER_SMTP_HOST, TIGER_SMTP_PORT, TIGER_SMTP_USER, TIGER_SMTP_PASSWORD, TIGER_SMTP_FROM, TIGER_SMTP_ALERT_ADDRESSES |
| TG15 `test_tg15_*` | Chats; founder inbox | Enable `alert_market_gap`; the controlled own product is in stock and every watched competitor has a fresh explicit out-of-stock reading. | One `market_gap` alert/email. Unknown, stale or in-stock competitor readings cannot fabricate a gap. | TIGER_SMTP_HOST, TIGER_SMTP_PORT, TIGER_SMTP_USER, TIGER_SMTP_PASSWORD, TIGER_SMTP_FROM, TIGER_SMTP_ALERT_ADDRESSES |
| TG16 `test_tg16_*` | https://app.tervory.com/chats | Send `tiger.alerts` after the five fixture transitions. | All five saved kinds and their counts, only own tenant rows; $0 Tiger code receipt, no model or Confirm. | none |
| TG17 `test_tg17_*` | Chats; `/v1/command/tiger/alerts` | Read one URL and one kind at a time; fixture also submits an unknown kind and another tenant's injected row. | URL/kind filters work; bad kind is refused, foreign data absent, exactly one $0 receipt per successful read. | none |
| TG18 `test_tg18_*` | Tiger Add product; internal watch preferences | Turn price/stock switches off/on and the three operator G5 booleans off/on. Check page, official-feed and approved-portal fixture readings. | Disabled kinds create/send no alert; readings continue. Muting after queueing also suppresses unsent mail; other tenant unchanged. | none |
| TG19 `test_tg19_*` | Founder inbox; isolated SMTP fixture | Reproduce a temporary SMTP rejection, retry after backoff, and repeat a successful dispatch. Reproduce an uncertain response after server acceptance offline. | Rejected send retries once with correct tenant recipient; accepted mail is never resent after uncertain completion. No default/cross-tenant recipient. | TIGER_SMTP_HOST, TIGER_SMTP_PORT, TIGER_SMTP_USER, TIGER_SMTP_PASSWORD, TIGER_SMTP_FROM, TIGER_SMTP_ALERT_ADDRESSES |
| TG20 `test_tg20_*` | Tiger Overview/History | Check a controlled unavailable/challenge page and an HTML page missing its price. Inspect latest attempt. | Existing Not checked status, reason, timestamp and link; no invented price or alert, no automatic challenge bypass. | none |
| TG21 `test_tg21_*` | Rig catalogue → Tiger History | Add an eligible own Rig product with a public page URL, check it twice with changed price/stock. | Automatic tenant-bound watch updates only its own Rig SKU. | none |
| TG22 `test_tg22_*` | Rig catalogue → Tiger History | Delete the isolated Rig product before the next check. | Old managed watch/delivery is cancelled before reading; other tenant unaffected. | none |
| TG23 `test_tg23_*` | Internal `http://agent-tiger:8000/rig/check-now` | Request a check of the owned enabled watched URL; fixture repeats with unknown stock, disallowed robots, challenge and timeout. | Explicit stock/price gives available/unavailable. Other cases return unknown with reason; never guess availability or create an alert. | RIG_TIGER_CHECK_KEY |
| TG24 `test_tg24_*` | Chats; Price position | Save a competitor site and run `tiger.match` against an own catalogue product whose page has the identical valid GTIN. | Exact identifier match is confirmed with evidence; own feed link/watch uses existing defaults. Title-only similarity never creates a match. | none; existing `tiger.vault` switch on |
| TG25 `test_tg25_*` | Matches to review | Discover matching brand+MPN without a matching GTIN. Inspect evidence and click Confirm. | Suggested first; durable bound confirmation creates only the own match/link/watch. Another tenant cannot confirm it. | none |
| TG26 `test_tg26_*` | Matches to review; `tiger.matches` | Open review and inspect newest suggestions/rejections. Fixture has 105 rows per tenant and a catalogue outage. | Own newest 100 only with identifier/page evidence; confirmed excluded. Stored evidence survives catalogue outage. $0 receipt. | none |
| TG27 `test_tg27_*` | Matches to review | Reject a suggestion, click Undo, then Confirm it; attempt Undo again in the fixture and under the other tenant. | Reject → rejected, Undo → suggested, Confirm → confirmed. Confirmed stays final; foreign row is 404 and changes require confirmation. | none |
| TG28 `test_tg28_*` | Tiger Watch list → Price position; `tiger.position` | With confirmed matches and fresh same-currency readings, inspect own price, competitor range, position and gap. | Figures come from the active tenant's real latest prices. Equal prices share a rank; read writes a $0 Tiger receipt. | none |
| TG29 `test_tg29_*` | Tiger Price position | In the offline fixture pause a watch, age a reading, use another currency, remove a price and set a zero comparison denominator. | No fabricated rank/percentage. Real last stale reading may remain with framed warning; unknown stays absent. | none |
| TG30 `test_tg30_*` | Tiger Competitor sites → Source links | Save the own source link, run discovery, inspect sites and open the Source links panel. | Only own saved sites; counters/times use that site's immutable latest-run evidence. Missing data differs from real zero. | none; existing `tiger.vault` switch on |
| TG31 `test_tg31_*` | All three Tiger Watch list views | Inspect Price position, Matches to review and Competitor sites at 1440 px and 375 px; use Reject/Undo/Confirm at both widths. | Approved FIXED text/layout/assets match all six populated frames. Real data replaces examples. No horizontal overflow; warning uses existing --warn. | none |
| TG32 `test_tg32_*` | Matches to review; Competitor sites | Open the two views for a tenant with no review matches or saved sites at both widths. | Exactly **No matches to review.** and **No saved sites.**; four approved empty frames. Failed reads are not presented as empty accounts. | none |
| TG33 `test_tg33_*` | Tiger → Plugins | Open Plugins with the vault off. | **This vault is off. Turn it on in Tank.** No write runs. | none |
| TG34 `test_tg34_*` | Tiger Plugins → API keys | With vault on, privately save a named key, inspect mask, then Remove. | Existing save/remove notices; raw key is never returned or rendered. Calls bind to own tenant/user and `tiger.vault`. | none; existing `tiger.vault` switch on |
| TG35 `test_tg35_*` | Tiger Plugins → Files | Upload an own CSV/XLSX/PDF, inspect metadata, then Remove. | Existing saved/removed notices and metadata only; file operations use own Tiger vault. | none; existing `tiger.vault` switch on |
| TG36 `test_tg36_*` | Tiger Plugins → Source links | Add an own HTTPS source, label and Daily frequency; inspect, then Remove. | Saved labelled source and frequency; same source powers Competitor sites. Save itself does not fetch the URL. | none; existing `tiger.vault` switch on |
| TG37 `test_tg37_*` | Tiger Plugins → MCP connections | Privately add an HTTPS connection with token, inspect mask, then Disconnect. | Existing saved/removed notices, own vault binding; token never rendered. | none; existing `tiger.vault` switch on |
| TG38 `test_tg38_*` | Internal source import/price; Tiger History | Load the controlled official feed or approved portal item, check the watch; fixture also makes feed missing/unavailable. | Own feed/portal price and receipt are used; no cross-tenant price. Missing/unavailable feed falls back to actual public HTML. | none |
| TG39 `test_tg39_*` | Internal `/v1/access/browser/tiger` and credentials | In an isolated approved Tiger connection fixture, release exact tenant/site credentials through its encrypted browser envelope; try another room/site/tenant; revoke. | Only the owning browser receives encrypted authorized values. Wrong scope, expired/denied terms and revocation refuse release; session revocation remains effective. | TANK_VAULT_KEY, ACCESS_BROWSER_KEY_TIGER |
| TG40 `test_tg40_*` | Internal access queue/live browser handback | Pause on a controlled login/CAPTCHA, use the existing authorized handback, then resume that same page; fixture replays control. | Human completes it; no automated CAPTCHA solver or unrestricted form POST. Same live page/session/tenant preserved; replay refused. | TANK_VAULT_KEY, ACCESS_BROWSER_KEY_TIGER |
| TG41 `test_tg41_*` | Internal access source fallback | Reproduce temporary public-source failures and a dated archive response. Repeat with private source and CAPTCHA fixtures. | Bounded backoff and dated provenance for public archive only. Private data/challenges never use an archive bypass. | none |
| TG42 `test_tg42_*` | Tiger scheduled checks; operator playbook evidence | Read three distinct complete public pages of one layout; read a fourth, then reproduce three consecutive layout failures. | Code-only structural playbook is promoted/reused then retired. Repeats/query aliases do not count as independent pages; shared data contains no tenant prices/secrets. | none |
| TG43 `test_tg43_*` | Operator reader correction inbox | Record the founder's corrected price against saved controlled HTML using `agents/tiger/gold_feedback.py`; inspect the saved inbox row. | Normalized correction is unverified/inbox only, never automatically trusted training gold. No new page is required. | none |
| TG44 `test_tg44_*` | Operator normal deploy; `ops/seal-check.sh` | Leave brain disabled; inspect normal Compose service list and host seal output. Offline fixture also inspects explicit profile and wrong-network cases. | Normal deploy starts no Tiger brain/sandbox; agent-tiger sealed. Optional pair has its own isolated topology, no provider keys/room volume. Capacity gate stays in force. | TIGER_BRAIN_ENABLED (leave false), SANDBOX_KEY_TIGER |
| TG45 `test_tg45_*` | Internal Tank `/v1/agents/tiger/chat/completions` | Run the isolated owning-key fixture, wrong-room/key fixture, paid-work pause and model refusal; inspect ledger. No live model request needed. | Only Tiger key accepted; Tank guards/accounting retained, ledger receipt written. Hostile room rejected before SQL. No caller added to Tiger. | none |
| TG46 `test_tg46_*` | Chats; isolated tenant without Tiger entitlement | Attempt watches, alert reads, match review and position with Tiger squad disabled. | 403 before room work/spend; no foreign result or successful receipt. | none |
| TG47 `test_tg47_*` | Tiger reader; operator saved-page fixtures | Read JSON-LD/microdata/visible-price HTML and an image-only fixture through the shipped reader skill evals. | Required reader cases pass; OCR uses Tiger's code box and lower confidence. Missing price remains unknown, prompt text cannot invent one. | none |
| TG48 `test_tg48_*` | Tiger Overview, Alerts, History | Search a real product/name/URL, inspect history and a failed latest attempt; fixture also omits account/name/currency/time fields. | Search uses actual data, history preserves attempts, existing failure wording and links remain. No fabricated product name, price or attempt time. | none |
| TG49 `test_tg49_*` | Rig catalogue → Tiger History | Give two own eligible SKUs the same controlled public page URL and allow a check. | One page read updates both own SKUs, with no other-tenant change. | none |
| TG50 `test_tg50_*` | Rig catalogue; isolated delivery fixture | Reproduce an unavailable Rig delivery, restore it and dispatch again without changing the page. | Durable pending delivery retries successfully without rereading the page or leaking tenants. | none |
| TG51 `test_tg51_*` | Rig catalogue → Tiger History | Change the isolated product's public page URL before the next read. | Old managed watch is cancelled; the new URL is bound before reading and stale delivery cannot update the product. | none |

## Frame gaps and live sign-off

Unframed loading/read failure/decision failure, unavailable site-check metadata,
an empty catalogue in Price position, GTIN review wording, and interval/threshold/
enabled/alert-kind card controls are listed, not built. Existing cards keep these
fields as data. The five alert kinds work in chats/email; G5 page labels await
their own frames. The approved ten frames are recorded in
`docs/figma/TIGER-POSITION-FRAMES.md`; no example shop is production content.

Founder records deployed head, date, desktop and phone results, real source URLs,
own observed prices and email receipts privately. Offline passing is not a claim
that live deployment or founder acceptance has happened. Brain remains off until
the founder's capacity approval; see `docs/cursor/ROOMS.md`.
