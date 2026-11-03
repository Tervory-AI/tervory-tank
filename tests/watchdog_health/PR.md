# Watchdog health coverage — 2026-10-30 07:00 PDT / 14:00 UTC

Failed run: https://github.com/Tervory-AI/tervory-tank/actions/runs/41021643887
Job 123950086781 at main 1cb2759a7c6fff731d135755deaf45c9e1f19257 failed because `trigger-crm` and `zenas-docassemble` were `running:unknown`. Existing incidents are #402 and #423. Its four public probes returned HTTP 200; other US applications were healthy; ZA was explicitly skipped by `ZA_OFFLINE=true`. This is incomplete application health coverage, not evidence the public sites were down.

Current Boston read-only container inventory showed CRM frontend/backend/redis healthy, Celery worker/beat running without healthchecks; Docassemble healthy, backup running without a healthcheck. The corresponding three services have no healthcheck in the existing Compose files. This change gives each a probe without weakening watchdog failure policy.

## Changed lines

- `ops/trigger-crm/docker-compose.yml:131`: targeted `celery@HOSTNAME` RPC ping with bounded timeout; another worker cannot mask a failed worker.
- `ops/trigger-crm/docker-compose.yml:180`: beat process identity probe (handles direct and Python-wrapped entrypoints).
- `agents/zenas/docker-compose.docassemble.yml:77` and `agents/zenas/docker-compose.docassemble.za.yml:77`: scheduled backup process identity probe.
- `tests/watchdog_health/test_health_probes.py:1`: offline positive/negative probe checks.

Beat and backup probes prove process liveness only. They do not prove timely job execution, a completed encrypted backup, upload, or restore. The backup worker already exits on configuration/encryption/upload failure. Real backup and endurance evidence remain separate build tasks. No secret values were read or created.

## Commands and results

- `git clone -q https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-watchdog-priority-20261030`; `git fetch origin main`; `git checkout -b codex/watchdog-priority-20261030 origin/main`: passed. Initial unrelated `find ..` reported permissions on systemd directories; repository AGENTS.md was found/read.
- GitHub connector `fetch_workflow_run_jobs(run_id=41021643887)` and `fetch_workflow_job_logs(job_id=123950086781)`: succeeded; earlier gh empty logs did not mean unavailable evidence.
- `docker ps --format '{{.Names}} {{.Status}}'`: inventory described above; no container environment or raw logs inspected.
- `docker exec celery-worker-aty7tukal0rlksfpet1mzplb-20261028T154528 sh -c 'celery -A crm inspect ping --destination "celery@$HOSTNAME" --timeout 5 >/dev/null 2>&1'`: exit 0, targeted worker answered (read-only broker control ping).
- Exact committed `healthcheck.test` argv extracted with `yaml.safe_load` and executed via `subprocess.run(['docker','exec',container,*command], capture_output=True)` against `celery-beat-aty7tukal0rlksfpet1mzplb-20261028T154528`, the worker above, and `docassemble-backup-iumzytsbbvjn2ah2wmlvuiyk-20261028T194340`: all three exit 0; no probe output exposed. For CMD-SHELL only, `$$` was rendered to `$` as Compose does.
- `python3 -m unittest discover -s tests/watchdog_health -v`: 3 tests passed, including wrong/missing process arguments and both supported Celery entrypoints; rerun after merging current main passed in 0.043s.
- `docker compose -f ops/trigger-crm/docker-compose.yml config --no-interpolate --quiet`: exit 0.
- `docker compose -f agents/zenas/docker-compose.docassemble.yml config --no-interpolate --quiet`: exit 0.
- `docker compose -f agents/zenas/docker-compose.docassemble.za.yml config --no-interpolate --quiet`: exit 0. No runtime setting values supplied or printed.
- `git diff --check`: passed.
- `git fetch origin main`; `git merge --no-edit origin/main`: current main a6a655fc merged normally; no conflicts. Initial merge attempt needed local committer identity, configured only in this checkout, then succeeded.
- Every finished file was committed and normally pushed. No force push. No production SQL, deployment or setting changes.

Corrections during implementation: host `python` was unavailable, so used `python3`; initial beat probe assumed argv[0] was Celery, read-only runtime exit 1 exposed Python wrapper, fixed to match exact executable basename anywhere in argv; initial test compared timeout strings, corrected to numeric seconds. Final committed probes and tests pass.

## Remaining gates

Separate review and exact-head hosted CI pending. Founder acceptance is last after the entire build plan; no founder screenshots claimed. After founder merge, deploy standalone `trigger-crm` and `zenas-docassemble` resources (not selected by current `agent-*` automatic deployment filter), then verify aggregate Coolify health and the next scheduled watchdog run. ZA matches coverage but remains intentionally offline; do not activate it. Never close incidents manually to hide a failure; watchdog closes them on actual recovery.
