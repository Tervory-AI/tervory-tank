# Workers

Tervory's own build workers take a brief off GitHub and open a draft pull request. Each task runs in a fresh container that is thrown away at the end. Model calls go through Tank. The worker never merges and never pushes to `main`.

The service runs on the Boston host itself, not in Docker. It runs as the dedicated user `tervory-workers` under a systemd user unit, and task containers are rootless podman under that user. It does not run on the ZA server. The old Coolify app `tervory-workers` (from `docker-compose.workers.yml`, now removed) is stopped and will be retired. Do not redeploy it. See [Host install](#host-install-boston).

## What starts a task

The service polls GitHub. An open issue becomes a task when both are true:

- It has the label `worker`.
- The body names exactly one brief under `docs/cursor/`, for example `docs/cursor/EXAMPLE.md`.

Anything else with that label gets one comment and is left alone. Pull requests are ignored. One task runs at a time on Boston (`WORKER_MAX_TASKS=1`).

## The sealed computer

Each task is a new rootless podman container (`podman run --rm`), started by the `tervory-workers` user on the host. It is not privileged, it does not join the host network, and it never sees `docker.sock`. The run keeps:

- `--cap-drop ALL`, with `NET_ADMIN` added only so the in-task firewall can install
- `--security-opt no-new-privileges`
- `--read-only`, with tmpfs for `/tmp`, `/work` and `/home/worker`
- `--network slirp4netns:allow_host_loopback=true` (see the network section below)
- `--runtime` set to the runtime podman itself reports in `podman info` (crun on Ubuntu), or gVisor (`runsc`) if podman lists it. runc is never assumed. If `podman info` fails, the task stops.

Limits are per task, from settings: `--cpus` (`WORKER_TASK_CPUS`, default 2), `--memory` (`WORKER_TASK_MEMORY`, default 4g), `--pids-limit 512`, and the 90-minute timeout. They work because the host uses cgroups v2 and the systemd user session delegates the `cpu`, `memory` and `pids` controllers to `tervory-workers`. `install.sh` checks for that delegation and stops if it is missing. The earlier `--isolation=chroot` and `--cgroups=disabled` workarounds were needed only inside the unprivileged Docker container, and they are gone.

The task image is built with plain `podman build` from `/srv/tervory-workers/app`. The worker user in the image is UID 1001, because `node:22-bookworm-slim` already uses 1000 for `node`. If the build or run fails, the service logs the last 20 lines of podman's output, redacted.

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

On Boston, `WORKER_LINK=loopback` and `TANK_URL=http://127.0.0.1:8100`. The Tank service in `docker-compose.yml` publishes `127.0.0.1:8100:8000`, which is host loopback only and never a public address. The service reaches Tank there. A task container reaches the same port as `http://10.0.2.2:8100`, because slirp4netns with `allow_host_loopback=true` maps the host's loopback to `10.0.2.2`. The service passes the task that address. With `WORKER_LINK=loopback`, any `TANK_URL` other than `http://127.0.0.1:<port>` (or `10.0.2.2` inside a task) is refused.

On the third server, `WORKER_LINK=wireguard` and `TANK_URL` is a private address, for example `http://10.90.0.1:8000`. A public Tank address is refused. That server uses the same host install. The WireGuard private key stays on the server. It is not a variable in this repo.

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

Every model call is a row in Tank's ledger (agent `workers`, with the cost Tank returns). The ledger has no column for a pull-request link or a duration, and this brief does not change the ledger or the Tank page. The workers service serves a read-only Workers panel on `127.0.0.1:$WORKER_PORT` only (default 8110 on the host, `GET /workers` and `GET /workers.json`) with the issue, brief, status, pull-request link, minutes, and model cost. Nothing else can reach that port. Tank's own Workers panel (`WORKERS_URL`, default `http://workers:8000`) cannot reach the host loopback from inside Docker, so until a follow-up gives it a route, it shows "not available". The same facts are commented on the issue.

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
8. On Boston, follow [Host install](#host-install-boston). Put the App ID, the Installation ID and `TANK_KEY_WORKERS` in `/etc/tervory-workers/worker.env`, and the private key in `/etc/tervory-workers/github-app.pem`.
9. Create `TANK_KEY_WORKERS` with `openssl rand -hex 32`. Set the same value on Tank and in `worker.env`. Never commit it.
10. Third server, when it exists: run the same install there. Set `WORKER_LINK=wireguard`, `TANK_URL` to Tank's private WireGuard address, `WORKER_MAX_TASKS=3`, `WORKER_TASK_CPUS=4` and `WORKER_TASK_MEMORY=8g`. Bring WireGuard up on the host. The private key stays there.

## Host install (Boston)

Everything is in `workers/host/`:

- `install.sh` installs and updates. It is idempotent, runs as root, and holds no secrets.
- `tervory-workers.service` is the systemd user unit.
- `worker.env.example` is the env template, with names only.

From a checkout of this repo on the host:

```
sudo workers/host/install.sh               # install or update, then (re)start the unit
sudo workers/host/install.sh --no-start    # install or update, leave the unit stopped
sudo workers/host/install.sh --subid-start 231072
```

What it does:

1. Installs `podman`, `crun`, `uidmap`, `slirp4netns`, `passt`, `dbus-user-session` and `python3-venv` from Ubuntu's own repos. It runs `apt-get install -s` first and aborts before any change if apt would install, remove or upgrade anything named `docker*`, `containerd*`, `runc`, `moby*` or `podman-docker`, or would remove any package. `needrestart` is told to list only, so no service (Docker included) is restarted. Already-installed packages are skipped.
2. Creates the user `tervory-workers`: `nologin` shell, home `0700`, its own group only. It is not in `sudo` or `docker`, and it has no extra groups. The script stops if it finds any of those.
3. Gives the user the next free 65536-wide subuid/subgid range after the existing ones (on Boston, after `ammosync 100000:65536` and `tngo 165536:65536`, that is `231072:65536`), or the range passed with `--subid-start`. A range that overlaps another user is refused.
4. Enables lingering (`loginctl enable-linger`) so the user's systemd manager runs without a login. This is the same pattern as `tngo-preview.service`.
5. Checks AppArmor. Ubuntu sets `kernel.apparmor_restrict_unprivileged_userns=1`, so rootless podman depends on the `podman` profile in `/etc/apparmor.d`. The script makes sure it is loaded.
6. Creates `/etc/tervory-workers` (owner root, group `tervory-workers`, mode `0750`). It copies the template to `worker.env` only if `worker.env` is missing, and sets `worker.env` and `github-app.pem` to owner root, group `tervory-workers`, mode `0640`. It prints the names (never the values) that are still empty.
7. Copies `workers/` to `/srv/tervory-workers/app` and builds the venv in `/srv/tervory-workers/venv`. Both are root-owned, so the service can read the code but not change it.
8. Installs the unit to `~tervory-workers/.config/systemd/user/`. Then, as the user, it checks `podman info`: rootless, cgroups v2 with `cpu`, `memory` and `pids` delegated, an OCI runtime, slirp4netns, and podman 5.x (podman 6 removed slirp4netns). It fails loudly if any is missing.
9. Enables and restarts the unit, unless `--no-start` is given.

To update, pull the checkout and run `install.sh` again. It replaces the code, reinstalls the venv only when `workers/requirements.txt` changed, and restarts the unit.

### Secrets and the env file

`/etc/tervory-workers/worker.env` and `/etc/tervory-workers/github-app.pem` are owned by root, group `tervory-workers`, mode `0640`. That satisfies "root-owned, only that user can read": root owns and writes them, and the only member of the group `tervory-workers` is the user `tervory-workers`. A root-only `0600` file would not work, because a systemd user unit's `EnvironmentFile=` is read by the user's own manager, not by root. The files live outside any git checkout.

The names are `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `TANK_KEY_WORKERS`, `GITHUB_APP_PRIVATE_KEY_FILE=/etc/tervory-workers/github-app.pem`, `TANK_URL=http://127.0.0.1:8100` and `WORKER_LINK=loopback`, plus the non-secret `WORKER_*` settings in the template. Never paste a value into chat, logs or GitHub.

Per-task token files are staged under `$XDG_RUNTIME_DIR/tervory-workers`, which is `/run/user/<uid>`. That is memory-backed and `0700` (`RuntimeDirectory=` in the unit). The App key is never mounted into a task.

### Security model

- **Host user:** an unprivileged user with no sudo and no docker group, so it cannot reach the Docker daemon or root.
- **Unit:** `NoNewPrivileges=yes` and `UMask=0077`. It restarts on failure and is wanted by `default.target`.
- **Tasks:** rootless podman, so container root is the unprivileged host user, and the task process drops to UID 1001 inside after the firewall is installed. It runs with `--cap-drop ALL`, `NET_ADMIN` only, `no-new-privileges` and `--read-only`.
- **Network:** slirp4netns gives each task its own user-mode network. `allow_host_loopback=true` makes the host's loopback reachable as `10.0.2.2`. The in-task firewall (nftables, drop by default) allows only DNS to the slirp resolver, GitHub, PyPI and npm on 443, and Tank at `10.0.2.2:8100`. Every other host-loopback port (Coolify, other previews) is dropped. The firewall is installed by container root before privileges drop, and the task user cannot change it.
- **Tank:** reachable only on `127.0.0.1:8100` on the host. It is never published on a public address.

### Troubleshooting

All of these run as root:

- Unit status: `runuser -u tervory-workers -- env XDG_RUNTIME_DIR=/run/user/$(id -u tervory-workers) systemctl --user status tervory-workers`
- Logs: the same with `journalctl --user -u tervory-workers -n 100`. The logs are redacted, so look for `task image build failed`, `podman info failed` or `poll failed`.
- `podman info failed` or `cannot set up namespace`: check `/etc/subuid` and `/etc/subgid`, then the AppArmor `podman` profile (`aa-status | grep podman`), then run `install.sh` again.
- `cgroup controllers not delegated`: check `/sys/fs/cgroup/user.slice/user-<uid>.slice/user@<uid>.service/cgroup.controllers`. It must list `cpu memory pids`.
- Tank unreachable: `curl -s http://127.0.0.1:8100/health` on the host. If nothing answers, Tank has not been redeployed with the `127.0.0.1:8100:8000` port yet.

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
