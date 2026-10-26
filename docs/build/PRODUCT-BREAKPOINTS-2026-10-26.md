# Where each product breaks: from the code, 26 Oct 2026

> Claude read each product's one job from the button to the result. **No live calls and no model calls; code only.** Each break is quoted from the code (file:line on main `65067a4`). The key ones were re-checked by hand.
>
> **"Done" for every fix** is that product's job working live, checked again. Tests passing doesn't count.

## The short version
| Product | Closest to working? | The first break |
|---|---|---|
| **Tiger** | **Closest: one fix** | The browser drops the page's HTML (`agents/_brain/browser.py:488`), and Tiger needs it to read the price (`agents/tiger/watch.py:950`). Every check is stored as an error. |
| **Chats and savings** | Works, but every turn is a paid call | Free rungs never run (`tank/main.py:891` blocks the code rung; `command.turn` has `cache_scope='none'`, `tank/schema.sql:1046`). **Chat turns never reach the savings report** (`tank/proof.py:268`, "No linked job"). |
| **Rig** | Import and search work | A store gets no embed key for its own site (only the fixture catalogues have keys), and **quotes can't reach a store by email**: there's no email sender (`agents/rig/rigbox/quotes/senders.py:140-172`). |
| **Base** | The pipeline works (through /data) | `/base` has no upload, no download and no "state + category" form. Sources are labels, not links, and there's no checked date. **Every client's /base reads the platform tenant's records** (`workspace/app/base/load.ts:16`), which breaks AGENTS.md rule 3. |
| **Market Lab** | Fetching is half built | Only one of 14 feeds is ever stored (`agents/market_lab/core/jobs.py:56-58`). The page never reads the stored data (`workspace/app/market-lab/load.ts:37-44`, no `FEEDS_DATABASE_URL`). "Ask" is a model call with feed home pages as "sources". "20 On" counts keys, not feeds that were fetched. |
| **Radix** | The scanner is real | The page has no way to hand over code. No Tank route starts a client scan; the room's scan is wired for Autumbra only (`tank/ghost_routes.py:238`). Findings and Reports are example data (`workspace/app/radix/content.ts`). |
| **Tisan** | Furthest | "Start build" does nothing (`workspace/app/tisan/tisan.tsx:508`, `preventDefault()` only). "Ask Tisan" is a local stub. Tank can't reach the room. There's no preview deploy, and the speed, accessibility, link and secret checks aren't run. |
| **Zenas** | Being fixed | PR #326 |

## The fixes, in order: quickest product win first
1. **Tiger:** get the page HTML back to Tiger only. Show an error read as "Can't read". Make a failed feed lookup fall through to the page read. Read the stock checkbox properly. → Tiger works on the page; alert emails come later.
2. **Chat savings:** link chat turns to the savings report. Give free tool cards a $0 ledger row so totals stop showing "pending". Reread receipts from the ledger when a thread loads. → Every chat shows in the client's savings.
3. **Base:** fix the tenant scoping now (it's a rule break). Then the page needs upload, download and "state + category" with real source links and dates; Figma frame C5 already exists for that page.
4. **Rig:** an embed-key operation and a delivery-settings operation (back end first), an email sender, and removing the "sample data" fine print from the widget. The admin screens for these need Figma.
5. **Chats free ladder:** an approved code skill answers with no model call, the tenant cache is on, and SearXNG becomes a rung. This touches `run_route`, which needs the founder's OK under AGENTS.md rule 6.
6. **Market Lab:** store every feed in Postgres, make the page and Ask read the stored data, link each number to its document, and make "On" honest.
7. **Radix:** client scan routes in Tank, a code upload, and real findings and reports. The upload and the reports need Figma.
8. **Tisan:** a real build form to Tank to the room, the checks run in the room, a preview deploy, and the results back on the page. The form needs Figma.
