# Regional restore drill

Prepared for Grok's return around 4 November 2026. Founder merges; Claude opens the PR from `codex/restore-drill`. No production SQL, settings edits, backup creation, deployment, service restart or live restore was performed by this job.

Read `BACKUP-AUDIT-2026-10-30.md`, `BACKUP-REDEPLOY-FIX-2026-10-30.md` and `BACKUP-RUNTIME-SCOPE-2026-10-30.md` together. The first audit's absent Boston backup worker is historical, not a claim about today's runtime.

## Preconditions on each owning box

Run directly on the regional Linux host, with local Docker permission and enough free space for the encrypted archives, decrypted archive, disposable Postgres and Qdrant. This uses the local `/var/run/docker.sock` explicitly, ignores remote Docker contexts, creates an internal bridge with no published ports, and removes only its randomly named containers/anonymous volumes/network. No existing container, database endpoint or data-volume path is accepted.

The operator supplies an **existing identity file path** through `RESTORE_IDENTITY_FILE`. The program passes that path to `age`; it never opens, copies or prints the identity. Do not put a private identity in an environment variable, command argument value, Docker container, repository or screenshot. Do not enable shell tracing. The offline test creates a temporary tool-generated identity solely for its own synthetic archives, never a production identity.

Use the existing secure operator environment to provide the following names, without displaying or copying values. Founder supplies missing values. Stop if a required name, image, identity file or region is missing; do not borrow another region's settings or change production to make the drill pass.

| Boston | ZA, on ZA host only |
| --- | --- |
| `TANK_REGION=us-east` | `TANK_REGION=za` |
| `R2_ACCOUNT_ID` | `R2_ACCOUNT_ID` |
| `R2_ACCESS_KEY_ID_UPLOADS` | `R2_ACCESS_KEY_ID_ZENAS` |
| `R2_SECRET_ACCESS_KEY_UPLOADS` | `R2_SECRET_ACCESS_KEY_ZENAS` |
| No foreign R2 credential names | `R2_BUCKET_ZENAS_ZA` (existing fixed regional bucket) |

Do not pass `DATABASE_URL`, `QDRANT_URL`, a model key or a production database password. The archive reader uses only LIST and GET through existing `Storage` and `restore_archive`. Boston uses the uploads private platform backup prefix. ZA uses the existing ZA Zenas encrypted platform backup prefix and bucket contract, including its existing `public=True` storage flag; that flag does not publish or decrypt anything. ZA plaintext stays in temporary files and disposable containers on the ZA host. Do not download ZA archives onto Boston or attach real archive/data files to GitHub.

## Prepare the isolated checkout and tools (each box)

Use a new inspection directory; do not replace another chat's checkout. Before merge use the review branch. After founder merge, use the reviewed merge commit instead.

```sh
set +x
mkdir -p "$HOME/restore-drill-review"
git clone --branch codex/restore-drill --single-branch https://github.com/Tervory-AI/tervory-tank.git "$HOME/restore-drill-review/repo"
cd "$HOME/restore-drill-review/repo"
git rev-parse HEAD
python3 -m venv .git/restore-venv
.git/restore-venv/bin/pip install pytest==9.1.1 pytest-asyncio==1.4.1 httpx==0.28.1
command -v age
command -v age-keygen
docker --host unix:///var/run/docker.sock image inspect postgres:16.15 --format '{{.Id}}'
docker --host unix:///var/run/docker.sock image inspect qdrant/qdrant:v1.20.0 --format '{{.Id}}'
```

The drill uses the same Postgres major and Qdrant image versions as both checked-in regional stacks. The program uses `--pull=never`. If a tool/image is absent, stop and record its name; preparation can install the existing free `age` package or pull those exact images before retrying. It does not start or redeploy the production stack. For an already present review directory, inspect its branch and status rather than rerunning clone over it.

## Boston command (Boston host only)

`RESTORE_IDENTITY_FILE` is the operator-selected existing file path, never the private identity itself. The current shell must already have the Boston names above, without foreign R2 credential pairs.

