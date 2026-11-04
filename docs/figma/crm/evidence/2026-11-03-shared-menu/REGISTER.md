# Shared left-menu fix · 3 Nov 2026

Branch: `codex/crm-marketing-chat-design`. Changed after approval, awaiting founder.

## Component-only correction

The shared menu account block no longer occupies a separate pinned area that cuts through the main list. It follows the menu groups in the same vertically scrolling, clipped viewport. Identity/header content stays outside that viewport. All existing entries, words, actions, fonts, colours and 44px item heights remain. Group spacing remains 8px; within-group and account-row spacing remains equal. No page content, page instance overrides, product headings or production code were changed.

Existing Top sources `180:8387` and `180:8467` use a hugging auto-layout content wrapper containing the original groups and account block; original node IDs are preserved. Existing authored scrolled sources `483:39615` and `483:39698` retain their group positions, with the account block placed after the final group. The account block now scrolls with the list rather than covering it. This supersedes earlier register references to a pinned account block.

On Rig Connected desktop `231:11986`, the shared menu is 860px high below its existing 40px notice. The list viewport is now **704px** high. Invoices occupies list y=472–516, fully inside the viewport; the account block starts at list y=888 and is reached by scrolling. Source-only changes propagate through every instance.

## All-frame authoring check

All **210** instances of the four shared menu states were checked, desktop and mobile. Adjacent item spacing was also checked across those instances; [spacing evidence](spacing.json) records the pair count, measured gaps and outliers. No Invoices / All products overlap was found. Every visible full list has clipping and vertical scrolling enabled, and every visible menu row remains 44px high. Compact mobile header instances and existing hidden/custom list variants were checked and left unchanged. Full frame/instance IDs, dimensions and checks are in [checks.json](checks.json).

Verification is from Figma source geometry, overflow settings, inherited instance reads and screenshot inspection; it does not claim a browser-driven prototype gesture test.

## Product heading setting is missing

The original menu family exposes Size and Scroll only. The authored scrolled components expose no product-heading property. Their heading text has no component-property reference. Per the brief, no setting or wording was added and no heading was changed.

Required missing frame: **`231:11986`**, Rig Plugins / MCP connections / Connected / Desktop, still inherits **Trigger** while its page product is **Rig**. Visible mismatches found elsewhere are listed below. [Full heading review](missing-headings.json) also records hidden headings without treating them as visible copy defects.

| Frame | Current heading | Page product | Frame name |
| --- | --- | --- | --- |
| `468:27698` | Trigger | Rig | Rig Plugins / Add connection / Desktop / Changed after approval, awaiting founder |
| `231:12042` | Trigger | Rig | Rig Plugins / MCP connections / Sign-in failed / Desktop / Changed after approval, awaiting founder |
| `231:12224` | Trigger | Tisan | Tisan Plugins / MCP connections / Saved with a token / Desktop / Changed after approval, awaiting founder |
| `231:12340` | Trigger | Tisan | Tisan Plugins / MCP connections / Connected / Desktop / Changed after approval, awaiting founder |
| `231:12284` | Trigger | Tisan | Tisan Plugins / MCP connections / Needs sign-in / Desktop / Changed after approval, awaiting founder |
| `468:26491` | Trigger | Tisan | Tisan Plugins / Disconnect / Desktop / Changed after approval, awaiting founder |
| `231:12098` | Trigger | Rig | Rig Plugins / MCP connections / Server not approved by Tervory / Desktop / Changed after approval, awaiting founder |
| `231:12452` | Trigger | Tisan | Tisan Plugins / MCP connections / Server not approved by Tervory / Desktop / Changed after approval, awaiting founder |
| `468:26347` | Trigger | Rig | Rig Plugins / Disconnect / Desktop / Changed after approval, awaiting founder |
| `231:12396` | Trigger | Tisan | Tisan Plugins / MCP connections / Sign-in failed / Desktop / Changed after approval, awaiting founder |
| `231:12150` | Trigger | Rig | Rig Plugins / MCP connections / Expanded / Desktop / Changed after approval, awaiting founder |
| `231:12504` | Trigger | Tisan | Tisan Plugins / MCP connections / Expanded / Desktop / Changed after approval, awaiting founder |
| `231:11870` | Trigger | Rig | Rig Plugins / MCP connections / Saved with a token / Desktop / Changed after approval, awaiting founder |
| `468:27804` | Trigger | Rig | Rig Plugins / Empty / Desktop / Changed after approval, awaiting founder |
| `468:28102` | Trigger | Tisan | Tisan Plugins / Empty / Desktop / Changed after approval, awaiting founder |
| `468:27996` | Trigger | Tisan | Tisan Plugins / Add connection / Desktop / Changed after approval, awaiting founder |
| `231:11930` | Trigger | Rig | Rig Plugins / MCP connections / Needs sign-in / Desktop / Changed after approval, awaiting founder |
| `231:11986` | Trigger | Rig | Rig Plugins / MCP connections / Connected / Desktop / Changed after approval, awaiting founder |

