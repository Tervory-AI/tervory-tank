# Zenas regulation alerts — stopped at the email-wording requirement

Branch: `codex/zenas-regulation-alerts`, from main `585a900`.

## Blocking requirement

The brief says: “Reuse only existing email words; if new wording is needed, stop and report it.”

The existing mailer in `agents/tiger/alert_email.py:88` constructs only price/stock notifications. Its subject is the existing price/stock change sentence, and its body contains the product name, that sentence and the source URL. It explicitly rejects other alert kinds. These sentences cannot accurately describe a legal change.

The existing Zenas notice is in `agents/zenas/core/service.py:52`: “Zenas provides legal information, not legal advice.” No existing Zenas regulation-change email subject/body template was found in the Zenas code, checked-in Figma specifications or build documentation. The requested generated summary is authorized data, but it does not establish an existing email template under the reuse-only requirement.

**Missing:** an approved law-change email subject/body template specifying how to present the requested summary, source link, date and existing legal-information notice. No subject, greeting, labels or body wording has been invented.

## Changes and verification

Only this report was added. No implementation, page, source adapter, watch, scheduler, SMTP delivery, production-data change or model call was made. No test email was sent and no live/browser success or screenshot is claimed. Tests were not run because no executable file changed.

Commands used for the read-only findings (working directory `/workspace/tervory-tank`):

```sh
cat AGENTS.md
sed -n '/## The rules block/,/## Prompt A/p' docs/build/MILESTONES-28OCT-1NOV.md
cat agents/tiger/alert_email.py
cat agents/zenas/pool/nightly.py
rg -n 'watch|alert|regulation|email' agents/zenas/schema.sql agents/zenas/app.py agents/zenas/core/*.py docs/cursor/CONTEXT.md --glob '*.py' --glob '*.sql' --glob '*.md'
rg -n -i 'email|e-mail|subject|alert|watch|regulat' workspace/app/zenas docs/figma --glob 'SPEC.md' --glob '*.tsx' --glob '*.md'
rg -n '^def letter_for|Price went|Stock changed|return \{"subject"|_LEGAL_NOTICE' agents/tiger/alert_email.py agents/zenas/core/service.py
```

Findings: Tiger has price/stock email copy; Zenas has the legal-information notice and existing on-page deadline alerts, but no law-change email copy. Existing Federal Register/eCFR adapters and the Laws.Africa nightly integration were located; they were not changed after reaching this blocker.

## Decisions I made

Stopped at the explicit email-wording requirement instead of repurposing product-price sentences or creating a new legal-email template. No question or permission request is being made. The founder merges; Claude opens any draft PR. No GitHub API was used.

## Live proof

Not available: no regulation-alert implementation or fixture-driven test email has been produced. The brief's acceptance condition remains outstanding. Once the missing wording is supplied, proof must use the existing source fixtures and a local test mailbox, followed by the founder's real Federal Register watch and next-day email.
