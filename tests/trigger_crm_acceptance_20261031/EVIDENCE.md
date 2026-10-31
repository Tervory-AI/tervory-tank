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
