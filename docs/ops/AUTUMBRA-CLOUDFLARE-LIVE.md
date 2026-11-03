# Autumbra Cloudflare live hand — tervory.com only

Founder authorization: 3 November 2026, 02:47 America/Los_Angeles.
The founder merges PR #566. This guide does not authorize other zones, client
tokens, page changes, model calls, or changes to the existing safety rules.

## Before deploying

1. In Cloudflare, select **tervory.com**. Under **Security → Security rules**,
   confirm the zone's current plan. On Free, inspect custom rules and confirm
   one available custom-rule slot for the host-scoped `block_ip` test below.
   Only for the Pro-plan variant, confirm a rate-limit slot and support for the
   existing fixed parameters in `agents/ghost/shields.py`. Stop if unavailable;
   do not change plans, quotas, existing rules, or the fixed parameters.
   Free or missing plan data refuses `rate_limit` and `waf_managed` before any
   write, with `applied=False`, the fixed error and `cloudflare_plan` in the
   receipt. No path-only rewrite or fixture fallback is allowed.
2. Create a **custom API token** with resource scope
   **Include → Specific zone → tervory.com** and only these permissions:
   **Zone → Zone → Read** and **Zone → WAF → Edit**. No DNS permission,
   account-wide scope, other zones, or global API key. The founder alone handles
   the value, directly in Coolify; never paste it into chat, logs or a command.
3. In the existing per-client **Enforce** Coolify project, set these names:
   `CLOUDFLARE_API_TOKEN_ENFORCE`, `AUTUMBRA_HEALTH_SECRET`, and `SITE_NAME`.
   Compose gives the latter to Enforce and its observer only. Neither proxy
   receives either value. Watch never receives either value.
4. Retain this client's existing `TENANT_ID`, `ENFORCE_NETWORK_NAME`,
   `ENFORCE_DATA_VOLUME` and `THREAT_PAYLOAD_QUEUE_VOLUME` bindings. Do not reuse
   another client's project, network or volumes. The existing settings mirror
   must identify `tervory.com` and the founder's owner email. Keep the existing
   client mode and action cap; a report-only mode does not apply a rule.
5. Confirm the existing signed Undo setting `AUTUMBRA_UNDO_TOKEN_SECRET` is
   configured by the founder in its existing locations. A2 owns owner-email
   delivery and durable action caps. Its production email delivery must be
   working before M24; fixture email delivery does not prove inbox delivery.

