# ML6: monthly opportunities brief delivery

Same branch `codex/market-lab-w3`, same PR [#640](https://github.com/Tervory-AI/tervory-tank/pull/640).
ML5 remains on this branch. ML7 remains parked. No main merge was performed.
Claude reviews; the founder merges. No deployment or production data change.

The opportunities job now saves its existing report and two channel claims in
one room transaction. The title is the existing report's `question`; its saved
`answer` and `citations` are the only mail body inputs. No subject, greeting,
heading, footer, page, label, empty-state or error copy was invented.

The existing monthly schedule is unchanged. The existing minute alert tick now
also drains brief claims using the room ledger. Email reuses
`agents.tiger.alert_email.deliver_pending`, configuration, recipient mapping and
Rig SMTP transport unchanged. Brief webhooks use ML3's existing signer, sealed
setting, SSRF-safe transport and Idempotency-Key through a shared helper, also
used by warnings. Only report ID, title, saved text and citations form the brief
webhook payload. No webhook credential leaves Tank.

## Claims, gates and status

- State lives in `agent_market_lab.brief_deliveries`, keyed by tenant/report/channel.
  The room schema remains additive and idempotent. All new queries are literal
  SQL with `$n` parameters and tenant predicates. No new Tank table or setting.
- Report insertion and its two initial claims commit together. A failed outbox
  insert rolls back the report too. Concurrent pending-to-sending transitions
  have one winner, tested with separate real PostgreSQL connections.
- A gate check reuses ML4's `gated_facts` before saving and immediately before
  each claim. Closed, missing or foreign predictive citations hold the report,
  recording `closed_or_unavailable_citation` in its channel status reason. Held
  claims are not automatically released later.
- Existing alert settings and opt-in timestamps are checked before dispatch.
  Disabled channels and reports predating the current opt-in are suppressed
  when inspected. No fallback recipient or URL exists.
- Sending is committed before transport. A crash between acceptance and finish
  leaves `sending`, never reclaimed automatically. Lost/failed webhook replies
  become `uncertain`; they are never automatically resent. Tiger retains its
  existing retry behavior for SMTP transactions that were definitely rejected.
- `market_lab.briefs` is an exact code command through ML3's existing READS route
  and pending Confirm-card flow. It reads only the tenant's last 12 monthly briefs
  (identified by the outbox), with per-channel statuses and a $0 code receipt.

## File and line manifest

| File | Line | Change |
| --- | --- | --- |
| `agents/market_lab/schema.sql` | 108 | Room-owned report/channel claims and pending index. |
| `agents/market_lab/core/ledger.py` | 36, 116, 532 | Memory/SQL outbox methods, atomic save, claim transition and last-12 reads. |
| `agents/market_lab/core/briefs.py` | 1 | Gate validation, exact saved-content letters and channel dispatcher. |
| `agents/market_lab/core/jobs.py` | 232 | Save and queue the opportunities report atomically. |
| `agents/market_lab/core/ml3.py` | 41, 94 | Briefs read and existing alert dispatch extension. |
| `agents/market_lab/app.py` | 152 | Supply the room ledger on the existing alert tick. |
| `tank/market_lab_ml3.py` | 25, 48, 198, 235, 274 | READS/projection, shared warning/brief webhook signer and room-only settings/delivery operations. |
| `tank/command.py` | 44, 1359 | Register the briefs tool and read adapter. |
| `tests/test_market_lab_ml6.py` | 1 | Ten offline SQL/SMTP/webhook/clock/scope/crash checks. |
| `tests/market_lab_ml6/verification.txt` | 1 | Exact commands, captured successful results and corrected setup failures. |
| `tests/market_lab_ml6/HANDOFF.md` | 1 | This handoff and remaining acceptance. |

## Verification

Source head tested: `1282aa069274806bf439b2892b27a7066dd9a3f0`. Later commits
record evidence only. Full commands and outputs: [verification.txt](verification.txt).

- Market Lab/feed/research/consumer/access selection plus Tiger mail: **337 passed,
  9 skipped**. Includes all ten new ML6 checks and the ML3/ML5 reads and receipts.
- Separate Tiger G5 group: **20 passed, 26 skipped**.
- Ruff E9/F on changed Python files and `git diff --check fc26952f`: passed.
- Initial new-test import/async-fixture errors were corrected. An initial targeted
  Tiger formatter failure was an absent Workspace TypeScript install; the existing
  lockfile was installed with `npm ci --ignore-scripts --no-audit --no-fund`, then
  the broad run passed. No Tiger source, package manifest or lockfile changed.

Tests disable outside sockets/DNS; pgserver, fake SMTP and the ASGI webhook
receiver stay local. TMPDIR is `/workspace/codex-market-lab-w3/.tmp`. No test
containers, production SQL, real recipient or model/provider call was used.
Existing optional integration/database checks retain their skips; no skipped
case is claimed as executed. Every finished file was committed and pushed
serially on this same branch; no push failed.

## Limits and founder acceptance still outstanding

The pre-existing opportunities generator saves an empty citation list. This
change preserves that behavior and does not fabricate sources. If a saved brief
contains citations, they are checked and delivered; local proof covers an actual
saved citation link and both open- and closed-cohort prediction references.
Producing additional citations is not claimed here.

The read uses existing Name, Summary and Status labels. Report IDs, citation
objects and delivery reasons remain structured response fields; dedicated UI
labels for them need an approved Figma frame. No Workspace file changed.

CI is the full-suite result of record. Source-head Tank shards and Workspace
were queued in run 41736299802 when checked. Final-head CI status is recorded in
the PR after these evidence commits; no queued run is called a pass.

After review, merge and deployment, the founder must enable his existing email
setting, run/wait for the existing opportunities job, receive his real saved
brief, verify any saved citation links, and confirm `market_lab.briefs` shows its
channel as sent with a $0 receipt. Capture the founder's actual browser/email
screenshots in the PR. No founder delivery, screenshots or DONE acceptance are
claimed by the offline proof. No merge, label or PR creation was performed.
