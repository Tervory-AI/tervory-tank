# Autumbra M24 — founder dogfood after deployment

This is a runbook, not a completed live test. The founder runs it after the
reviewed Wave 4 branch is deployed. This build performs no live edge writes,
attack traffic, deployment, email send or merge. Scope is `tervory.com` only.
Record the deployed Git head, UTC start/end, owner tenant UUID and receipt IDs.

## Prepare

1. Deploy the reviewed Ghost image and the existing per-client Enforce resource.
   Follow [the seal procedure](AUTUMBRA-CLOUDFLARE-LIVE.md#deploy-and-verify-the-seal).
   Keep all existing volume names and tenant bindings. Run `ops/seal-check.sh` on
   the host and require the per-client Enforce seal. This is the shield worker,
   distinct from the shared lifecycle-control service.
2. Connect the single-zone Cloudflare token using the named-vault backend in
   [Wave 4](AUTUMBRA-WAVE4.md#m17--connect-backend-and-missing-frames), then bind
   its name to `CLOUDFLARE_API_TOKEN_ENFORCE` on this client's Enforce only.
   Confirm Zone Read and Zone WAF Edit on `tervory.com` only; no account/global
   key. Confirm a free custom-rule slot. Free-plan dogfood uses `block_ip` only.
3. Set `SITE_NAME=tervory.com`, this client's approved HTTPS health path through
   `AUTUMBRA_HEALTH_URL`, and the existing `AUTUMBRA_HEALTH_SECRET` in Enforce and
   observer. Confirm the path returns 2xx through the health proxy before testing.
   Require `read_health('tervory.com')` to return True in the Enforce terminal.
4. Confirm the owner email, tenant queue/settings mirror, never-block CIDRs,
   action cap and chosen shield mode. Prefer the existing “I approve each one”
   mode for this run. Code fixes always wait for a human tap regardless of mode;
   no model second opinion is on the shield path. Never weaken a never-block rule.
5. Confirm Watch's existing `AUTUMBRA_SMTP_HOST`, `AUTUMBRA_SMTP_PORT`,
   `AUTUMBRA_SMTP_FROM`, `AUTUMBRA_SMTP_USER`, `AUTUMBRA_SMTP_PASSWORD`, and signed
   Undo settings are configured. Verify SMTP is active before making the shield:
   the sender intentionally does not email receipts older than SMTP activation.
   Keep the owner's real inbox, Cloudflare dashboard and receipt view open.
6. Choose a disposable, explicitly authorized external test source. It must not
   be on any never-block/client-owned CIDR and must not share an address with
   customers, office access, monitoring, search crawlers or the health observer.
   If no suitable source exists, use the documentation-address test in the older
   runbook as API-only proof and mark real-traffic dogfood incomplete.

## Make one controlled test event

From that test source make at most five ordinary HTTPS GETs, one second apart,
to a harmless test path on `tervory.com` with the test User-Agent
`Autumbra-Founder-Dogfood`. No exploit, credential attempt or load test is needed.
Record its actual source address from the site's existing edge/request logs;
this log evidence, not a caller's guessed address, identifies the source.

Feed that bounded, real test log line through the existing internal Watch relay.
Cloudflare alert notifications do not promise attacker-IP fields; do not invent
an IP from an alert, call a fixture endpoint, or pretend this internal handoff
is a provider-delivered notification. In Watch's existing browser terminal, use:

```python
import json, os, time, uuid
import httpx
from ghost.webhooks import sign_body

# Non-secret identifiers/log line entered interactively, never written to a file.
tenant = input('Dogfood tenant UUID: ').strip()
address = input('Observed disposable source address: ').strip()
line = input('One matching bounded test log line: ')
body = json.dumps({'tenant_id': tenant, 'site': 'tervory.com',
                   'address': address, 'raw_log': line,
                   'reason': 'Founder-authorized controlled dogfood event'}).encode()
ts, nonce = str(int(time.time())), str(uuid.uuid4())
headers = {'X-Tank-Key': os.environ['TANK_KEY'],
           'X-Autumbra-Timestamp': ts, 'X-Autumbra-Nonce': nonce,
           'X-Autumbra-Signature': sign_body(
               secret=os.environ['AUTUMBRA_EDGE_WEBHOOK_SECRET'],
               body=body, timestamp=ts, nonce=nonce)}
with httpx.Client(trust_env=False, follow_redirects=False) as client:
    response = client.post('http://127.0.0.1:8000/ghost/autumbra/webhooks/edge',
                           content=body, headers=headers, timeout=10)
    response.raise_for_status()
    result = response.json()
    print({'accepted': result['accepted'], 'queued': result['queued'],
           'queue_item_id': (result.get('queue_receipt') or {}).get('queue_item_id')})
```

Never print headers, environment values, bearer tokens or signed Undo URLs.
The source log remains in working memory and never crosses into Enforce.

If the selected mode requires approval, find the pending receipt for that queue
item in this tenant's existing receipt view. Tap its existing shield approval
once. If the approval surface is unavailable, the founder can enqueue exactly
that pending receipt using Watch's authenticated `/ghost/autumbra/queue/approve`
backend with `tenant_id`, `site: tervory.com`, and `prior_receipt_id`; do not change
the mode or bypass the queue/never-block checks. This is an explicit founder
approval, never an automatic code fix. If the client chose Never, expect a
report-only receipt; no applied-shield acceptance is possible in that mode.

## Verify the edge, health, receipt and email

Require a receipt with `control: cloudflare`, `measurement_path: real_edge`, the
owned rule ID, `applied: true`, and `health_ok: true`. It must contain a real
`health_probe` URL/status/ms whose checked_at is after applied_at, the edge
request durations/statuses, and speed-budget outcomes. Require decision ≤2s,
confirmed shield ≤10s, queue transit ≤5s, event-to-shield ≤15s and health ≤30s.
Retain actual overruns as failed acceptance; never relabel them as passes.
Human waiting before approval is not counted as edge execution latency.

In Cloudflare, verify exactly that host-scoped source-IP rule, retaining an
unrelated rule for comparison. From the disposable source repeat one harmless
GET and verify the edge blocks it. A clean source and the health observer must
still receive a healthy site. Do not count an API write alone as blocked-traffic
proof. Receipts naming fixture_edge, missing timings or stale health fail this run.

Wait for Watch's normal action-email poll (30 seconds, plus SMTP delivery).
Open the actual delivered owner email. Match its shield/report to this tenant's
receipt, and verify its signed Undo link works. A fixture transport, generated
email preview, send attempt or SMTP uncertainty is not inbox-delivery evidence.

Tap Undo once in that email's existing page. Require a new owned-rule Undo
receipt, actual API DELETE timing, and total queue-to-Undo ≤60s. Refresh
Cloudflare and verify that rule ID is absent while the unrelated rule remains.
From the disposable source verify one GET reaches the site again. Health must
remain healthy. A second Undo tap must show the existing already-undone state.

For automatic-Undo acceptance, separately use a founder-controlled health path
that deterministically returns failure, authorize one more disposable-source
shield, and require `auto_undone_health_failed`, post-write failed GET evidence,
owned-rule removal and Undo ≤60s. Restore the healthy URL afterwards. Never
break the production application to manufacture this test. If a controlled
health-failure path is unavailable, record that sub-check as pending.

## Evidence and cleanup

Save the deployed head, UTC times, queue/receipt IDs, actual receipt JSON and
screenshots of the owned Cloudflare rule, blocked test GET, delivered owner
email, Undo receipt and rule absent after Undo. Exclude secret values and
signed-link query strings. Record each speed stage's seconds and pass/fail;
link it to the same rule and receipt. Confirm no test rule remains and stop the
test source. If the edge result is unconfirmed, inspect the owned rule before
retrying. If Undo fails, remove only the owned test rule in Cloudflare and retain
the failure evidence; never delete an entire ruleset or another rule.

Provider-specific acceptance is separate: use Cloudflare's dashboard test with
`cf-webhook-auth`, and deliver a genuine Alert Center notification through the
configured authenticated Pub/Sub subscription. An internal HMAC test cannot
stand in for either provider's authentication evidence.
