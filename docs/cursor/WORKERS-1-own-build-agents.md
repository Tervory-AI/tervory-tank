# WORKERS-1: Tervory's own build workers (a server, a sealed computer per task, its own browser)

> Written 18 Oct 2026, 21:45 PT. Goal: our own workers take briefs off the list and open draft PRs, the same way Cursor builders do, on a server the founder owns, with every model call going through Tank.

**Where it runs (updated 18 Oct 21:50):** start on the **Boston server** as its own Coolify app (`tervory-workers`), with `WORKER_MAX_TASKS=1` and per-task limits of 2 CPU / 4 GB, so the live app is never starved. Never on the ZA server (SA data only). When the third server is added (planned before Wednesday 21 Oct), move the app there by changing its Coolify destination and raise the limits below; no code change.

**Files you may change:** new `workers/` folder (service, Dockerfile, task image, tests), new `docker-compose.workers.yml`, `.env.example` (names only), `docs/workers/README.md`, new tests. Do not change Tank's router, ledger or any agent room.

## How it works
1. **Queue.** A brief becomes a task when a GitHub issue is opened with the label `worker` and a body that names one brief file under `docs/cursor/`. The worker service polls for these (GitHub API, read issues; nothing public is exposed).
2. **One sealed computer per task.** Each task runs in a fresh rootless **podman** container (gVisor runtime where available), thrown away at the end. Limits per task come from settings (`WORKER_MAX_TASKS`, `WORKER_TASK_CPUS`, `WORKER_TASK_MEMORY`), default 1 task, 2 CPU, 4 GB, 90 minutes. On the third server: 3 tasks, 4 CPU, 8 GB.
3. **Inside the container:** a clone of `Tervory-AI/tervory-tank`, Python, Node 22, **Chromium via Playwright** (the agents' own browser for tests and screenshots), and **Aider** (Apache-2.0) as the coding engine.
4. **Models through Tank.** Aider calls Tank's model route, never a provider directly, so the ladder, cache, ledger and costs apply. The worker server reaches Tank over a **private link** (WireGuard between the worker server and Boston); Tank stays off the public internet.
5. **GitHub access.** A GitHub App installed on the repo with only: contents write on branches, pull requests write, issues read/write. It **cannot push to `main`** (branch protection) and **cannot merge**. The container gets a short-lived installation token, never a long-lived key.
6. **Same rules as Cursor builders.** Branch `worker/<brief>-<id>`, only the brief's allowed files, draft PR first, CI, then "ready for review" with a plain-English summary. Never merge, never deploy, no secrets in code, URLs, logs or tests.
7. **Network.** Containers may reach only GitHub, the package registries (PyPI, npm), and Tank over the private link. Everything else is refused.
8. **Visible.** Each task writes its status, PR link, minutes and model cost to Tank's ledger, shown on the Tank page as a "Workers" panel (read-only).

## Done when
CI green; on a test brief (for example a one-line copy change) a worker opens a draft PR with CI green and marks it ready, without touching `main`; a test proves the container cannot reach a host outside the allow-list; a test proves the token cannot push to `main`; the Tank page shows the task and its cost.

## Founder after merge
Create the GitHub App from the steps in `docs/workers/README.md` and paste its ID and private key into Coolify yourself. Add branch protection on `main` (require a PR, no direct pushes) if it is not on already.