Cloudflare references: [zone lookup](https://developers.cloudflare.com/api/resources/zones/methods/list/),
[rate limiting via API](https://developers.cloudflare.com/waf/rate-limiting-rules/create-api/),
[zone WAF permission](https://developers.cloudflare.com/waf/custom-rules/custom-rulesets/).

## Deploy and verify the seal

After the founder merges, deploy this client's existing raw Compose resource
from `agents/ghost/docker-compose.enforce.yml`. Build both existing images:
Ghost for Enforce/observer and Radix for the proxies. Both proxies require the exact allowed TLS SNI in addition to the CONNECT host.
Docker Engine must support
Compose `interface_name` (28.1 or later).

This adds `egress-proxy`, `health-observer` and `health-egress-proxy` to that
project. The two proxies publish no ports. Enforce retains only its internal
network. The observer retains a separate internal network and writes only its
health volume. Enforce mounts that volume at `/health` read-only. Each proxy
has its own outbound network and binds only its private NIC. No Tank network,
Docker socket or cross-client network is attached. Changes under
`agents/ghost` can also select the existing Ghost deploy-on-merge job; check
that job separately from the per-client raw Compose deployment.

Run `bash ops/seal-check.sh` on the deployment host. Require a clean seal for
this Enforce project, including both proxies and the observer; investigate any
other reported leaks. Do not claim deployment isolation from unit tests alone.

In Coolify's browser terminal for this client's Enforce container, run:

```bash
python -c 'from ghost.site_health import read_health; print(read_health("tervory.com"))'
```

Require `True`. With a blank secret or blank/unsupported SITE_NAME, the observer
logs one fixed line and sleeps without requests until the project is configured
and redeployed. A configured observer fetches only this project's SITE_NAME.
The observer GETs only `https://tervory.com/`, without a request
body, cookies or redirects. Its only persisted result fields are
`site, url, ok, status, ms, checked_at`, with an HMAC signature. Missing, unsigned,
tampered, failed or more-than-30-second-old results are false. After an apply, Enforce waits up to 60 seconds for an authenticated result
whose probe started strictly after the rule's confirmed apply time. A prior
success cannot approve the new rule. A fresh failed result, or no qualifying
result within that deadline, automatically undoes the owned rule. Proxy errors
retain that exact Undo for retry; approval and Undo never switch its control to
the fixture. Health waiting is recorded separately in the receipt's health stage. API connectivity
is never substituted for site health.

Enforce chooses Cloudflare only with all four gates: configured token,
allowlisted zone (`tervory.com`, fixed in code), responding API proxy, and
configured health observer. Otherwise it uses the fixture. Never proceed with
M24 if the receipt names the fixture.

## M24 in the founder's browser

Keep the Cloudflare dashboard, Coolify browser terminal, and the owner's inbox
open. On Free, the one authorized temporary test is `block_ip` on
`tervory.com` for `192.0.2.1`, the RFC 5737 TEST-NET-1 documentation address.
It never represents real traffic. Follow it immediately with Undo.

From the existing per-client Enforce browser terminal, run this through the
existing validated ThreatPayload queue door and existing client mode/cap:

```bash
python - <<'PY'
import os
from ghost.threat_payload import accept_threat_payload
from ghost.threat_queue import ThreatPayloadQueue, queue_root_from_env
payload = accept_threat_payload({
    "schema_version": "ghost.threat.v1",
    "action": "propose_shield",
    "site": "tervory.com",
    "kind": "block_ip",
    "address": "192.0.2.1",
    "reason": "Founder-authorized M24 documentation-address verification",
    "tenant_id": os.environ["TENANT_ID"],
})
print(ThreatPayloadQueue(queue_root_from_env()).put(payload))
PY
```

If payload validation or A2's never-block gate refuses this address, stop and
report the refusal. Do not change validation or substitute a real address.

**Pro-plan variant only:** the authorized temporary `rate_limit` test uses one
path the founder has confirmed is unused on `tervory.com`. Never target `/`,
login, checkout or a working application route. In the same queue command above,
replace `"kind": "block_ip"` and `"address": "192.0.2.1"` with
`"kind": "rate_limit"` and `"path": "/THE-CONFIRMED-UNUSED-PATH"`, and use
`"reason": "Founder-authorized M24 rate-limit verification"`. Use the confirmed
path in place of the placeholder. This variant requires the Pro-plan quota check
in step 1 and the same approval, receipt, email, signed Undo and health checks.
Never run it on Free or remove the host match to make it fit the plan.

If the existing client mode requires approval, use the existing approval door
for this receipt. Do not change modes to bypass it. Read this client's newest
queue receipt from `/queue/receipts` in the same browser terminal. Verify the
kind, documentation address (or Pro variant path) and site, `control=cloudflare`,
`applied=True`, `health_ok=True`, and the owned rule ID. Verify the matching rule appears in Cloudflare's dashboard.
The receipt's decision-to-shield must be at most 10 seconds and
 event-to-shield at most 15 seconds. Save the actual receipt; wall-clock dashboard
refresh timing is additional evidence, not a replacement for the receipt.

Open the actual owner email in the founder's inbox and use its existing signed
Undo link. Press the existing Undo button once. Verify the Undo receipt and
refresh Cloudflare: that rule ID must be gone and unrelated rules must remain.
Health must remain `True`. If Undo fails, remove only that test rule manually in
Cloudflare and retain the failure evidence; do not claim M24 passed.

Attach screenshots of the founder's actual browser: the matching Cloudflare
rule, the live receipt with timing/health/control, the owner email, and the rule
absent after Undo. Keep token values and signed-link query strings out of
screenshots. No mock, fixture email or generated screenshot counts as proof.
If any setting, delivery path or existing approval/Undo door is missing, stop
and report its name. Do not add page copy or controls without approved Figma.

## Kill switch

Undo the temporary rule first. Clear `CLOUDFLARE_API_TOKEN_ENFORCE` in this
Enforce project's Coolify settings and redeploy. On that next deploy Enforce
returns to the fixture. Clearing the setting does not delete existing
Cloudflare rules; durable real-rule records are retained and the fixture cannot
claim to undo them. To undo a remaining owned rule through Enforce, restore the
founder-managed setting and the approved proxy/health configuration, or remove
that exact rule manually in Cloudflare.

The job is complete only after the founder has seen the dashboard apply, healthy
result, receipt, inbox delivery and Undo succeed in his own browser.