```sh
set +x
cd "$HOME/restore-drill-review/repo"
: "${RESTORE_IDENTITY_FILE:?Existing identity file path is required}"
: "${R2_ACCOUNT_ID:?R2_ACCOUNT_ID is required}"
: "${R2_ACCESS_KEY_ID_UPLOADS:?R2_ACCESS_KEY_ID_UPLOADS is required}"
: "${R2_SECRET_ACCESS_KEY_UPLOADS:?R2_SECRET_ACCESS_KEY_UPLOADS is required}"
export TANK_REGION=us-east
export R2_ACCOUNT_ID R2_ACCESS_KEY_ID_UPLOADS R2_SECRET_ACCESS_KEY_UPLOADS
export TMPDIR
TMPDIR=$(mktemp -d /var/tmp/restore-drill.XXXXXX)
.git/restore-venv/bin/python ops/restore_drill.py --region us-east --identity-file "$RESTORE_IDENTITY_FILE" --rls
restore_status=$?
rmdir "$TMPDIR"
unset TMPDIR
exit "$restore_status"
```

## ZA command (ZA host only)

Do not run this real-backup command on Boston, CI or a laptop. Verify the session is on the ZA box first. It uses only ZA Zenas storage names; do not transplant Boston settings. If ZA is offline or no completed ZA backup exists, stop with that fact; do not activate the stack or create a new production backup under this job.

```sh
set +x
cd "$HOME/restore-drill-review/repo"
: "${RESTORE_IDENTITY_FILE:?Existing identity file path is required}"
: "${R2_ACCOUNT_ID:?R2_ACCOUNT_ID is required}"
: "${R2_ACCESS_KEY_ID_ZENAS:?R2_ACCESS_KEY_ID_ZENAS is required}"
: "${R2_SECRET_ACCESS_KEY_ZENAS:?R2_SECRET_ACCESS_KEY_ZENAS is required}"
: "${R2_BUCKET_ZENAS_ZA:?R2_BUCKET_ZENAS_ZA is required}"
export TANK_REGION=za
export R2_ACCOUNT_ID R2_ACCESS_KEY_ID_ZENAS R2_SECRET_ACCESS_KEY_ZENAS R2_BUCKET_ZENAS_ZA
export TMPDIR
TMPDIR=$(mktemp -d /var/tmp/restore-drill.XXXXXX)
.git/restore-venv/bin/python ops/restore_drill.py --region za --identity-file "$RESTORE_IDENTITY_FILE" --rls
restore_status=$?
rmdir "$TMPDIR"
unset TMPDIR
exit "$restore_status"
```

## Results and failure handling

Successful JSON contains the selected dated completion manifests, `restore_seconds` (container startup, decryption, restore and counts; excludes download and RLS), `tenant_table_rows` (total for every restored table containing `tenant_id`), exact `collection_points`, and `rls_failures`. SQL uses only the disposable Postgres. No tenant IDs, row contents or identity material are printed. The operator must retain stdout, exit status, UTC time, hostname/region, checked-out commit and image IDs as the regional evidence.

Selection uses the newest completed Postgres manifest and newest completed manifest **per Qdrant collection**. It is not an atomic cross-store snapshot, and does not claim deleted/never-backed-up collections are present. An empty SQL or Qdrant backup inventory fails closed. Existing archive checksums verify every part before decryption. Failed decrypt/restore exits nonzero and does not claim counts or completion. Ordinary errors are reduced to an error type to avoid exposing SQL, rows, identity or provider responses. After a hard host/process kill, inspect only names beginning `restore-drill-`; do not prune Docker globally. Remove only resources carrying that drill's `tervory.restore-drill` label. Restrict any interrupted temporary directory on that same regional host until its contents can be safely removed.

With `--rls`, all existing `db/migrations/tenant_rls/*.sql` run against the restored database, and **every failed migration path** is returned. The drill then runs `tests/tenant_rls`; its restored-copy tests enumerate every actual restored tenant table, require enabled and forced RLS plus a restrictive policy, verify unscoped reads return zero, and compare scoped reads against restored counts for each tenant. Each failing table/test path is returned from JUnit; collection/runner failure also makes the drill fail. These tests are read probes; they do not replace #428's broader synthetic INSERT/UPDATE/DELETE and service-startup suite in `tests/test_tenant_rls.py`. No migration or role is applied outside the disposable container.

Counts and elapsed time establish recovery of the selected archives. Production-source comparison counts are not collected by this job. Never infer backup freshness, pre-backup/source equality or founder browser acceptance from offline checks.

## Offline verification and watchdog evidence

