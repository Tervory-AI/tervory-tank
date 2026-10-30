# Boston backup: shared runtime environment drift

Report updated 30 October 2026, 11:12:23 PDT / 18:12:23 UTC. Base main `fdc45642bedcd859d803b05a61efc2b927b5bf60`.

## Post-merge result and cause

Founder merged #441 at 10:59:18 PDT / 17:59:18 UTC, merge `fdc45642bedcd859d803b05a61efc2b927b5bf60`. Its automatic deploy-on-merge run is `41102958930`; no duplicate deployment was dispatched by this lane.

At 11:04:25 PDT / 18:04:25 UTC, ordinary deployment created `r2-backup-xnmc0jkz8j9i5jh1jwanbsfv-20261030T175956` with no profile, `unless-stopped`, the original encrypted spool volume and normal nightly CMD. However it was restarting with exit 1. #441 fixed worker omission, but this runtime result is not healthy or completed backup proof.

A selected names-only inspect found all seven required configuration names nonempty, plus **`R2_ACCESS_KEY_ID_GHOST` and `R2_SECRET_ACCESS_KEY_GHOST`**. `Storage('uploads')` refuses foreign R2 credential names before the nightly loop, as required. That guard is unchanged.

The saved generated compose has only the correct UPLOADS names explicitly, but also `env_file: ['.env']`. Static inspection of the running Coolify source established:

- `/var/www/html/app/Jobs/ApplicationDeploymentJob.php:848` unconditionally adds that shared `.env` to every normal Compose service.
- The same file at `:1971` includes application settings with `is_runtime=true` in the runtime environment.
- Main `docker-compose.yml` has zero references to either GHOST name. Ghost's separate resource needs its own pair; this repair does not change that resource.

No per-service opt-out survives that unconditional normal-Compose rewrite. Switching the entire application to raw Compose would change unrelated deployment behavior and is not used.

## Minimal permanent correction and drift protection

The installed Coolify controller supports `PATCH /api/v1/applications/{uuid}/envs` for an **existing key**. It returns 404 if absent. At `ApplicationsController.php:4045–4048`, the value changes only when the request contains a `value` field. The correction therefore sends only:

```json
{"key":"R2_ACCESS_KEY_ID_GHOST","is_preview":false,"is_runtime":false}
```

and the same flags for `R2_SECRET_ACCESS_KEY_GHOST`, on main UUID `xnmc0jkz8j9i5jh1jwanbsfv` only. Existing values, build flags, preview settings and the Ghost resource are preserved. PATCH response bodies are discarded without being read. GET inventory handling accesses only key/preview/runtime metadata and never accesses or emits value fields; no raw API response is printed or saved.

- `.github/scripts/backup_runtime_scope.py:22,46,61,91`: fixed resource/two-key metadata repair, checks existing names and absence of main Compose consumers before writing, rejects unexpected foreign owners, preserves UPLOADS names, verifies postconditions and is idempotent. Missing/ambiguous metadata fails closed; no key is created. A partial PATCH failure stops without any deploy request.
- `.github/workflows/coolify-ops.yml:60–77`: adds fixed `op=backup-scope`; caller cannot supply arbitrary app/key/room inputs. It never deploys. Manual main `op=deploy` first runs the read-only scope gate; room deploys are unchanged.
- `.github/scripts/deploy_changed.py:140–144`: checks runtime credential-name scope before replacing main, blocking a future foreign pair reintroduction before any deploy call.
- `tests/test_backup_runtime_scope.py:47,107,122,158` and `tests/test_deploy_changed.py:257`: mocked GET/PATCH contract including the real HTTP helper against a fake controller with unchanged synthetic server-side value markers, exact allowed fields/path, no value-field access, discarded mutation body, idempotence, refusal/partial-failure cases, automatic and manual deployment gate ordering.

## Commands and evidence

```sh
gh pr view 441 -R Tervory-AI/tervory-tank --json state,mergedAt,mergeCommit,headRefOid
gh run list -R Tervory-AI/tervory-tank --workflow deploy-on-merge.yml --limit 3 --json databaseId,headSha,status,conclusion,createdAt
docker ps -a --filter name=r2-backup --format '{{.Names}} status={{.Status}}'
```

All succeeded. Merge/run above confirmed. New worker status was `Restarting (1)`; the previous founder-repaired healthy worker had been replaced by the automatic deployment.

The selected runtime projection used this exact command; no raw inspect or credential value reached the transcript:

```sh
python3 - <<'PY'
import subprocess,json
name='r2-backup-xnmc0jkz8j9i5jh1jwanbsfv-20261030T175956'
d=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
e=dict(item.split('=',1) for item in d['Config']['Env'])
names=['DATABASE_URL','QDRANT_URL','QDRANT_API_KEY','R2_ACCOUNT_ID','R2_ACCESS_KEY_ID_UPLOADS','R2_SECRET_ACCESS_KEY_UPLOADS','R2_BACKUP_RECIPIENT']
print(json.dumps({'container':name,'image':d['Image'],'state':d['State']['Status'],'exit_code':d['State']['ExitCode'],'restart':d['HostConfig']['RestartPolicy']['Name'],'setting_present':{n:bool(e.get(n)) for n in names},'r2_names':sorted(n for n in e if n.startswith('R2_')),'mounts':[{'type':m['Type'],'name':m.get('Name'),'destination':m['Destination']} for m in d['Mounts']],'compose':d['Config']['Labels'].get('com.docker.compose.project.config_files')}))
PY
```

Exit 0: image `sha256:0e09506a4ed1daa1c22fa1c3e7fdc63817634e933b7a86eda36f5209a0dfc433`, restarting/exit1, `unless-stopped`; seven required presence booleans true; the two GHOST names present alongside UPLOADS; volume `xnmc0jkz8j9i5jh1jwanbsfv_r2-backup-spool` mounted at `/tmp`; compose `/artifacts/kmrecypt7grajkwjnn34jbkf/docker-compose.yml`.

```sh
/tmp/tervory-rls-python/bin/python -m pytest -q tests/test_backup_runtime_scope.py tests/test_deploy_changed.py
/tmp/tervory-rls-python/bin/python -m pytest -q tests/test_backup_runtime_scope.py tests/test_deploy_changed.py tests/test_backup_deploy_persistence.py tests/test_bucket1_storage.py tests/test_bucket1_integration.py tests/zenas_docassemble/test_deployment.py
git diff --check
```

Final results: **27 passed** (0.18s); **136 passed** (6.47s), both with 13 existing environment deprecation warnings; whitespace check passed. An initial workflow assertion used a required step name on an unnamed checkout step; fixed to optional lookup before the passing runs. Independent review identified the manual-deploy bypass and requested real-transport/gate integration proof; both were fixed on this same branch. Finished files were committed and pushed individually without force pushes.

## Safe execution boundary

No scope operation, settings mutation, manual deployment, container restart, SQL, forced backup or secret-value change has been executed by this lane. Founder alone merges after exact-head review and CI. After merge, coordinator runs the fixed `backup-scope` metadata operation first, then a single coordinated main deployment through the existing gated interface. Verify generated/runtime names, restart policy, original volume and health afterwards. Do not infer upload success, SQL restore counts/duration or founder acceptance from health. ZA remains untouched.
