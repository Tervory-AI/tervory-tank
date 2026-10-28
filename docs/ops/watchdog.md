# Uptime check

A GitHub Action named **watchdog** checks the live sites every 10 minutes. It also has a manual run. Nothing is installed on the server, and it does not call a paid service.

The schedule starts after this workflow is on `main`. Until then, run it by hand from the branch or from `main` once it is merged.

## What it checks

- `https://app.tervory.com/api/health` must return HTTP 200. The site root returns 404 to a signed-out visitor because sign-in is required, so the check uses the public health probe.
- `https://coolify.tervory.com/api/health` must return HTTP 200.
- `https://rig.tervory.com/health` and `https://tervory.com` are checked once they are live.
- Every Coolify application, through `GET /api/v1/applications`. The token is the repo secret `COOLIFY_TOKEN`. An application must be `running:healthy`. The Boston stack (the one in the runbook) reporting `running:unknown` is still allowed until its health checks are deployed. A failed connection to the Coolify API opens `Down: Coolify`. A later successful call closes that issue, even when one application is still down.
- The certificate on each live domain. A warning is logged at 14 days left. An incident is opened at 7 days left.

## Not live yet

If a name does not resolve, the line says `not live yet` and no issue is opened. The same happens when the name resolves but the server does not yet have a certificate for it (the placeholder certificate). Today that is `tervory.com` (no DNS) and `rig.tervory.com` (DNS points at the server, certificate not issued yet).

## When something is down

The run opens one GitHub issue titled `Down: <thing>` with the label `incident`. If that issue is already open, it does not open another. When a later run finds the thing healthy again, it comments `recovered` and closes the issue.

GitHub emails people who watch the repository. The log shows status codes and names only. The Coolify token and response bodies are never printed.

## Run it

GitHub → **Actions** → **watchdog** → **Run workflow**. Leave the drill field empty.

The drill field takes one check name and fails that check on purpose, so you can see a single issue open and the next good run close it. Leave it empty for a real run.
## Uptime Kuma (Boston)

Uptime Kuma is also deployed on Boston (see `docs/ops/uptime-kuma.md`). **Keep this GitHub watchdog** until Kuma has run clean for one week. Do not delete the workflow or script in the same change that adds Kuma.
