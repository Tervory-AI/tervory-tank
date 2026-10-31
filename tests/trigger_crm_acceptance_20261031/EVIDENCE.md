# Trigger CRM completion evidence

Recorded 31 October 2026, 11:20 PDT / 18:20 UTC. Audit base: `35cae5ffd8cd6f90dc21e34f201707a74c093f01`.

This is an independent requirements and integration-test lane, not implementation or founder acceptance. Founder acceptance stays last. No secret values, live CRM records, production SQL, model calls, emails, or mutations were used.

## Requirement matrix

| Requirement | Source | Baseline result | Completion proof required |
| --- | --- | --- | --- |
| Canonical CRM entry | `ops/trigger-crm/README.md:8` | Exists: https://crm.tervory.com | Existing public Access gate, not inferred Workspace entry |
| Health | `ops/trigger-crm/README.md:9` | Anonymous `/healthz/` returned HTTP 302 to Cloudflare Access | Internal approved health evidence; redirect is not backend health proof |
| Eight independent sections | Historical PR 436 `docs/figma/crm/SPEC.md:11` | Design handoff only, not implemented in baseline Workspace | Leads, Accounts, Contacts, Opportunities, Cases, Tasks, Invoices and Estimates contract coverage |
| Separate invoice/estimate routes | `docs/figma/crm/INVOICES-ESTIMATES.md:9` | Pinned schema exists | Exact `/api/invoices/` and `/api/invoices/estimates/` response envelopes |
| Identity and tenant isolation | `AGENTS.md:23` | No BottleCRM connector on baseline | Tenant mapping from authenticated actor, never browser-selected CRM org; cross-user/tenant denial before upstream |
| Founder-only CRM | `docs/figma/crm/INVOICES-ESTIMATES.md:92` | Controlling scope; no client authorization inferred | Client role denied; no founder service credential exposed |
| Dangerous operations confirmed | `docs/figma/crm/INVOICES-ESTIMATES.md:91` | BottleCRM itself does not provide Tervory confirmation | Zero upstream mutation before actor-bound confirmation; no automatic send/payment/order |
| Public links disabled | `docs/figma/crm/INVOICES-ESTIMATES.md:92` | Explicit restriction | Public fields hidden, never enable links or proxy public endpoints |
| Currency and records | `docs/figma/crm/INVOICES-ESTIMATES.md:93` | Own currency; no conversion | Preserve actual record currency, no sample live data or invented cost |
| Scoped upstream credential | `ops/trigger-crm/TERVORY-CONNECTOR.md:1` | Founder creates token; values never inspected | Existing safe setting presence only; no token minting by agents |
| Screenshots and browser acceptance | `ops/trigger-crm/PROOF.md:1` | Historical proof is an unfilled scaffold, not health/acceptance evidence | Exact-head offline screenshots separately labelled; founder real-browser proof last |

PR 436 remains a founder-only design handoff. Its historical screen/schema audit does not establish application implementation or approve the rejected client dashboard/sidebars. Design work is owned separately; this lane does not alter Figma.

## Exact initial commands and results

- `git clone --quiet https://github.com/Tervory-AI/tervory-tank.git /home/ammosync/.codex/trigger-crm-acceptance-20261031`: exit 0.
- `git checkout -b codex/trigger-crm-acceptance-20261031`: exit 0.
- `ls AGENTS.md ops/trigger-crm/{README.md,PROOF.md,TERVORY-CONNECTOR.md,openapi-cd7c12a.yml}`: all named files exist.
- `cat AGENTS.md ops/trigger-crm/README.md ops/trigger-crm/PROOF.md ops/trigger-crm/TERVORY-CONNECTOR.md`: sources read.
- `gh pr view 436 --repo Tervory-AI/tervory-tank --json title,body,state,headRefOid`: OPEN, exact historical head `70c0d11a16faeec3d73fc93e928abb5e722b7d38`, design documentation only.
- `git fetch --quiet origin codex/crm-design` and `git show FETCH_HEAD:docs/figma/crm/SPEC.md`: read-only historical design comparison.
- Anonymous `curl` GET of the canonical `/healthz/`: HTTP 302 Access login; response body discarded. No authenticated request, redirect-following, or health-success claim. Redirect query metadata is not retained as evidence.
- PyYAML parse of the pinned OpenAPI: 306 paths, 481 HTTP operations; all eight named section GET routes exist. This is schema inventory, not connector runtime proof.

## Integration proof

