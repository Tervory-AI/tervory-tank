# Trigger Wave 4: CRM, Marketing and the embedded chat bot

Trigger now has its own responsive console at `/trigger`, mapped from `trigger.tervory.com`. It reads the active client's BottleCRM leads, contacts, quotes and invoices, and exposes the existing post/review, connection and bot workflows through durable Command confirmations. The embeddable widget uses B1's approved store sources, grounded answers and hand-over, with the approved 343×640 client surface at desktop and phone widths.

The implementation uses PR #642's approved design branch without merging it or main. The complete FIXED/DATA copy register, frame gaps, configuration and decisions are in [TRIGGER-WAVE4.md](../../docs/ops/TRIGGER-WAVE4.md). Every changed file and its changed line numbers are in [CHANGES.md](CHANGES.md).

## Decisions I made

- Tenant identity, role, C1 organization attestation and existing Confirm guards stay authoritative. Previews use the captured server payload, stale snapshots fail, and a replayed confirmation does not repeat a settings write.
- Existing tenant tables gain only settings JSON and a human-reply name; their RLS/retention remain in place. Schema additions precede generated memory, contain no destructive statement, and startup ordering was checked.
- Generated drafts are reviewed before approval/send; no unseen generated output is silently approved. Existing paid guards/routes own runtime drafting. Verification made no model/provider/SMTP calls.
- Visitor contact/quote capture remains disabled without a real client privacy notice/version. No placeholder notice is shipped. Actual first/last names and quote title/quantity/request metadata are preserved, with no invented price or invoice.
- The widget keeps the store Origin via a shadow root, uses the existing public origin-bound regional key, and never receives private provider or Workspace keys. Human replies are web-only. Static licensed fonts have narrowly scoped cross-origin headers; public API authorization is unchanged.
- Unsupported C1 mutations/shared-menu destinations and unsupported channel connections remain disabled. The copy register lists the missing connection/cancel confirmation variants, platform error/receipt regions and other frame gaps. This does not invent backend capabilities or stop the remaining work.

## Validation

- Existing B1/M1/Trigger tests plus Wave 4: **290 passed, 1 skipped**. The skipped integration test requires isolated room and LanguageTool containers.
- Additional CRM/W1/X-length, CRM acceptance, founder/schema, batch and device-login checks: **221 passed, 1 skipped** (before the last three additional Wave 4 cases; those also pass separately).
- Final Wave 4 focused suite: **14 passed**. Includes actual disposable schema/API, stale/foreign/confirmed/replayed actions, private-setting filtering, source-result projection, original M1 review refresh/receipt, privacy gating, web human-reply isolation, explicit local hours/DST and actual Rig request metadata.
- TypeScript and Next.js production build pass. Actual React views and public widget pass browser checks at 1440 and 375: no page overflow or runtime errors, three linked sources, pending-send prevention, privacy-disabled capture, hand-over and actual cross-origin font loading.
- CI's exact `ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"` prints **All checks passed!** before every push after the founder's lint update. `git diff --check` passes.

All database tests use disposable local Postgres, pytest socket blocking and fake services. Screenshots in [evidence/](evidence/) are labelled placeholder fixtures, not client/production data. Commands/results and corrected local harness/dependency issues are in [verification.txt](verification.txt).

## Deployment / founder proof

Claude opens the PR; no PR was opened, labelled or merged here. No live deployment or production writes were made. Normal deployment needs the existing founder-supplied CRM binding, B1 sources/hand-over settings and M1/M2 connections. Deploy #624's M2 and tenant-admin CRM implementation before Facebook/client-admin use. This branch adds no provider setting, secret, paid service or runtime model route.

The final production acceptance remains the founder viewing his own data on `trigger.tervory.com` at 1440 and on his phone, and checking an embed on his approved store origin. The static host mapping does not attach DNS/TLS or deploy a host by itself.
