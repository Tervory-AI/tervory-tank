# Self-hosted GitHub Actions runner

This cuts GitHub Actions minutes with path selection and an optional self-hosted runner.

1. **Docs-only changes skip CI.** `ci.yml` and `tisan-site.yml` have
   `paths-ignore: ["docs/**", "**/*.md"]` on both `push` and `pull_request`. A change
   that touches only files under `docs/` or Markdown files anywhere starts no run. If
   other files change, the selector below chooses the checks.
2. **`ci.yml` can run on our own machine.** The `tank` and `workspace` jobs run on a
   self-hosted runner with the labels `self-hosted, linux` when you switch it on. When
   it's off, or the runner isn't online, they run on GitHub's `ubuntu-latest` exactly
   as before. `tisan-site.yml` stays on GitHub's machines, because its Playwright step
   needs `sudo` and the runner user must not have it.

## How the fallback works

GitHub can't fall back to its own machines when a self-hosted runner is offline:
a job waiting for a missing runner just queues (for up to 24 hours). So `ci.yml` has a
small first job, **pick runner**, that decides and hands the answer to the other jobs.

| Situation | pick runner | tank and workspace run on |
| --- | --- | --- |
| `SELF_HOSTED_RUNNER_ONLINE` not set to `true` | skipped, costs nothing | `ubuntu-latest` |
| Pull request from a fork | skipped | `ubuntu-latest`, always |
| Switch on, no `RUNNER_STATUS_TOKEN` secret | runs | self-hosted (it trusts the switch) |
| Switch on, token set, a `self-hosted` + `linux` runner is online | runs | self-hosted |
| Switch on, token set, no runner online, or the check fails | runs | `ubuntu-latest` |

When pick runner does run, it's one shell step on `ubuntu-latest` with a 2-minute
limit. There's no checkout and no setup.

**The switch.** `SELF_HOSTED_RUNNER_ONLINE` is a repository *variable*, not a secret.
It holds no key; it's just on or off.

**The optional live check.** Listing a repository's runners needs a token with
"Administration: read" on the repository. The built-in `GITHUB_TOKEN` can't do it.
If you add the `RUNNER_STATUS_TOKEN` secret, pick runner asks GitHub whether a runner
is actually online. Without it, pick runner trusts the switch, so **turn the switch
off when you take the runner down**, or jobs will queue until it comes back.
Leaving the token out is fine. It's a convenience, not a requirement.

The token must be a fine-grained personal access token that:

- covers **only** the `Tervory-AI/tervory-tank` repository
- has **only** "Administration: Read-only" (nothing else, not even Contents)
- expires within 90 days

It isn't a Coolify key, a Tank key or any production secret, and none of those may
ever be used here. It lives only in this repository's Actions secrets, because that's
the only place a workflow can read it. Don't add it to Coolify or Tank. If you would
rather have no extra token at all, skip it and use the switch alone.

## Fork guard

Code from a fork must never run on our machine. Two checks enforce this, and both use
the same rule:

```
github.event.pull_request.head.repo.full_name == github.repository
```

- pick runner is skipped unless the change is a push to `main` or a pull request
  whose branch is in this repository. Its script checks the same thing again.
- The `runs-on` line of `tank` and `workspace` repeats the check, so a fork pull
  request lands on `ubuntu-latest` even if pick runner is ever changed.

No workflow here uses `pull_request_target`. Keep it that way, because that event
runs fork code with this repository's secrets. The tests in
`tests/test_ci_minutes_workflows.py` check all of the above.

## Security rules for the runner machine

Whoever can open a pull request on this repository can run code on the runner.
Treat the machine as untrusted and disposable.

- **An isolated VM, not Boston.** Use a separate small VM (a cloud VM or a VM on your
  own computer). Never use the Boston production host, the Coolify server, or any
  machine that runs Tank, a database or an agent.
- **An unprivileged user.** The runner runs as its own user (`gha` below) with no
  `sudo` and no password.
- **No Docker socket access.** Never mount or share the Docker socket of a production
  host, and don't put `gha` in a root `docker` group. The `tank` job needs Docker for
  its throwaway Postgres container, so install **rootless Docker** for the `gha` user.
  That's Docker running as `gha` itself, with no root daemon.
- **No production secrets.** No Coolify tokens, no Tank keys (`TANK_KEY_*`), no
  `.env` from production, no SSH keys to other servers, no GitHub App private key and
  no cloud credentials. CI needs none of them: its Postgres and Clerk values are test
  dummies.
- **Ephemeral is preferred.** `--ephemeral` makes the runner take one job and then
  unregister, so nothing is left behind from one job to the next. See step 5.
- **Labels.** The runner gets the labels `self-hosted` and `linux`, which match `ci.yml`.
- **Network.** Allow no inbound connections except SSH from your own IP. It needs
  outbound HTTPS to GitHub, PyPI, npm and Docker Hub.

## Founder steps

1. **Create the VM.** Ubuntu 24.04 LTS, x64, 2 vCPU, 4 GB RAM and 40 GB disk is
   plenty. Put nothing else on it. Firewall: inbound SSH from your IP only.

2. **Make the runner user.** Log in with your admin account:

   ```bash
   sudo adduser --disabled-password --gecos "" gha
   sudo apt-get update && sudo apt-get install -y curl jq git uidmap dbus-user-session
   ```

   Don't add `gha` to the `sudo` or `docker` groups.

