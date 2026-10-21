# Workers

Tervory's own build workers take a brief off GitHub and open a draft pull request. Each task runs in a fresh container that is thrown away at the end. Model calls go through Tank. The worker never merges and never pushes to `main`.

This app runs on the Boston server first, as its own Coolify app. It does not run on the ZA server. When the third server exists, move the app by changing its Coolify destination and the settings below. No code change.

## What starts a task

The service polls GitHub. An open issue becomes a task when both are true:

- It has the label `worker`.
- The body names exactly one brief under `docs/cursor/`, for example `docs/cursor/EXAMPLE.md`.

Anything else with that label gets one comment and is left alone. Pull requests are ignored. One task runs at a time on Boston (`WORKER_MAX_TASKS=1`).

## The sealed computer

Each task is a new rootless podman container (`podman run --rm`). It is not privileged and it does not join the host network. The task image is built with `podman build --isolation=chroot`, and the task runs with `--cgroups=disabled`, because the tervory-workers container is not privileged and cannot write cgroups. So the resource limits now come from the outer container: the compose limits on the tervory-workers service (`mem_limit` from `WORKER_SERVICE_MEMORY`, default 6g; `cpus` from `WORKER_SERVICE_CPUS`, default 3; `pids_limit: 1024`). The task still runs with `--cap-drop ALL` (only `NET_ADMIN` added), `no-new-privileges`, and `--read-only` with tmpfs mounts. The task timeout is still 90 minutes. If podman has the gVisor runtime (`runsc`), the container uses it. Otherwise it uses the ordinary runtime.

Inside the image: a clone of `Tervory-AI/tervory-tank` (cloned at run time, not baked in), Python, Node 22, Chromium installed with Playwright, and Aider. The container installs a firewall before the clone. If the firewall does not install, the task stops.

The firewall allows only:

- GitHub (`github.com`, `api.github.com`, and the GitHub download hosts)
- PyPI (`pypi.org`, `files.pythonhosted.org`, `pypi.python.org`)
- npm (`registry.npmjs.org`)
- Tank, on the host and port in `TANK_URL`
- The local proxy on `127.0.0.1`, which is how Aider reaches Tank

Everything else is dropped, including model providers.

## Models go through Tank

Aider is pointed at a proxy on `127.0.0.1`. That proxy calls `POST {TANK_URL}/v1/route` and nothing else. Tank applies the ladder, the cache, and the ledger. The call uses `TANK_KEY_WORKERS`, so the ledger agent is `workers`. The tenant is `WORKER_TENANT_ID` (the platform tenant unless you set another).

`WORKER_TASK_TYPE` must already be a Tank policy name. The default is `reason.brief`, which is the existing policy with the highest reply cap (4096). This brief does not add a policy row.

On Boston, `WORKER_LINK=internal` and `TANK_URL=http://tank:8000`. The workers app joins Tank's Docker network (`TANK_DOCKER_NETWORK`). The task container is given that address and reaches Tank through the workers app, still on the private network.

On the third server, `WORKER_LINK=wireguard` and `TANK_URL` is a private address, for example `http://10.90.0.1:8000`. A public Tank address is refused. `TANK_DOCKER_NETWORK` is a Docker network on that server whose route to Tank goes over WireGuard. The WireGuard private key stays on the server. It is not a variable in this repo.

## GitHub access

The container receives a GitHub App installation token, written into a file for that task and removed when the container exits. The App's private key stays on the workers service. It is not copied into the task.

The token is the short-lived installation token GitHub issues (about one hour). The App JWT used to mint it lasts under ten minutes. A personal access token is refused.

The App is installed with only:

- Contents: read and write
- Pull requests: read and write
- Issues: read and write

It does not get administration. The worker has no merge call. `main` and `master` are refused before `git push` runs. The branch is `worker/<brief>-<issue>`. Branch protection on `main` is still required: that is what stops a push to `main` if something else uses the token.

The pull request is opened as a draft. When the checks on that commit are green, the worker marks it ready and puts `ready for review` at the top of the description. A red check leaves the draft. The worker does not merge and does not deploy.

## What you can see

Every model call is a row in Tank's ledger (agent `workers`, with the cost Tank returns). The ledger has no column for a pull-request link or a duration, and this brief does not change the ledger or the Tank page. The workers service serves a read-only Workers panel on the internal port only (`GET /workers` and `GET /workers.json`) with the issue, brief, status, pull-request link, minutes, and model cost. That port is not published. The same facts are commented on the issue.

A follow-up that is allowed to edit the Tank page can show this panel there. This change does not.

## Brief files

The worker reads the section "Files you may change". Paths in backticks are allowed. A path that ends with `/` is a directory. The words "new tests" also allow `tests/`. After Aider runs, any other path fails the task and nothing is pushed.

## Founder, after merge

1. GitHub, organization Tervory-AI, Settings, Developer settings, GitHub Apps, New GitHub App.
2. Name: Tervory Workers. Homepage: `https://app.tervory.com`.
3. Uncheck Active under Webhook. The worker polls. It does not take public webhooks.
4. Repository permissions: Contents read and write, Pull requests read and write, Issues read and write. Leave Administration, Secrets, and Workflows off.
5. Installation: only this account. Create the app. Generate a private key. Do not commit it and do not paste it into chat.
6. Install the app on Tervory-AI, repository `tervory-tank` only. Copy the App ID and the Installation ID from the installation URL.
7. Branch protection on `main`: require a pull request, do not allow the app to bypass, and do not give the app a direct push or the right to merge.
8. Coolify, new app from `docker-compose.workers.yml`, name `tervory-workers`. Boston destination. Not the ZA server.
9. Set `TANK_DOCKER_NETWORK` to the Docker network the Tank service is already on, so `http://tank:8000` resolves.
10. Set `GITHUB_APP_PRIVATE_KEY` to the private key's content (the multiline PEM) as a Coolify setting. Compose passes it as environment; the service keeps it in memory-backed storage. No file on the server is needed. Set `GITHUB_APP_ID` and `GITHUB_APP_INSTALLATION_ID`.
11. Create `TANK_KEY_WORKERS` with `openssl rand -hex 32`. Set the same value on Tank and on this app. Never commit it.
12. Boston settings: `WORKER_LINK=internal`, `WORKER_MAX_TASKS=1`, `WORKER_TASK_CPUS=2`, `WORKER_TASK_MEMORY=4g`, `WORKER_TASK_TIMEOUT_MINUTES=90`, `WORKER_SERVICE_MEMORY=6g`. The service needs more memory than one task because the task runs inside it.
13. The app needs `/dev/fuse` (already in the compose file) so rootless podman can start task containers. The task process is an unprivileged user. The firewall is installed first, then privileges are dropped.
14. Third server, when it exists: change the Coolify destination. Set `WORKER_LINK=wireguard`, `TANK_URL` to Tank's private WireGuard address, `WORKER_MAX_TASKS=3`, `WORKER_TASK_CPUS=4`, `WORKER_TASK_MEMORY=8g`, and raise `WORKER_SERVICE_MEMORY` so three tasks fit. Point `TANK_DOCKER_NETWORK` at a Docker network that routes only across the WireGuard tunnel. Bring WireGuard up on the host. The private key stays there.

WireGuard shape the host keeps, with placeholders only:

```
[Interface]
PrivateKey = <server private key, not in git>
Address = 10.90.0.2/32

[Peer]
PublicKey = <boston public key>
Endpoint = <boston host>:51820
AllowedIPs = 10.90.0.1/32
```

`AllowedIPs` is Tank's tunnel address, not the whole internet.
