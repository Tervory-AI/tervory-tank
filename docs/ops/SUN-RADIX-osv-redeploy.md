# SUN-RADIX — refresh Radix advisories, then scan the two mains

Issue #309. Boston only. The founder merges this note and runs the steps. Nobody else merges, and nobody pushes to `main`.

This refreshes the advisory database baked into `agent-radix`, then tells Tank to hand Radix a git bundle of `main` for `Tervory-AI/tervory-tank` and `Tervory-AI/tervory-rig`. Radix does not clone. Names only: no key, token, or password value in a command, a log, or a message to the founder.

## 1. Redeploy `agent-radix` so the bake runs

The advisory file is `/opt/osv/osv.sqlite`. The image builds it. The `osv` stage of `agents/radix/Dockerfile` downloads the public PyPI and npm exports and runs `osv_bake.py`. A rebuild runs that stage again. Restarting the current container keeps the old file.

1. In Coolify, open the Boston application named `agent-radix`. Leave **Advanced → Raw Compose Deployment** on. That switch is what keeps the room sealed (SEAL-1). This step does not change it.
2. Deploy with **Force deploy (without cache)**. That is the Coolify control for a rebuild that does not reuse Docker's cache. The API form is `POST /api/v1/deploy?uuid=<agent-radix application uuid>&force=true`. The uuid is on that application's page. The bearer token is the secret named `COOLIFY_TOKEN`. The address is the variable named `COOLIFY_URL`, and it must stay `https://`.
3. Do not use the `coolify-ops` workflow op `deploy` for this refresh. That op sends `force=false` (`.github/workflows/coolify-ops.yml`). Op `status` is safe: it lists application names, uuids, and status, and it does not deploy.
4. Wait until that deployment says **Success**. In the build log, the `osv` stage must run `python /bake/osv_bake.py` and print one JSON line with `bytes` and `ecosystems`. A line that says the `osv` stage was cached means the file was not rebuilt. Stop and tell the founder. Do not scan on a stale file.
5. The same Dockerfile also builds `egress-proxy`. A rebuild of this application rebuilds both. That is expected.
6. If the deployment does not reach **Success**, or the room is unhealthy, stop. In Coolify, roll `agent-radix` back to the previous **Success** before any scan.

Coolify's own docs say a custom Docker Compose build command ignores the cache toggle. This application does not set one. Its compose file uses `build:` with `dockerfile: radix/Dockerfile`. The proof is still the log line from `osv_bake.py`, not the button label.

The build fails on its own when an export looks truncated, or when the two known advisories `GHSA-8q59-q68h-6hv4` (PyPI) and `GHSA-xvch-5gv4-984h` (npm) are missing. A failed build must not be treated as a clean scan.

## 2. Prove the new file, then the seal

On the Boston host, in the Coolify terminal on localhost. Read-only. Print counts and the bake time, not advisory text.

```bash
radix=$(docker ps --filter label=com.docker.compose.service=agent-radix --filter status=running --format '{{.ID}}' | head -n 1)
test -n "$radix"
docker exec "$radix" python -c 'import os,sqlite3; p="/opt/osv/osv.sqlite"; print("bytes", os.path.getsize(p)); c=sqlite3.connect("file:"+p+"?mode=ro", uri=True); print(list(c.execute("select ecosystem, records, rows, baked_at from meta order by ecosystem")))'
```

`baked_at` is UTC and should match this deploy. `records` should be in the thousands for PyPI and the tens of thousands for npm. The build floors are 5,000 and 20,000. Then:

```bash
bash ops/seal-check.sh
```

The `agent-radix` line must say `sealed`, and the script must exit 0. `LEAK`, `NOT FOUND`, or `NOT SEALED` means stop. Do not scan.

## 3. Build a git bundle of each `main`

Run this on the Boston host, with the access that host already has. Do not put a token in the clone URL. Do not clone on a laptop. Depth 1 is enough: after Radix unpacks a bundle it deletes `.git`, so the scan sees the tip tree.

```bash
git clone --depth 1 --branch main https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-tank-main
git -C /tmp/tervory-tank-main bundle create /tmp/tervory-tank-main.bundle HEAD
git -C /tmp/tervory-tank-main rev-parse --short HEAD

git clone --depth 1 --branch main https://github.com/Tervory-AI/tervory-rig.git /tmp/tervory-rig-main
git -C /tmp/tervory-rig-main bundle create /tmp/tervory-rig-main.bundle HEAD
git -C /tmp/tervory-rig-main rev-parse --short HEAD

wc -c /tmp/tervory-tank-main.bundle /tmp/tervory-rig-main.bundle
```

Keep the two short commit ids. They go in the report. Delete `/tmp/tervory-tank-main` and `/tmp/tervory-rig-main` after the bundles exist. Do not commit a bundle, and do not print its bytes.

## 4. Stop if a bundle is over 32 MiB

Radix refuses a source larger than 32 MiB (`MAX_SOURCE` in `agents/radix/scanlib/archive.py`, 33554432 bytes). That check applies to a `file:` on the room volume as well as to base64 in the job. The job must not carry the bundle: `agent_radix.jobs.input` would store it.

Measured from the `tervory-tank` checkout on 25 Oct 2026, commit `886656d`:

| Bundle | Size |
| --- | --- |
| `git bundle` of `HEAD` (full history reachable from that commit) | 48 MiB |
| depth-1 `HEAD` | 45 MiB |