3. **Install rootless Docker for `gha`.** Follow Docker's "Rootless mode" guide
   (docs.docker.com/engine/security/rootless). In short: install Docker Engine, run
   `sudo systemctl disable --now docker.service docker.socket` so there's no root
   daemon, then as `gha` run `dockerd-rootless-setuptool.sh install`. Also run
   `sudo loginctl enable-linger gha` so it keeps running after you log out. The
   `tank` job maps Postgres to port 5432, so keep that port free on the VM.

4. **Download the runner.** On GitHub go to tervory-tank, then **Settings**, then
   **Actions**, then **Runners**, then **New self-hosted runner**, and pick **Linux**
   and **x64**. As `gha` (`sudo -iu gha`), run the download commands GitHub shows into
   `~/actions-runner`.

5. **Register it.** Still as `gha`, in `~/actions-runner`. The registration token is
   the one on that GitHub page. It works once and expires in an hour. Don't save it
   anywhere.

   Preferred, ephemeral (one job, then it unregisters):

   ```bash
   ./config.sh --url https://github.com/Tervory-AI/tervory-tank \
     --token <token from the page> --name tervory-ci-1 \
     --labels self-hosted,linux --ephemeral --unattended
   ./run.sh
   ```

   An ephemeral runner needs a fresh registration for each job. Getting one
   automatically needs an admin token, and **that token must never be stored on the
   runner VM.** Until we build a small controller somewhere else, the practical setup
   is a persistent runner: the same command without `--ephemeral`. Install it as a
   service with your admin account (`cd /home/gha/actions-runner && sudo ./svc.sh
   install gha && sudo ./svc.sh start`). Then rebuild the VM from a clean snapshot
   every week, and straight away if anything looks wrong.

6. **Lock down GitHub's settings.**
   - Settings, then Actions, then General, then "Fork pull request workflows": leave
     running workflows from forks **off**.
   - If the runner is in an organisation runner group, limit that group to the
     `tervory-tank` repository only.

7. **Switch it on.** Settings, then **Secrets and variables**, then **Actions**, then
   the **Variables** tab, then **New repository variable**:
   `SELF_HOSTED_RUNNER_ONLINE` = `true`. To switch off, set it to `false` or delete
   it. Everything goes back to GitHub's machines straight away.

8. **(Optional) Live check.** Create the fine-grained token described above
   (Settings, then Developer settings, then Fine-grained tokens. Resource owner:
   Tervory-AI. Repository: tervory-tank only. Permission: Administration, Read-only.)
   Save it as the Actions **secret** `RUNNER_STATUS_TOKEN`. The organisation may need
   to approve the token first.

9. **Check it works.** Open a small pull request that changes a non-doc file. In the
   `ci` run, the **pick runner** log should say the runner was chosen, and the `tank`
   job's "Set up job" step should show runner `tervory-ci-1`.

## Docs-only pull requests and required checks

With `paths-ignore`, a pull request that only changes docs or Markdown gets **no** `ci`
or `tisan-site` checks at all. Today the `main` ruleset requires a pull request but
no required status check, so these pull requests can still be merged. If a required
status check (for example `tank`) is ever added to the ruleset, docs-only pull
requests would wait forever for a check that never starts. If that happens, either
keep CI checks out of the required list, or add a tiny always-run workflow that
reports the same check name.

One trade-off to know: a few tests read Markdown files (for example the Tisan template
scan and the skill packages). A change to only those `.md` files won't run CI. The
next non-doc change will catch any break.


## Checks selected by changed paths

Both workflows use `.github/scripts/ci_scope.py`. Pull requests compare the base
and head using their merge base; pushes compare the previous and current main.
Deleted files and both sides of a rename count. Checkout fetches full history,
so large pull requests are not limited to GitHub's changed-file API page size.

- Only docs or Markdown: neither workflow starts.
- Only `agents/<room>/` (plus optional docs): run that room's Python tests and
  the shared secret, room/client isolation, region and schema checks. Multiple
  rooms select the union. Postgres stays enabled for the schema apply checks.
- Tisan room changes also run the Tisan site gate on GitHub-hosted runners.
- `tank/`, `agents/_chassis/`, `workspace/`, shared files, workflow/test changes,
  and unrecognised rooms or paths run all Python tests, the Workspace build and
  the Tisan site gate. This conservative fallback protects new rooms until their
  test mapping is added to the selector.

Room checks include existing room page tests, so Node 22 remains available, but
only a full run installs Workspace packages and runs the global Ruff check.
The lightweight changed-path jobs always use GitHub-hosted runners. The existing
self-hosted choice and fork guards still apply to `tank` and `workspace`.

## Superseded runs are cancelled (CI-2)

`ci.yml` and `tisan-site.yml` share one workflow-level `concurrency` rule:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

- **Pull requests:** a second push to the same pull request cancels the first run.
  Different pull requests, and the two workflows, never cancel each other.
- **`main`:** runs are never cancelled. Each `main` run gets its own group
  (`github.run_id`), so it never waits behind or gets replaced by another `main` run.
  A shared `main` group would let GitHub cancel a *pending* run when a newer one
  queues, even with `cancel-in-progress: false`, and `deploy-on-merge` needs every
  `main` run to finish.

`savings-page` has a 12-minute limit and caches its npm downloads and Playwright
Chromium with `actions/cache`. Bump the cache keys when the pinned `esbuild` or
`playwright` versions in that job change; the tests check they match.
