## Refreshed founder-only evidence — 1 November 2026

This section supersedes all older source heads and client-grant acceptance below.
No production or founder-browser completion is claimed.

Frozen source heads (both include current main
`f545e182d3886c1af8a9b5878e26b70b08866ac3`):

| Branch | Tested head |
|---|---|
| #498 backend | `cbfa329f29783db6ccdf53e423adb25fc1f33f61` |
| #497 Workspace | `be137cb4146dee721125427c11a29810f9249ee0` |
| #499 acceptance harness before this evidence-only commit | `1d2f12b2` |

Changed `combined.cjs:47` to require 404 for a granted client, tenant admin and
member. Changed `test_combined.py:102` to run with grants enabled and disabled,
refuse direct nonfounder Tank reads/writes while the grant is enabled, and retain
unconfirmed-write, region and authenticated-organization refusal assertions.

Exact setup/verification commands in `/workspace/codex-trigger-crm`:

1. `git checkout codex/trigger-crm-acceptance-20261031 && git merge origin/main`: PASS, no conflicts; merge `fe4cce67`.
2. `git worktree add --detach /workspace/codex-trigger-crm/.crm-assembly codex/trigger-crm-backend-20261031`: PASS.
3. `git -C .crm-assembly merge --no-commit --no-ff codex/trigger-crm-workspace-20261031`: PASS, no conflicts. Local detached assembly only, never pushed as a product branch.
4. `ln -s /home/ammosync/.codex/trigger-crm-workspace-20261031/workspace/node_modules .crm-assembly/workspace/node_modules`: PASS, existing dependencies reused, untracked.
5. `CRM_ASSEMBLED_ROOT=/workspace/codex-trigger-crm/.crm-assembly PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q -s -p no:cacheprovider tests/trigger_crm_acceptance_20261031/test_combined.py --tb=short`: initial collection failed because local test environment lacked uvicorn. `/home/ammosync/trigger-crm-venv312/bin/python -m pip install 'uvicorn==0.54.0'` installed the existing Tank pin. Exact test command rerun: **1 passed, zero skips, one existing Pydantic warning, 3.66s**.
6. `node tests/trigger_crm_workspace/contract.cjs` in `.crm-assembly`: PASS, founder-only boundary and existing route contracts.
7. `git diff --check` in primary and assembled trees: PASS.
8. Every finished file committed and `git push origin codex/trigger-crm-acceptance-20261031`: PASS.

Actual observed assertions: founder list envelopes for leads/contacts/estimates,
limit/offset mapping, tenant binding, no credential reflection; clients/admins/
members refused; six synthetic reads across the two grant states; founder write
with forged boolean confirmation refused 409 before mutation; wrong-region read
refused 403; wrong authenticated CRM organization refused 502 before projection.
Only loopback Tank and synthetic httpx CRM transport were used. No model calls,
external CRM requests, live fixtures, production SQL, setting values or deployment.

Backend focused checks: **56 passed**, 19.56s; Ruff passed. Workspace route contract
and TypeScript (`--noEmit --incremental false`) passed. Commands and source-line
manifests are in each branch's own evidence document. Hosted exact-head checks
remain separate and pending at this checkpoint. Founder merge, approved screen
integration, real configured records and founder browser screenshots remain
required; no screenshots are fabricated or substituted with fixtures.

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

## Organization attestation update — 31 October 2026, 12:20 PDT / 19:20 UTC

Backend exact head `cb482eae2dacacedc7594a3c66bd3c7466b0858a`, Workspace unchanged `135e764befd79b33bc56556f2818d4c8bddaab3a`; isolated assembly `e7a807af776490a83b27468ef539cf9501b7483f`. Harness source `986b3d05`.

The old declared-org-only limitation is addressed in this backend revision. Independently reviewed the entire organization-attestation delta: appended middleware runs after pinned BottleCRM `common.middleware.get_company.GetProfileAndOrg`, whose actual upstream source resolves PAT `request.org` / `request._pat`. It rejects a mismatched expected organization before the CRM view, strips preexisting response attestations, and emits the resolved org only for successful authenticated responses. Tank requires that attestation for reads; mutations first require an attested read plus fresh entitlement check, and send expected org on the write, where the same middleware restricts execution. No token-derived organization is guessed by Tank.