Pending frozen backend/Workspace APIs. Tests must exercise actual new adapters against a mock CRM with exact pinned envelopes, not duplicate implementation logic. No full feature completion or merge readiness is claimed by this document.

## Independent runtime results — 31 October 2026, 11:53 PDT / 18:53 UTC

Backend tested first: PR 498 `94782b9d8bf28e5cf6d355f10abc30612fb0c308`.
Workspace tested: PR 497 `135e764befd79b33bc56556f2818d4c8bddaab3a`.
First isolated assembly: `9f7472fa05fd910202eb9dc6f247af0088b927f9`.
Harness runtime: `b92f069b` on this branch.

- Actual Workspace GET route and `workspace/lib/tank.ts` adapter call actual loopback HTTP Tank, using its existing service-key/user/tenant/home identity checks. Only Clerk session input and BottleCRM transport are synthetic. No service identity override is installed.
- Three actual pinned response envelopes traverse both implementations: leads open/closed groups, contact_obj_list, estimate results. Page 2 reaches BottleCRM as offset 10 / limit 10. No caller tenant/user assertion is forwarded to CRM.
- Unconfigured active tenant yields 503; client/anonymous Workspace users yield 404 before Tank; unsupported paths/query fail closed; Workspace exports no POST.
- Only allowed record fields reach the response; synthetic token/password/org metadata is omitted. This proves the tested metadata projection, not universal secret detection inside arbitrary user-controlled free text.
- A real Tank write request with a forged `x-confirmed: true` header returns 409 and causes zero upstream mutations. A wrong-region request returns 403 and causes zero additional CRM calls. No real or fake CRM mutation is performed by this harness.
- HTTP server listens only on 127.0.0.1, uses an OS-assigned port, and is shut down and joined in `finally`.

Exact successful commands:

```sh
CRM_ASSEMBLED_ROOT=/home/ammosync/.codex/trigger-crm-combined-20261031 PYTHONPATH=/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031 /tmp/tervory-rls-merge-python/bin/python -m pytest -q -s tests/trigger_crm_acceptance_20261031/test_combined.py
# 1 passed, zero skips, 1 existing Pydantic warning, 2.13s.
/home/ammosync/trigger-crm-venv312/bin/ruff check tests/trigger_crm_acceptance_20261031
# All checks passed.
git diff --check
# Passed.
```

In the first assembled checkout:

```sh
PYTHONPATH=/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031:tank /tmp/tervory-rls-merge-python/bin/python -m pytest -q tests/test_trigger_crm.py
# Independently 29 passed, 1 existing warning, 1.35s.
node tests/trigger_crm_workspace/contract.cjs
# Passed: founder isolation, aliases, path/query allowlists, no mutation export,
# same-box forwarding, empty errors and response envelope checks.
```

Environment history: initial collection failed because the reused Python environment lacked jsonschema. Initial pip install hit the default temporary-filesystem quota. Retried the installation with an owned HOME-local TMPDIR and no cache; installed the same `jsonschema==4.26.0` repository pin into this lane's isolated dependency directory. A trial using the backend owner's Python runtime failed collection because that runtime lacks uvicorn; no false test success was recorded. Harness lint initially reported import order, an unused noqa and missing explicit subprocess check; corrected before the final passing command. No other checkout, dependency tree or source was deleted.

This test module requires explicit `CRM_ASSEMBLED_ROOT`; default CI without the cross-PR assembly skips this integration module deliberately. The actual commands above run with the exact assembly and have **zero skips**. Default CI success cannot replace this explicit integration proof.

### Updated backend head: explicit clearance limit

Backend advanced to `c8628bf37c27090ff2587b9d96913d90636f8251` during verification. This changes schema property retention and authorizes persisted Trigger-granted clients instead of founder-only backend access. Assembly `abce3268fa972f861f39c2460d7104267df37d46` merges that backend with unchanged Workspace `135e764b`.

The same loopback test was repeated on that exact updated assembly: **1 passed, zero skips, 1 existing warning, 2.17s**. Its coverage remains founder reads plus denied client Workspace paths; it does not establish client access completion. Workspace still returns 404 for every non-founder, so client integration is not complete across both layers. Coordinator notified. The full eight-section historical design is also not delivered by this three-resource connector. Configured `organization_id` is a founder-supplied declaration, not an independent upstream membership authentication claim; no stronger guarantee is inferred.

Hosted checks were read with `gh pr checks 498` / `gh pr checks 497`; pending latest CodeQL analyses were present. No blanket CI clearance, production health, approved UI, secret setup, complete CRM, or founder acceptance is claimed.