## Screenshots

| Frame | Evidence |
| --- | --- |
| Rig Connected desktop `231:11986` before | [PNG](before-rig-desktop.png) |
| Rig Connected desktop `231:11986` after | [PNG](rig-desktop.png) |
| Rig Connected mobile `231:12014` | [PNG](rig-mobile.png) |
| CRM mobile drawer `98:9227` | [PNG](crm-mobile-drawer.png) |
| Authored Settings mobile drawer `468:30777` | [PNG](settings-mobile-drawer.png) |

## Changed source node IDs

- `180:8396`
- `180:8404`
- `180:8424`
- `180:8432`
- `180:8446`
- `502:19155`
- `180:8395`
- `180:8454`
- `180:8387`
- `180:8478`
- `180:8486`
- `180:8506`
- `180:8514`
- `180:8528`
- `502:19156`
- `180:8477`
- `180:8536`
- `180:8467`
- `483:39623`
- `483:39651`
- `483:39615`
- `483:39707`
- `483:39735`
- `483:39698`

## Created content-wrapper IDs

- `502:19155`
- `502:19156`

No new product words. The new wrapper layer name Menu content / Vertical scroll is metadata only. [Mutation receipt](changes.json). No other design nodes were directly edited.

## Every checked frame and instance

| Frame | Instance | Source | Full list visible | Frame name |
| --- | --- | --- | --- | --- |
| `310:26470` | `310:26471` | `180:8387` | Yes | Invoices / Detail / Desktop / Filled / Scrolled fields 2 · Changed after approval, awaiting founder |
| `97:8979` | `184:7723` | `180:8387` | Yes | Quotes / List / Desktop / Zero · Changed after approval, awaiting founder |
| `468:31173` | `468:31177` | `180:8387` | Yes | Founder MCP servers / Add server / Unreachable / Desktop / Changed after approval, awaiting founder |
| `310:26850` | `310:26851` | `180:8387` | Yes | Invoices / Detail / Desktop / Filled / Scrolled fields 3 · Changed after approval, awaiting founder |
| `310:35584` | `310:35585` | `180:8387` | Yes | Invoices / Confirm Record payment / Desktop / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:31852` | `310:31853` | `180:8387` | Yes | Quotes / Detail / Desktop / Zero / Scrolled fields 2 · Changed after approval, awaiting founder |
| `97:6671` | `183:9879` | `180:8387` | Yes | Tasks / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `468:31315` | `468:31319` | `180:8387` | Yes | Computers and connected apps / Empty / Desktop / Changed after approval, awaiting founder |
| `291:8357` | `456:19063` | `180:8387` | Yes | A07-failed · Shop platform · connection failed · 1440 · Changed after approval, awaiting founder |
| `256:283` | `465:26776` | `180:8387` | No — compact or hidden list | 02 · Matches to review · 1440 · Approved 3 Nov · Changed after approval, awaiting founder |
| `310:21467` | `310:21468` | `180:8387` | Yes | Opportunities / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:35765` | `310:35766` | `180:8387` | Yes | Invoices / Detail / Desktop / Zero / Scrolled to Items and Payments · Changed after approval, awaiting founder |
| `291:8309` | `456:18970` | `180:8387` | Yes | A07-connected · Shop platform · connected · 1440 · Changed after approval, awaiting founder |
| `231:12680` | `465:48828` | `180:8387` | Yes | Founder MCP servers / Add server / Desktop / Changed after approval, awaiting founder |
| `468:27698` | `468:27702` | `180:8387` | Yes | Rig Plugins / Add connection / Desktop / Changed after approval, awaiting founder |
| `310:15871` | `310:15872` | `180:8387` | Yes | Leads / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:15307` | `310:15308` | `180:8387` | Yes | Leads / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:25719` | `310:25720` | `180:8387` | Yes | Invoices / Detail / Desktop / Zero / Scrolled fields 3 · Changed after approval, awaiting founder |
| `310:20183` | `310:20184` | `180:8387` | Yes | Contacts / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:24466` | `310:24467` | `180:8387` | Yes | Tasks / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `291:8213` | `456:18784` | `180:8387` | Yes | A07-big · BigCommerce · enter credentials · 1440 · Changed after approval, awaiting founder |
| `98:8781` | `192:21949` | `180:8387` | Yes | Invoices / Confirm Send / Desktop · Changed after approval, awaiting founder |
| `94:417` | `182:8951` | `180:8387` | Yes | Leads / List / Desktop / Filled · Changed after approval, awaiting founder |
| `97:2800` | `183:8871` | `180:8387` | Yes | Contacts / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `97:7276` | `184:7467` | `180:8387` | Yes | Invoices / List / Desktop / Filled · Changed after approval, awaiting founder |
| `94:172` | `182:8871` | `180:8387` | Yes | Leads / List / Desktop / Zero · Changed after approval, awaiting founder |
| `98:8893` | `192:22151` | `180:8387` | Yes | Quotes / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `97:3846` | `183:9127` | `180:8387` | Yes | Opportunities / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `231:12744` | `465:48997` | `180:8387` | Yes | Founder MCP servers / Remove server / Desktop / Changed after approval, awaiting founder |
| `98:8685` | `192:21646` | `180:8387` | Yes | Opportunities / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `97:2245` | `183:8703` | `180:8387` | Yes | Contacts / List / Desktop / Filled · Changed after approval, awaiting founder |
| `256:471` | `465:26859` | `180:8387` | No — compact or hidden list | 03 · Competitor sites · 1440 · Approved 3 Nov · Changed after approval, awaiting founder |
| `97:10064` | `184:7971` | `180:8387` | Yes | Quotes / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `267:19232` | `465:26942` | `180:8387` | No — compact or hidden list | 02 · Matches to review · 1440 · Empty · Approved 3 Nov · Changed after approval, awaiting founder |
| `97:8098` | `184:7635` | `180:8387` | Yes | Invoices / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `98:8621` | `192:21444` | `180:8387` | Yes | Clients / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `231:12042` | `465:46359` | `180:8387` | Yes | Rig Plugins / MCP connections / Sign-in failed / Desktop / Changed after approval, awaiting founder |
| `310:35403` | `310:35404` | `180:8387` | Yes | Invoices / Confirm Mark paid / Desktop / Scrolled fields 1 · Changed after approval, awaiting founder |
| `97:2543` | `183:8791` | `180:8387` | Yes | Contacts / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `98:8819` | `192:22050` | `180:8387` | Yes | Invoices / Confirm Mark paid / Desktop · Changed after approval, awaiting founder |
| `98:8963` | `192:22353` | `180:8387` | Yes | Quotes / Confirm Convert / Desktop · Changed after approval, awaiting founder |
| `97:7743` | `184:7555` | `180:8387` | Yes | Invoices / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `97:6463` | `183:9799` | `180:8387` | Yes | Tasks / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `97:7053` | `184:7387` | `180:8387` | Yes | Invoices / List / Desktop / Zero · Changed after approval, awaiting founder |
| `231:12224` | `465:47581` | `180:8387` | Yes | Tisan Plugins / MCP connections / Saved with a token / Desktop / Changed after approval, awaiting founder |
| `231:12340` | `465:47931` | `180:8387` | Yes | Tisan Plugins / MCP connections / Connected / Desktop / Changed after approval, awaiting founder |
| `310:18991` | `310:18992` | `180:8387` | Yes | Clients / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `98:9087` | `192:22555` | `180:8387` | Yes | Invoices / Confirm Delete payment / Desktop · Changed after approval, awaiting founder |
| `310:24977` | `310:24978` | `180:8387` | Yes | Invoices / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:16156` | `310:16157` | `180:8387` | Yes | Leads / Detail / Desktop / Filled / Scrolled fields 2 · Changed after approval, awaiting founder |
| `94:741` | `182:9039` | `180:8387` | Yes | Leads / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `98:8653` | `192:21545` | `180:8387` | Yes | Contacts / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `310:21690` | `310:21691` | `180:8387` | Yes | Opportunities / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `94:1061` | `182:9119` | `180:8387` | Yes | Leads / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `321:6304` | `456:19342` | `180:8387` | Yes | A08-late · Order paid after window · 1440 · Changed after approval, awaiting founder |
| `98:9013` | `192:22454` | `180:8387` | Yes | Invoices / Confirm Record payment / Desktop · Changed after approval, awaiting founder |
| `98:8749` | `192:21848` | `180:8387` | Yes | Tasks / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `231:11794` | `465:43393` | `180:8387` | Yes | CLI sign-ins and connected apps / Connected / Desktop / Changed after approval, awaiting founder |
| `468:31031` | `468:31035` | `180:8387` | Yes | Founder MCP servers / Add server / Duplicate / Desktop / Changed after approval, awaiting founder |
| `97:3522` | `183:9039` | `180:8387` | Yes | Opportunities / List / Desktop / Filled · Changed after approval, awaiting founder |
| `97:5148` | `183:9463` | `180:8387` | Yes | Cases / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `94:2263` | `183:8455` | `180:8387` | Yes | Clients / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `291:8053` | `456:18492` | `180:8387` | Yes | A07-choose · Shop platform · not connected · 1440 · Changed after approval, awaiting founder |
| `231:12284` | `465:47756` | `180:8387` | Yes | Tisan Plugins / MCP connections / Needs sign-in / Desktop / Changed after approval, awaiting founder |
| `310:25348` | `310:25349` | `180:8387` | Yes | Invoices / Detail / Desktop / Zero / Scrolled fields 2 · Changed after approval, awaiting founder |
| `310:19200` | `310:19201` | `180:8387` | Yes | Clients / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `291:8267` | `456:18877` | `180:8387` | Yes | A07-testing · Shop platform · testing · 1440 · Changed after approval, awaiting founder |
| `310:23013` | `310:23014` | `180:8387` | Yes | Cases / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `321:6382` | `456:19435` | `180:8387` | Yes | A07-choose-open · Choose a platform · open · 1440 · Changed after approval, awaiting founder |
| `98:8925` | `192:22252` | `180:8387` | Yes | Quotes / Confirm Send / Desktop · Changed after approval, awaiting founder |
| `97:4837` | `183:9375` | `180:8387` | Yes | Cases / List / Desktop / Filled · Changed after approval, awaiting founder |
| `94:2510` | `183:8535` | `180:8387` | Yes | Clients / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `310:26090` | `310:26091` | `180:8387` | Yes | Invoices / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:32437` | `310:32438` | `180:8387` | Yes | Quotes / Detail / Desktop / Filled / Scrolled fields 2 · Changed after approval, awaiting founder |
| `94:1978` | `183:8367` | `180:8387` | Yes | Clients / List / Desktop / Filled · Changed after approval, awaiting founder |
| `231:12578` | `465:48656` | `180:8387` | Yes | Founder MCP servers / Servers / Desktop / Changed after approval, awaiting founder |
| `291:8151` | `456:18691` | `180:8387` | Yes | A07-woo · WooCommerce · enter credentials · 1440 · Changed after approval, awaiting founder |
| `468:26491` | `468:26495` | `180:8387` | Yes | Tisan Plugins / Disconnect / Desktop / Changed after approval, awaiting founder |
| `310:20402` | `310:20403` | `180:8387` | Yes | Contacts / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `231:12098` | `465:47228` | `180:8387` | Yes | Rig Plugins / MCP connections / Server not approved by Tervory / Desktop / Changed after approval, awaiting founder |
| `97:2074` | `183:8623` | `180:8387` | Yes | Contacts / List / Desktop / Zero · Changed after approval, awaiting founder |
| `97:9218` | `184:7803` | `180:8387` | Yes | Quotes / List / Desktop / Filled · Changed after approval, awaiting founder |
| `97:5994` | `183:9631` | `180:8387` | Yes | Tasks / List / Desktop / Zero · Changed after approval, awaiting founder |
| `310:15589` | `310:15590` | `180:8387` | Yes | Leads / Detail / Desktop / Zero / Scrolled fields 2 · Changed after approval, awaiting founder |
| `267:19424` | `465:27025` | `180:8387` | No — compact or hidden list | 03 · Competitor sites · 1440 · Empty · Approved 3 Nov · Changed after approval, awaiting founder |
| `231:12452` | `465:48286` | `180:8387` | Yes | Tisan Plugins / MCP connections / Server not approved by Tervory / Desktop / Changed after approval, awaiting founder |
| `97:6165` | `183:9711` | `180:8387` | Yes | Tasks / List / Desktop / Filled · Changed after approval, awaiting founder |
| `468:30889` | `468:30893` | `180:8387` | Yes | Founder MCP servers / Add server / Bad address / Desktop / Changed after approval, awaiting founder |
| `468:26347` | `468:26351` | `180:8387` | Yes | Rig Plugins / Disconnect / Desktop / Changed after approval, awaiting founder |
| `97:4662` | `183:9295` | `180:8387` | Yes | Cases / List / Desktop / Zero · Changed after approval, awaiting founder |
| `97:4107` | `183:9207` | `180:8387` | Yes | Opportunities / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `468:26067` | `468:26071` | `180:8387` | Yes | Computers and connected apps / Revoke Computer / Desktop / Changed after approval, awaiting founder |
| `231:12396` | `465:48107` | `180:8387` | Yes | Tisan Plugins / MCP connections / Sign-in failed / Desktop / Changed after approval, awaiting founder |
| `310:31563` | `310:31564` | `180:8387` | Yes | Quotes / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `98:8589` | `192:21343` | `180:8387` | Yes | Leads / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `231:12150` | `465:47406` | `180:8387` | Yes | Rig Plugins / MCP connections / Expanded / Desktop / Changed after approval, awaiting founder |
| `310:32141` | `310:32142` | `180:8387` | Yes | Quotes / Detail / Desktop / Filled / Scrolled fields 1 · Changed after approval, awaiting founder |
| `310:22783` | `310:22784` | `180:8387` | Yes | Cases / Detail / Desktop / Zero / Scrolled fields 1 · Changed after approval, awaiting founder |
| `231:12504` | `465:48464` | `180:8387` | Yes | Tisan Plugins / MCP connections / Expanded / Desktop / Changed after approval, awaiting founder |
| `231:11870` | `465:45832` | `180:8387` | Yes | Rig Plugins / MCP connections / Saved with a token / Desktop / Changed after approval, awaiting founder |
| `291:8405` | `456:19156` | `180:8387` | Yes | A08 · Orders · 1440 · Changed after approval, awaiting founder |
| `94:1811` | `183:8287` | `180:8387` | Yes | Clients / List / Desktop / Zero · Changed after approval, awaiting founder |
| `468:27804` | `468:27808` | `180:8387` | Yes | Rig Plugins / Empty / Desktop / Changed after approval, awaiting founder |
| `468:28102` | `468:28106` | `180:8387` | Yes | Tisan Plugins / Empty / Desktop / Changed after approval, awaiting founder |
| `468:27996` | `468:28000` | `180:8387` | Yes | Tisan Plugins / Add connection / Desktop / Changed after approval, awaiting founder |
| `256:10` | `465:26693` | `180:8387` | No — compact or hidden list | 01 · Price position · 1440 · Approved 3 Nov · Changed after approval, awaiting founder |
| `98:8717` | `192:21747` | `180:8387` | Yes | Cases / Confirm Delete / Desktop · Changed after approval, awaiting founder |
| `310:36136` | `310:36137` | `180:8387` | Yes | Invoices / Detail / Desktop / Filled / Scrolled to Items and Payments · Changed after approval, awaiting founder |
| `231:11930` | `465:46007` | `180:8387` | Yes | Rig Plugins / MCP connections / Needs sign-in / Desktop / Changed after approval, awaiting founder |
| `231:11986` | `465:46183` | `180:8387` | Yes | Rig Plugins / MCP connections / Connected / Desktop / Changed after approval, awaiting founder |
| `97:5416` | `183:9543` | `180:8387` | Yes | Cases / Detail / Desktop / Filled · Changed after approval, awaiting founder |
| `291:8097` | `456:18598` | `180:8387` | Yes | A07-shopify · Shopify · enter credentials · 1440 · Changed after approval, awaiting founder |
| `468:26207` | `468:26211` | `180:8387` | Yes | Computers and connected apps / Revoke App / Desktop / Changed after approval, awaiting founder |
| `98:9131` | `192:22656` | `180:8387` | Yes | Invoices / Confirm Delete line item / Desktop · Changed after approval, awaiting founder |
| `291:8444` | `456:19249` | `180:8387` | Yes | A09 · Store delivery time · 1440 · Changed after approval, awaiting founder |
| `97:9737` | `184:7891` | `180:8387` | Yes | Quotes / Detail / Desktop / Zero · Changed after approval, awaiting founder |
| `97:3343` | `183:8959` | `180:8387` | Yes | Opportunities / List / Desktop / Zero · Changed after approval, awaiting founder |
| `468:31138` | `468:31142` | `180:8467` | No — compact or hidden list | Founder MCP servers / Add server / Duplicate / Mobile / Changed after approval, awaiting founder |
| `231:12478` | `465:48376` | `180:8467` | No — compact or hidden list | Tisan Plugins / MCP connections / Server not approved by Tervory / Mobile / Changed after approval, awaiting founder |
| `468:31280` | `468:31284` | `180:8467` | No — compact or hidden list | Founder MCP servers / Add server / Unreachable / Mobile / Changed after approval, awaiting founder |
| `468:26313` | `468:26317` | `180:8467` | No — compact or hidden list | Computers and connected apps / Revoke App / Mobile / Changed after approval, awaiting founder |
| `468:30996` | `468:31000` | `180:8467` | No — compact or hidden list | Founder MCP servers / Add server / Bad address / Mobile / Changed after approval, awaiting founder |
| `468:27919` | `468:27923` | `180:8467` | No — compact or hidden list | Rig Plugins / Add connection / Mobile / Changed after approval, awaiting founder |
| `231:12014` | `465:46270` | `180:8467` | No — compact or hidden list | Rig Plugins / MCP connections / Connected / Mobile / Changed after approval, awaiting founder |
| `468:26455` | `468:26459` | `180:8467` | No — compact or hidden list | Rig Plugins / Disconnect / Mobile / Changed after approval, awaiting founder |
| `468:28217` | `468:28221` | `180:8467` | No — compact or hidden list | Tisan Plugins / Add connection / Mobile / Changed after approval, awaiting founder |
| `468:31427` | `468:31431` | `180:8467` | No — compact or hidden list | Computers and connected apps / Empty / Mobile / Changed after approval, awaiting founder |
| `468:26173` | `468:26177` | `180:8467` | No — compact or hidden list | Computers and connected apps / Revoke Computer / Mobile / Changed after approval, awaiting founder |
| `231:12124` | `465:47318` | `180:8467` | No — compact or hidden list | Rig Plugins / MCP connections / Server not approved by Tervory / Mobile / Changed after approval, awaiting founder |
| `231:12712` | `465:48912` | `180:8467` | No — compact or hidden list | Founder MCP servers / Add server / Mobile / Changed after approval, awaiting founder |
| `231:12774` | `465:49081` | `180:8467` | No — compact or hidden list | Founder MCP servers / Remove server / Mobile / Changed after approval, awaiting founder |
| `468:26599` | `468:26603` | `180:8467` | No — compact or hidden list | Tisan Plugins / Disconnect / Mobile / Changed after approval, awaiting founder |
| `468:28251` | `468:28255` | `180:8467` | No — compact or hidden list | Tisan Plugins / Empty / Mobile / Changed after approval, awaiting founder |
| `231:12424` | `465:48195` | `180:8467` | No — compact or hidden list | Tisan Plugins / MCP connections / Sign-in failed / Mobile / Changed after approval, awaiting founder |
| `468:27953` | `468:27957` | `180:8467` | No — compact or hidden list | Rig Plugins / Empty / Mobile / Changed after approval, awaiting founder |
| `98:9181` | `187:12961` | `180:8467` | Yes | Trigger / Mobile drawer / Zero · Changed after approval, awaiting founder |
| `231:11832` | `465:43476` | `180:8467` | No — compact or hidden list | CLI sign-ins and connected apps / Connected / Mobile / Changed after approval, awaiting founder |
| `231:12187` | `465:47493` | `180:8467` | No — compact or hidden list | Rig Plugins / MCP connections / Expanded / Mobile / Changed after approval, awaiting founder |
| `231:12368` | `465:48018` | `180:8467` | No — compact or hidden list | Tisan Plugins / MCP connections / Connected / Mobile / Changed after approval, awaiting founder |
| `231:12541` | `465:48551` | `180:8467` | No — compact or hidden list | Tisan Plugins / MCP connections / Expanded / Mobile / Changed after approval, awaiting founder |
| `231:12629` | `465:48743` | `180:8467` | No — compact or hidden list | Founder MCP servers / Servers / Mobile / Changed after approval, awaiting founder |
| `231:11900` | `465:45919` | `180:8467` | No — compact or hidden list | Rig Plugins / MCP connections / Saved with a token / Mobile / Changed after approval, awaiting founder |
| `231:12070` | `465:46447` | `180:8467` | No — compact or hidden list | Rig Plugins / MCP connections / Sign-in failed / Mobile / Changed after approval, awaiting founder |
| `231:12312` | `465:47843` | `180:8467` | No — compact or hidden list | Tisan Plugins / MCP connections / Needs sign-in / Mobile / Changed after approval, awaiting founder |
| `231:12254` | `465:47668` | `180:8467` | No — compact or hidden list | Tisan Plugins / MCP connections / Saved with a token / Mobile / Changed after approval, awaiting founder |
| `98:9227` | `187:13042` | `180:8467` | Yes | Trigger / Mobile drawer / Filled · Changed after approval, awaiting founder |
| `231:11958` | `465:46094` | `180:8467` | No — compact or hidden list | Rig Plugins / MCP connections / Needs sign-in / Mobile / Changed after approval, awaiting founder |
| `271:3480` | `271:3481` | `483:39615` | Yes | Composer / Desktop / Approved · Changed after approval, awaiting founder |
| `149:16251` | `186:5092` | `483:39615` | Yes | Hand-over / Desktop / Zero · Changed after approval, awaiting founder |
| `151:11582` | `186:7148` | `483:39615` | Yes | Confirm · Settings / Desktop / Zero · Changed after approval, awaiting founder |
| `149:8383` | `185:5512` | `483:39615` | Yes | Post detail / Desktop / Zero · Changed after approval, awaiting founder |
| `149:14042` | `186:4644` | `483:39615` | Yes | Inbox // Desktop / Filled · Changed after approval, awaiting founder |
| `149:23463` | `185:6818` | `483:39615` | Yes | Confirm · Send review reply / Desktop / Zero · Changed after approval, awaiting founder |
| `149:10819` | `185:6082` | `483:39615` | Yes | Google Business Profile · Reviews / Desktop / Zero · Changed after approval, awaiting founder |
| `149:7134` | `185:4631` | `483:39615` | Yes | Composer / Desktop / Filled · Changed after approval, awaiting founder |
| `149:2696` | `185:4101` | `483:39615` | Yes | Channels / Desktop / Filled · Changed after approval, awaiting founder |
| `270:3220` | `270:3221` | `483:39615` | Yes | Confirm · Connect / Desktop / Zero · Changed after approval, awaiting founder |
| `151:10432` | `186:6884` | `483:39615` | Yes | Confirm · Quote / Desktop / Zero · Changed after approval, awaiting founder |
| `149:3789` | `185:4215` | `483:39615` | Yes | Calendar · Month / Desktop / Zero · Changed after approval, awaiting founder |
| `149:2263` | `185:3973` | `483:39615` | Yes | Channels / Desktop / Zero · Changed after approval, awaiting founder |
| `149:9975` | `185:5845` | `483:39615` | Yes | Google Business Profile · Posts / Desktop / Filled · Changed after approval, awaiting founder |
| `149:21481` | `185:6390` | `483:39615` | Yes | Confirm · Approve / Desktop / Filled · Changed after approval, awaiting founder |
| `149:4224` | `185:4295` | `483:39615` | Yes | Calendar · Month / Desktop / Filled · Changed after approval, awaiting founder |
| `151:6994` | `186:6148` | `483:39615` | Yes | Confirm · Send reply / Desktop / Zero · Changed after approval, awaiting founder |
| `149:24613` | `185:7082` | `483:39615` | Yes | Confirm · Disconnect / Desktop / Zero · Changed after approval, awaiting founder |
| `270:3789` | `270:3790` | `483:39615` | Yes | Review detail / Desktop / Zero · Changed after approval, awaiting founder |
| `270:3964` | `270:3965` | `483:39615` | Yes | Review detail / Desktop / Filled · Changed after approval, awaiting founder |
| `149:5331` | `185:4383` | `483:39615` | Yes | Calendar · Week / Desktop / Zero · Changed after approval, awaiting founder |
| `270:3369` | `270:3370` | `483:39615` | Yes | Confirm · Connect / Desktop / Filled · Changed after approval, awaiting founder |
| `151:9270` | `186:6676` | `483:39615` | Yes | Confirm · Lead / Desktop / Zero · Changed after approval, awaiting founder |
| `149:22301` | `185:6610` | `483:39615` | Yes | Confirm · Schedule / Desktop / Zero · Changed after approval, awaiting founder |
| `149:5710` | `185:4463` | `483:39615` | Yes | Calendar · Week / Desktop / Filled · Changed after approval, awaiting founder |
| `149:13691` | `186:4478` | `483:39615` | Yes | Inbox // Desktop / Zero · Changed after approval, awaiting founder |
| `151:8468` | `186:6456` | `483:39615` | Yes | Confirm · Hand-over / Desktop / Filled · Changed after approval, awaiting founder |
| `149:19889` | `186:5828` | `483:39615` | Yes | Settings // Desktop / Zero · Changed after approval, awaiting founder |
| `149:16604` | `186:5192` | `483:39615` | Yes | Hand-over / Desktop / Filled · Changed after approval, awaiting founder |
| `149:6649` | `185:4551` | `483:39615` | Yes | Composer / Desktop / Zero · Changed after approval, awaiting founder |
| `151:7330` | `186:6248` | `483:39615` | Yes | Confirm · Send reply / Desktop / Filled · Changed after approval, awaiting founder |
| `149:22643` | `185:6710` | `483:39615` | Yes | Confirm · Schedule / Desktop / Filled · Changed after approval, awaiting founder |
| `149:8745` | `185:5632` | `483:39615` | Yes | Post detail / Desktop / Filled · Changed after approval, awaiting founder |
| `149:19033` | `186:5720` | `483:39615` | Yes | Quote draft / Desktop / Filled · Changed after approval, awaiting founder |
| `151:8132` | `186:6356` | `483:39615` | Yes | Confirm · Hand-over / Desktop / Zero · Changed after approval, awaiting founder |
| `149:21139` | `185:6290` | `483:39615` | Yes | Confirm · Approve / Desktop / Zero · Changed after approval, awaiting founder |
| `151:11924` | `186:7248` | `483:39615` | Yes | Confirm · Settings / Desktop / Filled · Changed after approval, awaiting founder |
| `151:10771` | `186:6984` | `483:39615` | Yes | Confirm · Quote / Desktop / Filled · Changed after approval, awaiting founder |
| `149:24946` | `185:7182` | `483:39615` | Yes | Confirm · Disconnect / Desktop / Filled · Changed after approval, awaiting founder |
| `149:14889` | `186:4772` | `483:39615` | Yes | Conversation detail / Desktop / Zero · Changed after approval, awaiting founder |
| `149:23802` | `185:6918` | `483:39615` | Yes | Confirm · Send review reply / Desktop / Filled · Changed after approval, awaiting founder |
| `149:15281` | `186:4872` | `483:39615` | Yes | Conversation detail / Desktop / Filled · Changed after approval, awaiting founder |
| `149:20253` | `186:5928` | `483:39615` | Yes | Settings // Desktop / Filled · Changed after approval, awaiting founder |
| `149:11184` | `185:6182` | `483:39615` | Yes | Google Business Profile · Reviews / Desktop / Filled · Changed after approval, awaiting founder |
| `151:9612` | `186:6776` | `483:39615` | Yes | Confirm · Lead / Desktop / Filled · Changed after approval, awaiting founder |
| `149:18679` | `186:5620` | `483:39615` | Yes | Quote draft / Desktop / Zero · Changed after approval, awaiting founder |
| `149:9625` | `185:5740` | `483:39615` | Yes | Google Business Profile · Posts / Desktop / Zero · Changed after approval, awaiting founder |
| `149:17814` | `186:5400` | `483:39615` | Yes | Lead draft / Desktop / Filled · Changed after approval, awaiting founder |
| `149:17457` | `186:5300` | `483:39615` | Yes | Lead draft / Desktop / Zero · Changed after approval, awaiting founder |
| `468:28924` | `468:28926` | `483:39698` | Yes | Trigger / Mobile drawer / google-reviews / Filled · Changed after approval, awaiting founder |
| `468:28384` | `468:28386` | `483:39698` | Yes | Trigger / Mobile drawer / calendar / Filled · Changed after approval, awaiting founder |
| `468:28474` | `468:28476` | `483:39698` | Yes | Trigger / Mobile drawer / composer / Zero · Changed after approval, awaiting founder |
| `468:28834` | `468:28836` | `483:39698` | Yes | Trigger / Mobile drawer / google-reviews / Zero · Changed after approval, awaiting founder |
| `468:28654` | `468:28656` | `483:39698` | Yes | Trigger / Mobile drawer / google-posts / Zero · Changed after approval, awaiting founder |
| `468:28564` | `468:28566` | `483:39698` | Yes | Trigger / Mobile drawer / composer / Filled · Changed after approval, awaiting founder |
| `468:28294` | `468:28296` | `483:39698` | Yes | Trigger / Mobile drawer / calendar / Zero · Changed after approval, awaiting founder |
| `153:4367` | `187:13285` | `483:39698` | Yes | Trigger / Mobile drawer / Zero · Changed after approval, awaiting founder |
| `468:30687` | `468:30689` | `483:39698` | Yes | Trigger / Mobile drawer / Settings / Zero · Changed after approval, awaiting founder |
| `150:4047` | `187:13123` | `483:39698` | Yes | Trigger / Mobile drawer / Zero · Changed after approval, awaiting founder |
| `150:4061` | `187:13204` | `483:39698` | Yes | Trigger / Mobile drawer / Filled · Changed after approval, awaiting founder |
| `468:28744` | `468:28746` | `483:39698` | Yes | Trigger / Mobile drawer / google-posts / Filled · Changed after approval, awaiting founder |
| `468:30777` | `468:30779` | `483:39698` | Yes | Trigger / Mobile drawer / Settings / Filled · Changed after approval, awaiting founder |
| `153:4381` | `187:13366` | `483:39698` | Yes | Trigger / Mobile drawer / Filled · Changed after approval, awaiting founder |
