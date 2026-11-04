# Window agents and PR reviews

Tank owns durable jobs, tenant/user authorization and receipts. The existing worker
server polls them independently of window lifetime. `tank/main.py` registers the
router; `workers/service.py` shares its existing worker slot and health state with
the poller. No model provider or paid route is added. Every model request goes
through the existing command code-turn with `model: auto`.

Task containers reuse the worker image and `cli/src/code-mode.mjs`. They require
rootless Podman, start as UID 1001 with all capabilities dropped, no-new-privileges,
a read-only root, private temporary filesystems and no host socket. The private
PID namespace allows only `/proc/*` unmasking for the CLI's nested Bubblewrap
command sandbox. Only a job-scoped Tank lease and the selected GitHub credential
enter the container; the worker's Tank service key stays on the server. Cancel
revokes the lease and stops the named container. Stale jobs fail after two minutes
without a heartbeat and are never automatically replayed after an uncertain push
or charge.

The window saves a GitHub token through a masked field to the user's existing
vault. Jobs carry its name only. Tasks push a `worker/window-<uuid>` branch to the
user's repository and create a draft PR against its actual default branch. There
is no merge operation. Reviews read the PR diff without executing repository code,
validate comment locations and bind comments to the reviewed commit. An explicitly
enabled, HMAC-verified webhook deduplicates deliveries for the same PR head; queued
obsolete heads are superseded before a model call. Manual reviews use the latest
head when the worker starts.

Job lists include all running jobs plus up to 100 recent active and 100 finished
jobs. Receipt reads reuse Tank's public receipt projection and totals, scoped to
the same tenant and user. Migrations are additive, retain tenant RLS and grant the
existing application role access only to this feature's new tables.

## Validation

Run with the repository's Python test dependencies and an isolated PostgreSQL
connection in `POOL_SCHEMA_DATABASE_URL`:

```sh
python -m pytest -q tests/test_window_agents.py tests/test_window_agent_reviews.py
bash scripts/precheck.sh
```

The fake-GitHub acceptance test uses real Git commits, a local bare remote, the
production task and review functions and the actual CLI agent loop. GitHub and
Tank/model responses are fake; it incurs no model charges and creates no real PR.
To include the CLI command sandbox, run inside the derived worker image:

```sh
podman build -t tervory-window-agent:1 -f workers/window_agent/Dockerfile .
podman run --rm --label tervory.test=1 --name codex-agents-fake-github-e2e \
  --user 1001:1001 --cap-drop ALL --security-opt no-new-privileges \
  --security-opt 'unmask=/proc/*' --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --tmpfs /work:rw,nosuid,nodev,mode=1777,size=256m --env TMPDIR=/work \
  --entrypoint python3 tervory-window-agent:1 \
  /opt/tervory/workers/window_agent/test/e2e.py --check-command
```

The extension lives in `Tervory-AI/tervory-window`, at
`extensions/tervory-agents/`. Its README lists the Figma frames required before
replacing plain wording placeholders. User fields are recorded in
`docs/ops/FOUNDER-SETTINGS.md`. No new deployment setting is required.