Actual independent commands in the assembly:

```sh
PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_trigger_crm.py tests/test_trigger_crm_wsgi.py tests/test_secrets.py
# 44 passed, zero skips, 1 existing Pydantic warning, 26.43s.
```

This includes the real pinned Django WSGI smoke using synthetic settings/auth, plus wrong/missing attestation, pre-write read barrier and persisted Trigger grant/revocation tests. The earlier attempt using a Tank-only Python runtime produced 38 passed / 1 skipped because Django was absent; that is not the final result. The full command above uses the existing isolated CRM test runtime with Django present and has zero skips.

Updated the independent fake CRM to assert the expected org request header and return its authenticated-org attestation. Actual Workspace -> Tank -> fake CRM command on the exact new assembly:

```sh
CRM_ASSEMBLED_ROOT=/home/ammosync/.codex/trigger-crm-combined-20261031 PYTHONPATH=/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031 /tmp/tervory-rls-merge-python/bin/python -m pytest -q -s tests/trigger_crm_acceptance_20261031/test_combined.py
# 1 passed, zero skips, 1 existing Pydantic warning, 2.55s.
/home/ammosync/trigger-crm-venv312/bin/ruff check tests/trigger_crm_acceptance_20261031
# All checks passed.
```

Read-only upstream source command: `gh api 'repos/Django-CRM/Django-CRM/contents/backend/common/middleware/get_company.py?ref=cd7c12a607df1719518fcdaf289864f6ba7d0bcd' --jq .content | base64 -d` (selected implementation lines inspected, no live CRM request). The first attempted `backend/requirements.txt` lookup returned 404; dependency evidence instead uses the existing pinned runtime and backend uv.lock reference, not an invented requirements path.

**Bounded backend source review clear at cb482eae. Full client flow remains uncleared:** Workspace exact head still rejects every non-founder. No latest-head blanket hosted-CI clearance or live deployment/CRM acceptance is claimed.

## Client corridor verified — 31 October 2026, 12:22 PDT / 19:22 UTC

Supersedes the earlier founder-only Workspace mismatch for this exact reviewed head: Workspace PR 497 `a3954f2` (runtime change `378fb6e`), backend PR 498 `cb482eae2dacacedc7594a3c66bd3c7466b0858a`. Assembly `46ac68905f401873cf4f0a26344a3b03eaa56a71`; independent harness `ad0d3630`.

Independently reviewed the Workspace change: it removes only the obsolete founder prefilter. Signed-in user plus active organization remain mandatory, identity still comes from Clerk/session and server tenant alias mapping, and Tank remains authoritative for persisted Trigger grants and authenticated organization binding. No client role, grant or founder privilege is created by the proxy.

The actual loopback integration now runs the same client twice. With a synthetic persisted Trigger grant, the actual Tank `authorized_actor` reads the tenant-scoped `tenant_squad` predicate and the client receives 200 through Workspace. With that grant revoked, the same user/organization request receives 403 and causes zero additional CRM requests. An unrelated no-grant tenant also receives 403. Only the persistence adapter is synthetic; the actual authorization predicate/function executes. The test is not a real Postgres/RLS deployment claim.

A final mismatched authenticated organization response returns 502 before any record projection. Founder reads, exact limit/offset, no user/tenant assertion forwarding, synthetic credential metadata redaction, wrong-region refusal and unconfirmed mutation barriers remain covered.

```sh
CRM_ASSEMBLED_ROOT=/home/ammosync/.codex/trigger-crm-combined-20261031 PYTHONPATH=/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031 /tmp/tervory-rls-merge-python/bin/python -m pytest -q -s tests/trigger_crm_acceptance_20261031/test_combined.py
# 1 passed, zero skips, 1 existing warning, 2.81s.
/home/ammosync/trigger-crm-venv312/bin/ruff check tests/trigger_crm_acceptance_20261031
# All checks passed before commit.
```

Source clearance covers this bounded client corridor, not invented UI or every historical CRM resource. Fresh `gh pr checks 497` / `498` still showed pending latest analyses/service checks at 12:22 PDT; no all-CI-ready statement is made. Parent coordinates subsequent catalog/invoice extensions and their own exact-head proof.