Exact executed commands during preparation:

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-restore-drill
git fetch origin main && git checkout -B codex/restore-drill origin/main
ls docs/ops/BACKUP-AUDIT-2026-10-30.md jobs/train/r2_archive.py db/migrations/tenant_rls/ tests/tenant_rls .github/workflows/watchdog.yml .github/scripts/watchdog.py
sudo -n apt-get install -y age
RESTORE_DRILL_E2E=1 /tmp/tervory-rls-python/bin/python -m pytest -q tests/test_restore_drill.py --tb=short
```

Clone/fetch/checkout and file inventory passed. The preexisting isolated Python environment supplies pytest/httpx. Installing age succeeded. First roundtrip attempt failed twice because Docker internal networks do not supply published-port bindings; corrected to the newly created container's private bridge IP, with no ports published. Next run: **3 passed, 13 existing dependency warnings, 49.05 seconds**, including both regional synthetic fixtures and archive-corruption refusal. No live storage, database or model used. Dedicated `.github/workflows/restore-drill.yml` runs this same real-container/age test on push to the review branch and relevant PRs; synthetic ZA test objects are entirely local, not ZA client archives.

The latest failed watchdog run inspected was [41116835210](https://github.com/Tervory-AI/tervory-tank/actions/runs/41116835210), Check job `124273143654`, 30 October 2026 12:38 PDT. The decisive log lines were `rig.tervory.com` HTTP **503**, while `agent-rig` was `running:healthy`; it opened incident #452 and exited 1. This was a real public-endpoint outage, not a Python exception or missing setting. Preserve that detection.

Existing completed work has already recovered it: [41337506842](https://github.com/Tervory-AI/tervory-tank/actions/runs/41337506842), Check job `124940330500`, **success**, 1 November 2026 10:36 PST. Logs show Rig HTTP **200**, all four public endpoints HTTP 200, and Boston/ZA applications healthy. The two preceding listed watchdog runs `41313066924` and `41282106873` were also successful. No watchdog code, thresholds, skip rules, settings or production resources were changed to manufacture a green run. This reuses existing recovery, as required by the brief.

Queries executed: `gh run list --repo Tervory-AI/tervory-tank --workflow watchdog.yml --limit 3 --json databaseId,conclusion,headSha` and the same list with `--status failure --limit 2 --json databaseId,headSha,createdAt`. Job logs and summaries were read through the connected GitHub job-log tool for the exact job IDs above. `gh run view ... --log-failed` initially failed to cache in the shared /tmp quota; a task-owned TMPDIR command returned no log text, so the connector supplied the actual evidence. No raw secret values were accessed. The first git commit required setting this clone's missing author identity; local Codex author configuration fixed it, then the real source commit and every completed file were committed/pushed normally.

## Founder acceptance still pending

Grok's real regional execution and the founder's own-browser demonstration/screenshots are pending. No screenshot or live restore result is fabricated. The PR must include the exact-head CI link, regional result JSON and founder-test screenshots when available. Offline success is preparation evidence, not product completion.

## Identity database on ZA

After deploying the separate `identity-za` resource, its worker uses the existing
streaming encrypted Postgres backup/archive path with the label
`identity/database.dump.age`, inside the existing ZA regional platform backup
prefix. It has its own database role and named Postgres volume; it does not dump
through the main ZA database connection. See [IDENTITY-ZA.md](IDENTITY-ZA.md).

Use the same secure ZA operator environment, existing private identity **file
path**, checkout/tools and completed Tank/Qdrant archives described above. On the
**ZA host only**, the acceptance command additionally requires the identity dump:

```sh
.git/restore-venv/bin/python ops/restore_drill.py --region za --identity-file "$RESTORE_IDENTITY_FILE" --rls --identity
```

`--identity` fails if that completed encrypted archive is absent, and is refused
on us-east. Identity cannot substitute for a required Qdrant archive. When an
identity archive is present on ZA, selection includes its newest completed
manifest; it restores into **identity_restore**, a separate database in the
newly created disposable Postgres container. No production SQL or database
connection is added. Main Tank RLS checks remain on the restored Tank database.
Success includes `identity_database_restored: true` and a nonzero
`identity_table_count`. Counts are metadata only, never identity user rows.

This is a database restore proof. Keep the immutable original
`ZITADEL_MASTERKEY` securely outside the backup, and retain the identity resource's
operator settings and Login/bootstrap named volumes; the database dump does not
back up those separate secret volumes. Do not put a master key or private age
identity in a command, PR, screenshot, or repository.

Offline coverage now includes a synthetic identity database in the existing
real-container/age ZA round trip, with a separate identity-archive requirement
and refusal to treat identity as a Qdrant snapshot. This does not claim the live
ZA identity database has been restored; founder acceptance remains pending.
