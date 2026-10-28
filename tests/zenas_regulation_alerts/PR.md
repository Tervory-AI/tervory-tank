# Zenas daily civil-law change alerts

Branch: `codex/zenas-regulation-alerts`. Latest main merged: `b08ff95`.

Implementation in progress; keep the PR a draft. Claude opens it. No deployment or live acceptance is claimed.

## Approved email copy

Founder approved this exact copy on 28 October:

Subject: `Law change: {title}`

Body (one item per line):
```
{title}
{summary}
Source: {link}
Date: {date}
Zenas provides legal information, not legal advice.
```

The notice is reused from `agents/zenas/core/service.py` (#372).

## Scope

Daily source comparison, durable tenant watch/change records, summaries through Tank's existing cheap plain-language route, SMTP using the Tiger delivery pattern, and offline proof including a local test mailbox. No Workspace page changes. Congress.gov and LegiScan remain off without their named keys; Laws.Africa remains ZA-only and off without its token. No API key is placed in a URL.

## Proof

Pending implementation and offline checks. No founder browser screenshots are available from this cloud session; the founder's assessor performs live acceptance after deployment.
