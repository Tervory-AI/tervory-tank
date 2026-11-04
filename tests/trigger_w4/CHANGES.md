# Trigger Wave 4 — change index

Branch: `codex/trigger-w4`; base: `55b2e224` from `origin/main`. The pushed final head is reported in the task handoff. Line numbers refer to the final branch files; binaries have no text line numbers.

| File | Changed line starts | Change |
|---|---|---|
| [agents/rig/rigbox/api.py](../../agents/rig/rigbox/api.py) | 56 | Accept bounded optional quote request title, quantity and request text. |
| [agents/rig/rigbox/service.py](../../agents/rig/rigbox/service.py) | 653 | Keep request metadata on the existing quote request without inventing pricing. |
| [docs/ops/TRIGGER-WAVE4.md](../../docs/ops/TRIGGER-WAVE4.md) | 1 | FIXED/DATA copy register, frame gaps, decisions, embed/configuration and deployment boundaries. |
| [tank/main.py](../../tank/main.py) | 4702 | Mount only the two Trigger routers; startup guards and routing ladder are unchanged. |
| [tank/schema.sql](../../tank/schema.sql) | 2842 | Add settings JSON and human-reply name above generated memory; existing table RLS/retention apply. |
| [tank/trigger_bot.py](../../tank/trigger_bot.py) | 210 | Preserve actual first and last names in lead drafts. |
| [tank/trigger_bot_api.py](../../tank/trigger_bot_api.py) | 73, 132, 220, 232 | Wire confirmed console operations; preserve quote request metadata through the existing draft/activation flow. |
| [tank/trigger_bot_contract.py](../../tank/trigger_bot_contract.py) | 44, 64, 100 | Register strict console tools and preserve explicit contact/quote fields. |
| [tank/trigger_console.py](../../tank/trigger_console.py) | 1 | Tenant-admin page reads, M1 review refresh, explicit proposals, server-captured previews, stale-write checks and local scheduling. |
| [tank/trigger_console_contract.py](../../tank/trigger_console_contract.py) | 1 | Strict settings/conversation payloads and IANA-zone validation. |
| [tank/trigger_crm.py](../../tank/trigger_crm.py) | 28, 151 | Project framed fields and nested item/payment data while excluding credentials, public links/tokens and creator email metadata. |
| [tank/trigger_widget.py](../../tank/trigger_widget.py) | 1 | Origin-bound public config/message/poll/hand-over over B1, private-data filtering and privacy/hours gates. |
| [tests/trigger_w4/CHANGES.md](../../tests/trigger_w4/CHANGES.md) | 1 | This complete file/line change index. |
| [tests/trigger_w4/PR.md](../../tests/trigger_w4/PR.md) | 1 | Review-ready description for Claude; no PR operation performed. |
| [tests/trigger_w4/browser.cjs](../../tests/trigger_w4/browser.cjs) | 1 | Actual React and cross-origin widget browser proof at 1440/375 with placeholder fixtures. |
| [tests/trigger_w4/evidence/channels-1440.png](../../tests/trigger_w4/evidence/channels-1440.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/channels-375.png](../../tests/trigger_w4/evidence/channels-375.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/detail-1440.png](../../tests/trigger_w4/evidence/detail-1440.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/detail-375.png](../../tests/trigger_w4/evidence/detail-375.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/leads-1440.png](../../tests/trigger_w4/evidence/leads-1440.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/leads-375.png](../../tests/trigger_w4/evidence/leads-375.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/settings-1440.png](../../tests/trigger_w4/evidence/settings-1440.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/settings-375.png](../../tests/trigger_w4/evidence/settings-375.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/widget-1440.png](../../tests/trigger_w4/evidence/widget-1440.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/evidence/widget-375.png](../../tests/trigger_w4/evidence/widget-375.png) | binary | Offline placeholder browser evidence at the width in the filename; no production data. |
| [tests/trigger_w4/test_console_widget.py](../../tests/trigger_w4/test_console_widget.py) | 1 | Real disposable-schema/API, tenant/privacy/Confirm/poll/schedule/quote projection tests. |
| [tests/trigger_w4/test_wave4_workspace.py](../../tests/trigger_w4/test_wave4_workspace.py) | 1 | Run actual server-action/public transport contracts in CI. |
| [tests/trigger_w4/verification.txt](../../tests/trigger_w4/verification.txt) | 1 | Exact verification commands, results, skips and corrected local harness issues. |
| [tests/trigger_w4/workspace.cjs](../../tests/trigger_w4/workspace.cjs) | 1 | Named offline identity/fetch substitutes around actual Workspace modules. |
| [workspace/app/product-nav.ts](../../workspace/app/product-nav.ts) | 80, 96 | Use the Trigger shell on root and nested Trigger pages. |
| [workspace/app/trigger/\[\[...segments\]\]/page.tsx](../../workspace/app/trigger/%5B%5B...segments%5D%5D/page.tsx) | 1 | Allowlisted server page routes and tenant reads. |
| [workspace/app/trigger/actions.ts](../../workspace/app/trigger/actions.ts) | 1 | Active-tenant server reads/proposals and canonical durable-card Confirm/Cancel transport. |
| [workspace/app/trigger/copy.ts](../../workspace/app/trigger/copy.ts) | 1 | FIXED CRM/menu/channel register and safe DATA formatting. |
| [workspace/app/trigger/layout.tsx](../../workspace/app/trigger/layout.tsx) | 1 | Own scoped Trigger shell/style entry. |
| [workspace/app/trigger/records.tsx](../../workspace/app/trigger/records.tsx) | 1 | Four CRM list/detail views, mobile summary cards, real item/payment tables and framed unsupported controls. |
| [workspace/app/trigger/shell.tsx](../../workspace/app/trigger/shell.tsx) | 1 | Responsive approved navigation, active business switcher and keyboard-accessible mobile drawer. |
| [workspace/app/trigger/trigger.css](../../workspace/app/trigger/trigger.css) | 1 | Scoped approved light desktop/mobile layout and control geometry. |
| [workspace/app/trigger/view.tsx](../../workspace/app/trigger/view.tsx) | 1 | Channels, calendar, Composer, post/review detail, Inbox, settings, drafts, Confirm and receipt links. |
| [workspace/app/v1/bot/widget/\[operation\]/route.ts](../../workspace/app/v1/bot/widget/%5Boperation%5D/route.ts) | 1 | Bounded same-region public transport preserving store Origin; no private Workspace key or fallback. |
| [workspace/lib/product-hosts.ts](../../workspace/lib/product-hosts.ts) | 28 | Map trigger.tervory.com to /trigger. |
| [workspace/middleware.ts](../../workspace/middleware.ts) | 23 | Allow only the four origin/key-authenticated public widget operations through Clerk. |
| [workspace/next.config.ts](../../workspace/next.config.ts) | 8 | Scoped public CORS headers for the two licensed widget font files. |
| [workspace/public/trigger/Atkinson-OFL.txt](../../workspace/public/trigger/Atkinson-OFL.txt) | 1 | Original font licence. |
| [workspace/public/trigger/AtkinsonHyperlegible-Regular.ttf](../../workspace/public/trigger/AtkinsonHyperlegible-Regular.ttf) | binary | Unmodified self-hosted OFL font from the official Google Fonts repository. |
| [workspace/public/trigger/Literata-OFL.txt](../../workspace/public/trigger/Literata-OFL.txt) | 1 | Original font licence. |
| [workspace/public/trigger/Literata.ttf](../../workspace/public/trigger/Literata.ttf) | binary | Unmodified self-hosted OFL font from the official Google Fonts repository. |
| [workspace/public/trigger/toggle-off.svg](../../workspace/public/trigger/toggle-off.svg) | 1 | Original approved Figma toggle asset, unchanged. |
| [workspace/public/trigger/toggle-on.svg](../../workspace/public/trigger/toggle-on.svg) | 1 | Original approved Figma toggle asset, unchanged. |
| [workspace/public/trigger/widget.css](../../workspace/public/trigger/widget.css) | 1 | Approved client panel, fonts, bubbles, controls and responsive bounds. |
| [workspace/public/trigger/widget.js](../../workspace/public/trigger/widget.js) | 1 | Client-only shadow-root embed, repeatable source chips, hand-over, contact/quote drafts and cross-origin font loading. |
| [workspace/public/trigger/wordmark.png](../../workspace/public/trigger/wordmark.png) | binary | Original approved Figma wordmark asset, unchanged. |

## PR #654 security follow-up

| File/call | Lines | Change |
|---|---|---|
| `workspace/app/trigger/actions.ts` reads | 44, 75 | Constant route lookup; separately validated and encoded path/query UUIDs, before identity or fetch. |
| `workspace/app/trigger/actions.ts` confirm/cancel | 91, 106 | Exact UUID validation for both identifiers and encoded card segment. |
| `workspace/app/trigger/[[...segments]]/page.tsx` | 14, 28, 44 | Strict UUID/own-resource checks and structured action arguments replace raw upstream path assembly. |
| `workspace/app/v1/bot/widget/[operation]/route.ts` | 42, 78 | Constant operation lookup and encoded literal segment. |
| `tests/trigger_w4/ssrf.cjs` | 1 | Actual transport fetch-spy coverage of every malformed-value case at every caller. |
| `tests/trigger_w4/test_wave4_workspace.py` | 15 | Run the SSRF contract in CI. |
| `tests/trigger_w4/workspace.cjs` | 116 | Existing contract uses the structured read signature. |
| `tests/trigger_w4/SSRF.md` | 1 | Full caller audit and validation evidence. |
