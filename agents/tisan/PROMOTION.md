# Tisan site promotion

Promotion uses Coolify's HTTP API. It never mounts or calls a Docker socket.
This is an API operation through the existing founder-only Tank corridor; no
Workspace page, button or copy changes are included.

## Before enabling it

Merge and deploy Radix job 8 first. Tisan calls the real
`POST /v1/radix/passive/scans` and `/gate` through Tank with its existing room key,
tenant, `tisan` squad and box-region headers. Missing/denied/unavailable gates
refuse promotion before any production application update. There is no passing
fallback. The founder must authorize the staging host through Radix's domain
proof workflow. Scans run only when explicitly promoting a registered site.

The founder supplies `TISAN_COOLIFY_URL` (HTTPS API origin) and
`TISAN_COOLIFY_TOKEN` through Coolify, by name only. Use a token limited to the
intended applications with read/write/deploy access and **without**
`read:sensitive`. No environment-list or log API is used. The HTTP client disables
proxy inheritance and redirects, and never returns Coolify response bodies,
headers or errors to the caller. Only selected deployment metadata is journalled.

The site's staging and production applications must already exist. Both must be
Git-backed, healthy, pinned to their deployed full 40-character SHA, and have
automatic deployment disabled. They must use the same repository, base directory
and build pack. The registered staging HTTPS origin must belong to the staging
application. This job supports full Git commits; mutable image tags and moving
branch names cannot be promoted. Application creation, credentials, repositories
and customer content are not invented by this job.

Deploy Tisan with repository-root build context and
`agents/tisan/Dockerfile`, as the checked-in Compose file specifies. The image
reuses the existing Playwright 1.64.1 dependency and `ops/live_check.mjs`, including
Chromium. The Dockerfile-specific ignore file limits context to required sources.
No promotion, scan or Coolify request runs at import or startup.

## API contract

Every route requires the existing Workspace key and verified founder identity
(`X-Tervory-Admin`) at Tank. Tank forwards only the room key and authenticated
founder header. Ordinary members cannot use these routes. The room independently
checks its key and founder allowlist. Tenant/site bindings are local to this room.

- `POST /v1/tisan/promotion/sites`: register `{tenant_id, site, staging, production,
  url}`. `staging` and `production` are existing Coolify application UUIDs. The
  binding is immutable; an application cannot be reused by another site/tenant.
- `POST /v1/tisan/promotion/promote`: `{tenant_id, site, operation_id, commit}`.
  `operation_id` is the caller's stable UUID for this action. `commit` is the exact
  staging SHA the founder intends to promote.
- `POST /v1/tisan/promotion/status`: the same operation identity fields. Poll to
  observe completion; a queue acknowledgement is only `pending`.
- `POST /v1/tisan/promotion/rollback`: a **new** operation UUID, same tenant/site,
  and the recorded previous production SHA as `commit`.
- `GET /v1/tisan/promotion/history?tenant_id=...&site=...`: latest 100 records.

The service reads the latest finished, non-preview Coolify staging deployment,
checks the live origin at 1440px and 375px, runs Radix for `commit:<full SHA>`, and
requires an exact tenant/origin/artifact binding with a complete result no older
than one hour and zero high/critical findings. The staging browser is signed out,
sends no credentials and blocks cross-origin requests and all methods except
GET/HEAD. It requires a successful same-origin root response, checks visible error
and fixture text and runtime errors, and retains screenshots on the data volume.
Coolify staging and production records are rechecked after these gates. The
Coolify deployment record is the source-revision attestation; no user boolean,
page text or invented revision header substitutes for it.

Production is pinned with `PATCH /applications/{uuid}` using `git_commit_sha`,
then queued through `POST /deploy` with the application's UUID. `succeeded`
requires Coolify's named deployment to finish at that exact SHA and still be the
latest healthy pinned production deployment. No queue response alone is success.
Promotion to an already-current SHA is refused without a redundant deployment.

Rollback uses the same API and the server's recorded previous SHA. After an
acknowledged terminal failed/cancelled deployment, explicit rollback additionally
requires that exact failed deployment UUID and pin still be current. It forces a
redeployment so Coolify cannot skip recovery merely because the old commit is
still running. A changed or still-running deployment cannot use this recovery.

## Journal and ambiguous outcomes

`/data/promotion.sqlite3` records tenant/site, operation UUID, actor, timestamps,
expected/previous/target commit, scan/deployment identifiers and result. It uses
the existing persistent Tisan data volume, short atomic transactions and a
per-site durable reservation. It is not a production Postgres migration.
No token, raw scanner report, request header or Coolify log is stored.

Reusing an operation UUID with the same identity reads the existing record;
changing actor/action/commit is refused. A preflight timeout or failed gate
records `refused` and releases the site. A lost acknowledgement or uncertainty
after a possible production mutation records `unknown` and keeps the site
reserved. Interrupted `checking`/`pinning`/`submitting` operations also remain
reserved. There is deliberately no automatic resend or unlock for these cases:
an operator must first reconcile the actual Coolify deployment read-only. This
build does not invent an outcome or provide an unsafe force-unlock endpoint.
Known pending operations can be polled; definitively failed operations support
the guarded explicit rollback above. Do not change these applications through
another writer while a promotion/rollback is in progress.

## Official API sources checked 28 October 2026

- https://coolify.io/docs/api/endpoints/applications/update-application-by-uuid
- https://coolify.io/docs/api/endpoints/applications/get-application-by-uuid
- https://coolify.io/docs/api/endpoints/deployments/deploy-by-tag-or-uuid
- https://coolify.io/docs/api/endpoints/deployments/get-deployment-by-uuid
- https://coolify.io/docs/api/endpoints/deployments/list-deployments-by-app-uuid
- https://github.com/coollabsio/coolify/blob/v4.x/app/Http/Controllers/Api/DeployController.php

The list-deployments page's example incorrectly shows application records. The
upstream controller returns the application's `deployments` collection; this is
the envelope used by the client and fake server. Validate compatibility with the
founder's installed Coolify version before enabling live promotion. The API has
no deployment idempotency/CAS parameter; the durable journal prevents this client
from resending an ambiguous request. It cannot arbitrate an unrelated writer.

## Founder acceptance still required

After founder merge and authorized deployment of Radix and Tisan, use a real
founder-owned test site with existing staging/production applications and domain
proof. Register the binding, promote its tested staging SHA, poll to
`succeeded`, and open both sites in the founder's browser. Retain the staging and
production deployment SHAs, operation history and actual browser screenshots.
Then explicitly roll back and confirm the recorded previous SHA is live.
No live site was registered, scanned, promoted or rolled back by this branch;
local synthetic browser screenshots are not founder acceptance.
