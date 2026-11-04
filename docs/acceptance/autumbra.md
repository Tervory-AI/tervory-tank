# Autumbra — founder testing sheet

Baseline: acceptance branch rebased onto Claude's main merge `2e8b69c4`.
A01–A60 are feature/safety checks. P05, P06 and P11 now check the Wave 4
routes' authentication and input validation (401/422); these negative checks do
not prove a successful connection or alert intake. Other P rows still check
unavailable Wave 3 routes (404), not functional acceptance of #622. No unmerged
/chats command or missing connect screen is advertised as working.

Settings names were checked against
`docs/ops/FOUNDER-SETTINGS.md` on `origin/claude/founder-settings` (PR #657),
with this product's existing optional flag names from `.env.example`. Use the
register's exact names; enter values in the service's secret panel, never here.
The register's Autumbra heading groups names, not service placement: edge write
credentials belong only on the per-client Enforce service; SMTP and webhook
verification settings belong on Watch; lifecycle settings belong only on the
lifecycle service, with its HMAC key also on Tank. Never copy all of them to Watch.

`none` means no additional founder-filled setting for that row. Existing managed
service keys, founder authentication and this tenant's queue/settings bindings
are baseline deployment prerequisites. Optional OSS flags remain off outside
an isolated acceptance check. Do not enable brain/model flags or buy a service.

## Exact execution instructions

- Public URLs use `https://app.tervory.com`. A01, A57, A58 and A59 execute the
  actual page or HTTP handler offline, not copied HTML. Follow the supplied
  owner email link for signed receipt/Undo pages; never type a token from chat.
- Private URLs are called from **Coolify → Tank application → Terminal** using
  the helper below. They are not public browser addresses. For a per-client
  Enforce URL, use that client's Enforce terminal/queue; do not attach it to Tank.
  The `enforce` service name resolves inside that existing per-client project.
- Replace `A` with your disposable dogfood tenant UUID and `B` with a second
  disposable tenant. Offline fixtures use A=`aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`,
  B=`bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`. Never use a real client's tenant.
  Replace `<incident>`, `<shield>`, and `<tenant>` with IDs returned by the prior
  step; repeat with the same ID where the sheet says to test idempotence.
- Rows that say “fixture” or inject failure are run against the isolated
  acceptance deployment/fixture provider, not production. Do not add a fixture
  success flag to a real edge worker. Real traffic, certificate/egress reachability,
  dashboard state and inbox delivery still require founder observation; a mocked
  provider response or SMTP capture is not live evidence. For the real dogfood
  source/block/Undo sequence use the reviewed Cloudflare live-hand runbook.
- The JSON values in the action column are the exact request data. Unquoted A/B
  mean the UUID substitutions above, not literal JSON identifiers. A “then” step
  is part of the same row. Use POST unless GET is explicitly stated. Enforce
  drains are POST with no body. All earlier incident/proposal setup is seeded
  automatically by that row's offline case.

Private Watch request helper (enter method, exact private URL and row JSON):

```python
import json, os, httpx
method = input('GET or POST: ').strip().upper()
url = input('Private Watch URL from the row: ').strip()
body = input('JSON, or blank for no body: ').strip()
with httpx.Client(trust_env=False, follow_redirects=False) as client:
    response = client.request(method, url,
        headers={'X-Tank-Key': os.environ['TANK_KEY_GHOST']},
        json=json.loads(body) if body else None, timeout=90)
def safe(value):
    if isinstance(value, dict):
        return {k: '[redacted]' if k.lower() in {'token','signature','authorization'} else safe(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, str) and 'token=' in value:
        return value.split('?')[0] + '?[signed link redacted]'
    return value
print(response.status_code, safe(response.json()))
```

Do not use this helper for provider callbacks: Cloudflare uses `cf-webhook-auth`,
Google uses its signed bearer token, and internal relay rows use their documented
HMAC. Do not substitute the generated room key for provider verification. The
lifecycle/owner-facing public doors each have their own documented authorization.

## Rows

| ID | Where (exact URL/path) | What the founder does | Exact expected result | Setting it needs |
| --- | --- | --- | --- | --- |
| A01 | https://app.tervory.com/autumbra | Open https://app.tervory.com/autumbra without signing in. | Watch the edge.; Keep the proof.; Autumbra Watch; Autumbra Enforce | none |
| A02 | http://agent-ghost:8000/incidents | GET without X-Tank-Key. | HTTP 404; detail=Not found. | none |
| A03 | http://agent-ghost:8000/look | POST {"target":"workspace","signal":"health"} with a reproduced 503. | state=needs_review; brief.status=awaiting_founder_approval; cost_usd=0 | none |
| A04 | http://agent-ghost:8000/look | POST {"target":"workspace","signal":"health"} with a healthy probe. | state=not_reproduced; no executable fix | none |
| A05 | http://agent-ghost:8000/look | POST {"target":"workspace","signal":"human_check"}. | state=human_required; A human check needs a person. Autumbra Watch has stopped. | none |
| A06 | http://agent-ghost:8000/alert | POST the same {"target":"workspace","signal":"health","failing":true,"status_code":503} twice. | same incident id; one open incident | none |
| A07 | http://agent-ghost:8000/incidents/<incident>/resolve | POST {"cause":"application_bug","fix":"reviewed_pr_deployed"} while original probe still fails. | HTTP 409; The original check must pass before solving the issue. | none |
| A08 | http://agent-ghost:8000/incidents/<incident>/resolve | After the original probe passes, POST the same resolution, then repeat Look and GET /gold/candidates. | state=solved; next incident recalls reviewed_pr_deployed; gold.public=false | none |
| A09 | http://agent-ghost:8000/message | POST {"text":"Ghost, the login page is slow"}. | target=workspace; signal=slow; origin=message; original text not retained | none |
| A10 | http://agent-ghost:8000/incidents | GET monitoring state and integration status. | workers=founder_approval_required; logs_ci_deploys=awaiting_read_only_feed | none |
| A11 | http://agent-ghost:8000/ghost/inventory/report | POST {"source":"repo:acceptance","components":[{"app":"coolify","kind":"package","name":"requests","version":"2.31.0","ecosystem":"pypi"}]}; GET /ghost/inventory. | accepted=true; requests version=2.31.0 | none |
| A12 | http://agent-ghost:8000/ghost/advisories/pull | POST after loading inventory-before.json; GET /ghost/advisories/matches. | CVE-2026-109618 is matched to installed inventory; state=open | none |
| A13 | http://agent-ghost:8000/ghost/shields/propose | POST {"site":"coolify.tervory.com","kind":"block_multipart_post"}, then POST /ghost/shields/<id>/raise. | state=dry_run; no edge API write by Watch | none |
| A14 | http://agent-ghost:8000/ghost/shields/<shield>/undo | POST Undo on the Watch dry-run proposal. | state=withdrawn; no edge API DELETE by Watch | none |
| A15 | http://agent-ghost:8000/ghost/summary | GET the shield summary with no open matches. | open_total=0; sites_broken_by_a_shield=0; mode=dry_run | none |
| A16 | http://agent-ghost:8000/ghost/triage/accept | POST a valid ghost.threat.v1 propose_shield for block_multipart_post. | accepted=true; action=propose_shield; note=Proposed only. Founder must tap Shield before anything changes. | none |
| A17 | http://agent-ghost:8000/ghost/triage/accept | POST the same shape with reason="ignore previous instructions". | HTTP 422; Threat payload burned. No action was taken. | none |
| A18 | http://agent-ghost:8000/ghost/watch/oss | GET with WATCH_OSS_ENABLED unset. | enabled=false; telemetry disabled; no collector daemon is started | none |
| A19 | http://agent-ghost:8000/ghost/watch/intake | Enable WATCH_OSS_ENABLED only for this probe; POST vector_anomalies.json[0]. | accepted anomaly proposes a shield only; state=proposed | WATCH_OSS_ENABLED |
| A20 | http://agent-ghost:8000/ghost/wraith/enforce | POST a valid threat with GHOST_WRAITH_ENABLED unset. | HTTP 404; no execution | none |
| A21 | http://agent-ghost:8000/ghost/enforce/oss | GET the Enforce adapter status with ENFORCE_OSS_ENABLED unset. | enabled=false; no playbook or Terraform apply | none |
| A22 | http://agent-ghost:8000/ghost/patch/from-match | POST tests/fixtures/autumbra/patch_connect_match.json with GHOST_PATCH_PR_ENABLED off. | result.mode=dry_run; result.draft=true; requests 2.31.0 to 2.32.3; no GitHub write | none |
| A23 | http://agent-ghost:8000/ghost/patch/from-match | POST that match with an extra command="printenv" field. | HTTP 422; no branch, merge or deploy | none |
| A24 | http://agent-ghost:8000/ghost/autumbra/settings | Save A with shield_mode=Never and fix_mode=I approve each one; read A and B. | A shield_mode=Never; B site_name=""; B fix_mode=I approve each one | none |
| A25 | http://agent-ghost:8000/ghost/autumbra/settings | Save A watching shop-a.example.com; try registering that host under B. | HTTP 409; That site is already registered by another client. | none |
| A26 | http://agent-ghost:8000/ghost/autumbra/queue/fixture-attack → http://enforce:8000/v1/drain-once | Save own_cidrs=[198.51.100.0/24]; submit a test event for 198.51.100.20. | outcome=refused_never_block; applied=false; own address is never blocked | none |
| A27 | http://agent-ghost:8000/ghost/autumbra/hands | POST {"tenant_id":A,"hand":"host_firewall","connected":true}; read hands for A and B. | A block_in_seconds=true; B block_in_seconds=false; optional=true/required=false | none |
| A28 | http://agent-ghost:8000/ghost/autumbra/intel/consume | POST the free fixture IOC bundle from abuse.ch Feodo via Market Lab. | accepted=true; indicator_count=1; receipt.sources[0].via=Market Lab; client_visible_feed_list=false | none |
| A29 | http://agent-ghost:8000/ghost/autumbra/intel/consume | POST the same IOC bundle with paid=true. | HTTP 422; paid feeds are off at launch; public + Market Lab only | none |
| A30 | http://agent-ghost:8000/ghost/autumbra/webhooks/edge | Send one timestamp/nonce/body HMAC-signed internal test event; send it again. | first HTTP 200; replay HTTP 401; raw body not stored | AUTUMBRA_EDGE_WEBHOOK_SECRET |
| A31 | http://agent-ghost:8000/ghost/autumbra/webhooks/cloudflare | Cloudflare Alerts → Destinations → webhook → Save and Test with the configured secret. | valid cf-webhook-auth HTTP 200, accepted=true, queued=false; bad header HTTP 401 | AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET |
| A32 | http://agent-ghost:8000/ghost/autumbra/webhooks/google_workspace | Google Cloud Console → Pub/Sub → existing topic → Messages → Publish message → Message body={} → Publish; authenticated push uses the configured audience and service-account email. | valid Google-signed RS256 push HTTP 200, queued=false; wrong audience HTTP 401 | AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT |
| A33 | http://agent-ghost:8000/ghost/autumbra/queue/fixture-attack → http://enforce:8000/v1/drain-once | In an isolated fixture tenant, submit a test IP event with I approve each one; drain once. | outcome=awaiting_approval; applied=false; no edge rule added | none |
| A34 | http://agent-ghost:8000/ghost/autumbra/queue/approve → http://enforce:8000/v1/drain-once | Approve exactly the pending receipt from A33; drain once. | control=cloudflare; outcome=applied; applied=true; health_ok=true; rule is host-scoped | CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_HEALTH_SECRET |
| A35 | http://enforce:8000/v1/drain-once | Drain an authorized shield whose fresh post-write health result fails. | outcome=auto_undone_health_failed; applied=false; owned rule removed, unrelated rule retained | CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_HEALTH_SECRET |
| A36 | http://agent-ghost:8000/ghost/autumbra/queue/undo → http://enforce:8000/v1/drain-once | Undo one applied receipt, drain, then tap the same Undo again. | outcome=undone; second outcome=already_undone; queued=false; unrelated rule retained | CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_HEALTH_SECRET, AUTUMBRA_UNDO_TOKEN_SECRET |
| A37 | http://enforce:8000/v1/drain-once | After this tenant reaches its configured action cap, submit another proposal and drain. | outcome=refused_action_cap; applied=false | none |
| A38 | http://enforce:8000/v1/apply | POST a JSON body directly instead of a validated queue payload. | HTTP 415; accepted=false; raw_log_seen=true | none |
| A39 | http://agent-ghost:8000/ghost/autumbra/receipts | Read A receipts after one A event, then read B receipts. | A count=1 with timestamp and tenant_id=A; B count=0 | none |
| A40 | http://agent-ghost:8000/ghost/autumbra/receipts/weekly/<tenant> | Open the owner weekly page using a valid signed link for A; reuse the token for B. | A HTTP 200, kind=weekly_receipts, time_zone=America/Los_Angeles; B HTTP 401 | AUTUMBRA_UNDO_TOKEN_SECRET |
| A41 | http://agent-ghost:8000/ghost/autumbra/owner-update | POST {"tenant_id":A} with no receipt this week, then repeat. Inspect the owner inbox. | sent=true then sent=false; transport=smtp; subject/body say Quiet week.; exactly one owner email | AUTUMBRA_SMTP_HOST, AUTUMBRA_SMTP_PORT, AUTUMBRA_SMTP_USER, AUTUMBRA_SMTP_PASSWORD, AUTUMBRA_SMTP_FROM |
| A42 | http://agent-ghost:8000/ghost/autumbra/owner-update | Try a different recipient via settings.owner_email in the request body. | HTTP 422; request cannot name the recipient; no mail sent | AUTUMBRA_SMTP_HOST, AUTUMBRA_SMTP_PORT, AUTUMBRA_SMTP_USER, AUTUMBRA_SMTP_PASSWORD, AUTUMBRA_SMTP_FROM |
| A43 | http://agent-ghost:8000/ghost/autumbra/jobs | GET the registered schedule. | job id=autumbra_weekly_owner_update; cadence=weekly | none |
| A44 | http://agent-ghost:8000/ghost/autumbra/enforce/plan-create | POST {tenant_id:A,existing_count:0,execute:false}; repeat for B. | different project names and data volumes; routes_to_queue_only=true; no deployment | none |
| A45 | http://agent-ghost:8000/ghost/autumbra/enforce/plan-destroy | POST {tenant_id:A,execute:false}. | plan.action=destroy_enforce; receipt.outcome=planned; no deletion executed | none |
| A46 | http://agent-ghost:8000/ghost/autumbra/exercises/run | POST credential_stuffing_fixture for coolify.tervory.com, then try evil.example. | own-site receipt.kind=exercise; unauthorized site HTTP 403 | none |
| A47 | https://tervory.com/ (GET by the health observer) | Run one fixture HTTPS GET to https://tervory.com/ through the health observer; inspect signed result. | GET only, no body/cookies; signed status=200; fresh result true; tampered signature false | AUTUMBRA_HEALTH_SECRET |
| A48 | http://enforce:8000/v1/drain-once | Drain one allowed fixture event and inspect the persisted receipt timings. | numeric nonnegative seconds for queue_transit, decision_to_shield, health_check, event_to_shield_e2e | none |
| A49 | http://enforce:8000/v1/drain-once | Place an invalid queue item before a valid test item; drain once. | quarantined receipt exists; valid following item is processed; raw logs are not executed | none |
| A50 | http://agent-ghost:8000/ghost/autumbra/webhooks/cloudflare | Send an internal X-Autumbra-Signature instead of Cloudflare authentication. | HTTP 401; internal HMAC cannot authenticate a provider URL | AUTUMBRA_EDGE_WEBHOOK_SECRET |
| A51 | http://agent-ghost:8000/ghost/autumbra/webhooks/google_workspace | Send internal X-Autumbra-Signature instead of a Google-signed bearer token. | HTTP 401; internal HMAC cannot authenticate a Google URL | AUTUMBRA_MAILBOX_WEBHOOK_SECRET |
| A52 | http://agent-ghost:8000/ghost/autumbra/jobs → registered ghost.owner_email_jobs.run_weekly_owner_updates | Allow the registered weekly job to run twice for the same fixture week; inspect the owner inbox. | one SMTP email only; Quiet week.; second result sent=false | AUTUMBRA_SMTP_HOST, AUTUMBRA_SMTP_PORT, AUTUMBRA_SMTP_USER, AUTUMBRA_SMTP_PASSWORD, AUTUMBRA_SMTP_FROM |
| A53 | http://agent-ghost:8000/ghost/autumbra/queue/approve → Watch action-email poll | After one shield is applied, wait for the 30-second Watch email poll; poll again. | one SMTP email to the saved owner; real receipt counts; no duplicate email | AUTUMBRA_SMTP_HOST, AUTUMBRA_SMTP_PORT, AUTUMBRA_SMTP_USER, AUTUMBRA_SMTP_PASSWORD, AUTUMBRA_SMTP_FROM, AUTUMBRA_UNDO_TOKEN_SECRET |
| A54 | http://enforce:8000/v1/drain-once | Apply a fixture rule, restart the control from its durable table, then queue Undo and drain. | owned Cloudflare rule survives restart and is undone; unrelated rule remains | CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_HEALTH_SECRET |
| A55 | http://agent-ghost:8000/ghost/autumbra/queue/fixture-attack | Submit a test log naming Cloudflare address 104.16.1.1. | queued=false; Cloudflare infrastructure is never blocked | none |
| A56 | http://agent-ghost:8000/ghost/autumbra/exercises/run | Try path_scan_fixture on client.example without permission, then save red_team_permission=true and retry. | without permission HTTP 403; with saved permission kind=exercise | none |
| A57 | https://app.tervory.com/api/autumbra/undo | POST {} to https://app.tervory.com/api/autumbra/undo. | HTTP 401; This undo link is invalid or has expired. | none |
| A58 | https://app.tervory.com/autumbra/receipts/weekly/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa?token=expired | Open https://app.tervory.com/autumbra/receipts/weekly/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa?token=expired. | Your Autumbra weekly update; This link is invalid or has expired.; no receipt rows | none |
| A59 | https://app.tervory.com/api/autumbra/undo | Tap the owner email Undo link for A; an extra body tenant_id=B must be ignored. | ok=true; queued=true; forwarded tenant_id=A and original receipt/rule only | AUTUMBRA_UNDO_TOKEN_SECRET |
| A60 | http://enforce:8000/v1/drain-once | Queue one rate_limit proposal on /autumbra-check with a Free-plan fixture. | outcome=refused_plan; cloudflare_plan=free; applied=false; no edge write | CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_HEALTH_SECRET |
| P01 | http://agent-ghost:8000/ghost/autumbra/enforce/list | Probe live lifecycle list before #622 is deployed. | HTTP 404 on this main snapshot: unavailable, not a successful live-lifecycle test | AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN, AUTUMBRA_COOLIFY_PROJECT_UUID, AUTUMBRA_COOLIFY_SERVER_UUID, AUTUMBRA_COOLIFY_ENVIRONMENT, AUTUMBRA_COOLIFY_GITHUB_APP_UUID, AUTUMBRA_LIFECYCLE_KEY |
| P02 | http://agent-ghost:8000/ghost/patch/fixes | Probe the Wave 3 stored-match fixes list before #622 is deployed. | HTTP 404: unavailable; do not invent a working /chats command | GHOST_GITHUB_TOKEN, GHOST_PATCH_PR_ENABLED |
| P03 | http://agent-ghost:8000/ghost/autumbra/blocks | Probe standing shared-block evidence before #622 is deployed. | HTTP 404: unavailable; no cross-client memory claim | none |
| P04 | http://tank:8000/v1/ghost/autumbra/blocks/share | Probe founder-only policy-checked publication before #622 is deployed. | HTTP 404: unavailable; no platform record published | none |
| P05 | http://tank:8000/v1/vaults/ghost.vault/autumbra/connect/cloudflare | POST {} without authentication to the named client-vault connection. | HTTP 401: authentication required; no client-vault connection created | CLOUDFLARE_API_TOKEN_ENFORCE |
| P06 | http://agent-ghost:8000/ghost/autumbra/connections/google_workspace | POST {} with the managed Watch key to the tenant-bound Alert Center connect route. | HTTP 422: Google connection was not understood.; no connection saved | AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT |
| P07 | http://tank:8000/v1/ghost/autumbra/enforce/create | Probe founder-confirmed live create before #622 is deployed. | HTTP 404: unavailable; no Coolify resource created | AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN, AUTUMBRA_COOLIFY_PROJECT_UUID, AUTUMBRA_COOLIFY_SERVER_UUID, AUTUMBRA_COOLIFY_ENVIRONMENT, AUTUMBRA_COOLIFY_GITHUB_APP_UUID, AUTUMBRA_LIFECYCLE_KEY |
| P08 | http://tank:8000/v1/ghost/autumbra/enforce/destroy | Probe founder-confirmed live destroy before #622 is deployed. | HTTP 404: unavailable; no resource deleted | AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN, AUTUMBRA_LIFECYCLE_KEY |
| P09 | http://tank:8000/v1/ghost/autumbra/fix/approve | Probe the Wave 3 one-tap stored-match fix command before #622 is deployed. | HTTP 404: unavailable; no code fix dispatched | GHOST_GITHUB_TOKEN, GHOST_PATCH_PR_ENABLED |
| P10 | http://tank:8000/v1/ghost/autumbra/blocks/withdraw | Probe platform-block withdrawal before #622 is deployed. | HTTP 404: unavailable; no memory record deleted | none |
| P11 | http://tank:8000/v1/vaults/ghost.vault/autumbra/alerts | GET the tenant-bound Alert Center receipts URL without the required tenant_id query. | HTTP 422: required tenant_id query missing; no mailbox content exposed | AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT |

## Offline proof and deployment gaps

Each row maps to the same-ID pytest node:
`tests/acceptance/test_autumbra.py::test_founder_row[A01]` through `[A60]`,
and `[P01]` through `[P11]`. A separate integrity check prevents rows or fixture
cases silently disappearing. Tests use the actual Watch and Enforce ASGI routes,
existing SQLite/queue/persistence code, real token verification and draft-plan
logic, actual Next public handlers/pages, and the existing SMTP adapter. Provider
HTTP, observation signals, Tank receipt acknowledgements and SMTP delivery are
fixture boundaries. No test opens a PR, deploys, sends email or calls a model.

```bash
python -m pytest -q tests/acceptance/test_autumbra.py \
  --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
```

Wave 3 capabilities and positive Wave 4 connection acceptance remain unproved here:
live lifecycle list/create/destroy and separate key; stored-match one-tap fixes;
24-hour standing block evidence, founder policy-checked seven-day publication
and source-Undo withdrawal; successful named single-zone client vault connection and tenant-bound Alert
Center intake. Wave 4 configurable client health paths and richer per-request
budget summaries are on main; the existing A rows retain their narrower contracts. Existing main provides real edge apply/owned Undo,
signed root-URL health observation, provider-native verification, raw-log air gap,
measured numeric budgets and owner email paths, which the A rows exercise.

Missing frames remain: optional-connections chooser; Cloudflare scoped named-token
entry/validation/awaiting-binding states; Google topic/subscription/customer setup,
waiting/verified/error states; connection replacement/disconnect; the unmerged
founder stored-match and shared-block command projections. Do not manufacture a
new route or claim a UI exists. No UI files are changed by this acceptance PR.

One acceptance regression exposed provider URLs accepting an internal HMAC in
place of native verification. This branch fixes that dispatch; A50/A51 prove the
provider doors reject the internal scheme, and A30 proves the relay still works.
