# Rule 11 proof — Trigger CRM (PR scaffolding)

Fill results and screenshot paths **after** Tervory deploys Coolify `trigger-crm` and the founder finishes the browser test. Nothing claimed without proof.

## Pin

| Field | Value | Checked |
|---|---|---|
| Upstream | Django-CRM/Django-CRM | |
| Tag | v1.39.0 | |
| Commit | cd7c12a607df1719518fcdaf289864f6ba7d0bcd | |

Command:

```bash
gh api repos/Django-CRM/Django-CRM/git/ref/tags/v1.39.0 --jq .object.sha
# expect: cd7c12a607df1719518fcdaf289864f6ba7d0bcd
```

Result (paste):

```text
(pending Tervory / re-check at merge)
```

## Files in this PR (file + purpose)

| File | What changed |
|---|---|
| `ops/trigger-crm/docker-compose.yml` | Coolify overlay: shared Postgres `trigger_crm` (no compose `db`), redis, gunicorn backend, celery, production frontend; pin in header |
| `ops/trigger-crm/README.md` | Coolify paths, health/admin, env name list |
| `ops/trigger-crm/TERVORY-CONNECTOR.md` | API user + PAT scope names only (no token) |
| `ops/trigger-crm/PROOF.md` | This Rule 11 scaffold |
| `docker-compose.yml` | Attach Boston postgres to corridor `tervory-gw-trigger-crm` (external) |

## Commands / results (deploy — Tervory)

| Step | Command / action | Result |
|---|---|---|
| Network | `docker network create tervory-gw-trigger-crm` | pending |
| DB+role | create database/role `trigger_crm` on Boston Postgres (never tank schema) | pending |
| Coolify | resource `trigger-crm`, base_directory `ops/trigger-crm`, compose `/docker-compose.yml`, FQDN `crm.tervory.com` | pending |
| Envs | Coolify names from README; founder fills values | pending |
| Health | GET `https://crm.tervory.com/healthz/` (or backend `/healthz/`) | pending |
| Kuma | internal check on `/healthz/` | pending |
| r2-backup | add `trigger_crm` DB; once-backup + throwaway restore row counts | pending |
| Memory at rest | backend 1g / frontend 512m / celery-worker 512m / celery-beat 256m (compose caps); live RSS after deploy: | pending |

## Founder browser test (DONE WHEN)

| Step | Pass? | Screenshot path |
|---|---|---|
| Access gate → sign in at `https://crm.tervory.com` | | |
| Create one contact | | |
| Create one estimate | | |
| Open estimate public accept link | | |
| Accept → becomes invoice | | |
| Django admin location noted (`/admin/` on backend) — no password in chat | | |
| Create user `tervory-connector` + PAT scopes per TERVORY-CONNECTOR.md (token never shown) | | |

## Blockers

Waiting on **Tervory** for Coolify resource + network + DB role + Kuma + r2-backup registration. No further compose rewrites unless Tervory reports a blocker.