Both are over 32 MiB. The working tree of that commit is about 105 MiB. `agent-radix` has `mem_limit: 256m`.

**Founder decision, before any scan of current `tervory-tank` main:** raise `MAX_SOURCE`, and decide whether 256 MiB is enough for a scan of that tree. This note does not change either limit. Until you do, do not copy that bundle into the room and do not post the job. Tell the founder the measured size and stop that repo.

`tervory-rig` was not measured here. Run `wc -c` on its bundle and apply the same 32 MiB stop.

A bundle at or under 32 MiB continues below. One repo can proceed while the other waits.

## 5. Hand the bundle to Radix through Tank

The platform tenant is `00000000-0000-0000-0000-000000000001`. The file name has no colon. The room reads `file:<name>` from `/data/<tenant_id>/<name>`.

`POST /v1/ghost/radix` is the Autumbra Watch corridor. It accepts a tar or zip, caps the body, and refuses a git bundle. These scans do not use it.

Tank already calls the room with header `X-Tank-Key` set from the variable `TANK_KEY_RADIX` (`tank/ghost_routes.py`, `call_room`). Post the job from the Tank container so the value is read inside that container. The command below does not print the variable. Leave shell tracing off (`set +x`).

`$radix` is the container id from section 2. In a new shell, set it again with the same `docker ps` filter before the copy.

```bash
tank=$(docker ps --filter label=com.docker.compose.service=tank --filter status=running --format '{{.ID}}' | head -n 1)
test -n "$radix" && test -n "$tank"

tenant=00000000-0000-0000-0000-000000000001
docker exec -u root "$radix" mkdir -p "/data/$tenant"
docker cp /tmp/tervory-tank-main.bundle "$radix:/data/$tenant/tervory-tank-main.bundle"
docker exec -u root "$radix" chown agent:agent "/data/$tenant/tervory-tank-main.bundle"

docker exec -e SRC=file:tervory-tank-main.bundle -e REF="tervory-tank main <short-commit>" "$tank" python -c '
import json, os, urllib.request, urllib.error
key = os.environ["TANK_KEY_RADIX"]
body = json.dumps({
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "kind": "scan",
    "input": {
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "source": os.environ["SRC"],
        "ref": os.environ["REF"],
    },
}).encode()
req = urllib.request.Request(
    "http://agent-radix:8000/jobs",
    data=body,
    headers={"Content-Type": "application/json", "X-Tank-Key": key},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as exc:
    print(json.dumps({"http": exc.code}))
    raise SystemExit(1)
print(json.dumps({"id": data.get("id"), "status": data.get("status")}))
'
```

Repeat the copy and the post for rig. Use `SRC=file:tervory-rig-main.bundle` and `REF` `tervory-rig main <short-commit>`. Keep each printed job id.

A `201` body has `id` and `status` `queued`. Any other HTTP code means stop and tell the founder the code only.

## 6. Read the result, then tell the founder

Poll from the same Tank container until `status` is `done` or `failed`. A scan of a whole tree can take several minutes. The room memory limit is 256 MiB; a failure whose `error` is a short message (for example `source is too large`) is safe to forward.

```bash
docker exec -e JOB=<job-id> "$tank" python -c '
import json, os, urllib.request, urllib.error
key = os.environ["TANK_KEY_RADIX"]
job = os.environ["JOB"]
url = "http://agent-radix:8000/jobs/" + job + "?tenant_id=00000000-0000-0000-0000-000000000001"
req = urllib.request.Request(url, headers={"X-Tank-Key": key})
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as exc:
    print(json.dumps({"http": exc.code}))
    raise SystemExit(1)
result = data.get("result") or {}
keep = ("tool", "severity", "file", "line", "rule", "fix", "package", "version", "advisory")
rows = []
for item in result.get("findings") or []:
    if item.get("severity") == "critical":
        rows.append({k: item.get(k) for k in keep if k in item})
out = {
    "id": data.get("id"),
    "status": data.get("status"),
    "error": data.get("error"),
    "ref": result.get("ref"),
    "summary": result.get("summary"),
    "critical": result.get("critical"),
    "deploy_blocked": result.get("deploy_blocked"),
    "leaked": result.get("leaked"),
}
if result.get("leaked") is True:
    out = {"id": data.get("id"), "status": data.get("status"), "leaked": True}
else:
    out["critical_findings"] = rows
print(json.dumps(out))
'
```

When `critical` is greater than 0, or `deploy_blocked` is true, message the founder immediately with that JSON and nothing else. Severity `critical` means the build must not deploy.

When `leaked` is true, message the founder the job id and `leaked: true` only. Do not paste findings, the summary, or the log.

When `status` is `failed`, forward `error` and the job id.

Then remove the bundles from the room and from `/tmp`:

```bash
docker exec -u root "$radix" rm -f \
  "/data/$tenant/tervory-tank-main.bundle" \
  "/data/$tenant/tervory-rig-main.bundle"
rm -f /tmp/tervory-tank-main.bundle /tmp/tervory-rig-main.bundle
```

Findings stay in `agent_radix.findings` for that tenant and scan id. The secret text is not a column.

## 7. What this note does not do

- It does not deploy, scan, or merge.
- It does not change `MAX_SOURCE`, the room memory limit, or the compose file.
- It does not print `TANK_KEY_RADIX`, `COOLIFY_TOKEN`, or any other secret value.
- It does not scan a repo other than those two `main` branches, and it does not follow a link from a finding.
