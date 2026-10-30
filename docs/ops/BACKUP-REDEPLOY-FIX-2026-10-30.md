# Boston backup redeploy persistence

Prepared 30 October 2026, 10:40:09 PDT / 17:40:09 UTC. Base main: `14d16a0`.

The founder repaired the Tank encrypted R2 backup and reported it healthy, but ordinary Tank redeployments repeatedly removed it. The earlier missing-runtime snapshot in BACKUP-AUDIT-2026-10-30.md is historical, not the current runtime status.

## Cause and change

The repository and the saved Coolify composition both retained `profiles: [r2-backup]` and `restart: "no"`. A real Compose dry run with no profile omitted the worker, independently reproducing the defect without changing live resources.

- `docker-compose.yml:309–315`: remove Boston's opt-in profile and use `unless-stopped` so ordinary redeployments retain the already founder-enabled backup.
- `tests/test_backup_deploy_persistence.py:14–46`: exercise real Compose dry-run deployment selection from isolated artifact and saved-compose paths, with no inherited profile or setting values; check worker volume, read-only filesystem, image source, recipient setting name and unchanged ZA opt-in profile.
- `tests/test_bucket1_integration.py:45–86`: align Boston persistence assertions and retain credential ownership/ZA isolation assertions. The existing room loop also needed to recognize the separate US/ZA Docassemble sidecars, including their public recipient name.
- `jobs/train/README.md:144–162`: replace the old default-off/manual-enable instructions and state the scheduling/proof limits.

Encryption code, age recipient handling, credential names, encrypted-only spool volume, worker image, database/Qdrant dependencies and ZA deployment configuration remain unchanged. There is no production activation, Tank redeployment, SQL, private identity access or new setting value in this work.

## Read-only runtime evidence

```sh
docker ps -a --filter name=backup --format '{{.Names}} status={{.Status}}'
```

At approximately 10:31 PDT / 17:31 UTC, the repaired `r2-backup-xnmc0jkz8j9i5jh1jwanbsfv-20261030T172113` was Up 5 minutes (healthy); the Docassemble backup sidecar was also healthy. These are runtime observations, not backup-success/restore proof.

```sh
docker inspect --format '{{ index .Config.Labels "com.docker.compose.project.config_files" }} {{ index .Config.Labels "com.docker.compose.project.working_dir" }}' r2-backup-xnmc0jkz8j9i5jh1jwanbsfv-20261030T172113
```

Exit 0: `/data/coolify/applications/xnmc0jkz8j9i5jh1jwanbsfv/docker-compose.yaml /data/coolify/applications/xnmc0jkz8j9i5jh1jwanbsfv`.

The same project's Tank deployment used an ephemeral `/artifacts/.../docker-compose.yml` path, reported by the watchdog owner using selected Compose labels only. The root cause is profile-based selection, not a claim that these different paths alone cause the defect.

The saved compose was inspected through a root-owned file read that returned only selected nonsecret service fields:

```sh
sudo -n python3 - <<'PY'
from pathlib import Path
import yaml,json
p=Path('/data/coolify/applications/xnmc0jkz8j9i5jh1jwanbsfv/docker-compose.yaml')
d=yaml.safe_load(p.read_text());s=d['services'].get('r2-backup');print(json.dumps({'compose_path':str(p),'service_present':s is not None,'profiles':s.get('profiles'),'restart':s.get('restart'),'build':s.get('build'),'volumes':s.get('volumes'),'command':s.get('command')}))
PY
```

Exit 0: service present, profile `["r2-backup"]`, restart `"no"`, Dockerfile `jobs/train/Dockerfile.backup`, spool `xnmc0jkz8j9i5jh1jwanbsfv_r2-backup-spool:/tmp`, command unset (the image's existing nightly CMD is used). No environment values were output. An initial unprivileged read returned PermissionError; the selected read above succeeded.

## Regression and verification

```sh
/tmp/tervory-rls-python/bin/python -m pytest -q tests/test_backup_deploy_persistence.py
```

On unchanged main composition: **2 failed**, both `ordinary redeploy drops the profiled backup`. After the compose fix: **2 passed**. Tests invoke `docker compose --project-name backup-regression --dry-run -f <isolated-file> up -d --no-build --pull never --no-deps` twice for each path. Only Coolify's `exclude_from_hc` metadata is removed before parsing; this is not standard Compose syntax. `--no-deps` avoids unrelated existing dependency waits and does not claim runtime dependency readiness. `config --services` was rejected as selection proof because the installed Compose v5.6.0 includes disabled-profile services in that listing. An initial test draft also compared nondeterministically ordered output; the committed regression checks worker inclusion instead.

```sh
/tmp/tervory-rls-python/bin/python -m pytest -q tests/test_bucket1_integration.py
```

Initial run: **1 failed, 21 passed**, because the preexisting room-loop assumptions did not recognize the separate ZA Docassemble compose filename/recipient name. After preserving those existing sidecars explicitly: **22 passed**.

```sh
/tmp/tervory-rls-python/bin/python -m pytest -q tests/test_backup_deploy_persistence.py tests/test_bucket1_storage.py tests/test_bucket1_integration.py tests/zenas_docassemble/test_deployment.py
```

**109 passed**, 13 environment deprecation warnings, in 7.81 seconds. These are offline/mocked storage checks and Compose dry runs; no model or production query was used.

```sh
git diff --check
docker ps -a --filter name=backup-regression --format '{{.Names}}'
docker volume ls --filter name=backup-regression --format '{{.Name}}'
```

All exit 0; no whitespace errors, no test containers and no test volumes. Each finished file was committed and pushed successfully on `codex/backup-redeploy-persistence-20261030`, without force pushes.

## Review and remaining operational proof

Founder alone merges. Independent exact-head review and hosted CI are required. No live redeployment was run or authorized by this report; coordinate any eventual deployment so the founder's repaired backup remains protected.

The worker still schedules its next run at 02:00 UTC after a restart and does not immediately catch up missed runs. `unless-stopped` restarts errors but does not change that schedule. Healthy configuration does not prove successful uploads. A fresh dated main SQL archive, isolated SQL restore, comparison counts and duration remain separate unresolved proof requirements. Founder screenshots/walkthrough remain last; none are supplied or claimed here.
