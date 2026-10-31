"""coolify-ops op=zenas-renormalise / zenas-renormalise-report.

Runs `python -m agents.zenas.pool.renormalise` inside the deployed ZA Zenas room
container, the same way the nightly pool job runs there: as a Coolify scheduled
task on that application (the container comes from the existing
zenas-pool-nightly task). Nothing is exec'd from a laptop or box; the Coolify
token stays in this job.

- Dry run unless the workflow input apply is exactly "true". Only then is
  --apply added to the command.
- Refuses to start while an earlier renormalise execution is still running.
- The task is kept disabled with a yearly frequency, so it never runs on a
  schedule; it runs only when this op queues it.
- Prints only a fixed projection of the job's JSON report (counts, resume id,
  changed rows' ids and suspect-space counts). The raw execution output and any
  API body are never printed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import shlex
import sys
import time
import urllib.error
import urllib.request

HOST = "https://coolify.tervory.com"
# region -> (application uuid, application name, nightly task uuid). Only ZA has the job.
TARGETS = {"za": ("rslmzhfmq5tf9ipx385gmu6p", "agent-zenas-za", "m6ggpxv2iegsecpkakqzlwxd")}
NIGHTLY_NAME = "zenas-pool-nightly"
TASK_NAME = "zenas-za-renormalise"
FREQUENCY = "0 0 1 1 *"  # never reached: the task stays disabled
TASK_TIMEOUT = 36000  # Coolify's maximum; resume with --after if a run is cut
BATCH_SIZE = 25
WAIT_SECONDS = int(os.environ.get("RENORMALISE_WAIT_SECONDS", "450") or 450)
POLL_SECONDS = 15

_UUID = re.compile(r"^[a-z0-9]{8,40}$")
_SOURCE = re.compile(r"^[a-z0-9-]{1,40}$")
_AFTER = re.compile(r"^[A-Za-z0-9:._ ()\[\]/-]{1,200}$")
_CONTAINER = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_COUNT_KEY = re.compile(r"^[a-z :]{1,40}$")


class OpError(Exception):
    """A fixed message that is safe to print."""


def allowed_paths(app: str, task: str = "") -> set[str]:
    base = f"/applications/{app}"
    paths = {base, base + "/scheduled-tasks"}
    if task:
        paths |= {f"{base}/scheduled-tasks/{task}", f"{base}/scheduled-tasks/{task}/executions",
                  f"{base}/scheduled-tasks/{task}/execute"}
    return paths


def api(method: str, path: str, body: dict | None = None):
    """One Coolify call. Only fixed ZA-room paths; https host only; no redirects."""
    if os.environ.get("COOLIFY_URL", "").rstrip("/") != HOST:
        raise OpError("COOLIFY_URL must be " + HOST)
    parts = path.split("/")
    app = parts[2] if len(parts) > 2 else ""
    task = parts[4] if len(parts) > 4 else ""
    if app not in {t[0] for t in TARGETS.values()} or (task and not _UUID.match(task)) or path not in allowed_paths(app, task):
        raise OpError("path not allowed")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        HOST + "/api/v1" + path, method=method, data=data,
        headers={"Authorization": "Bearer " + os.environ["COOLIFY_TOKEN"], "Accept": "application/json",
                 **({"Content-Type": "application/json"} if data is not None else {})},
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def inputs(env=os.environ) -> dict:
    region = env.get("REGION", "").strip()
    if region not in TARGETS:
        raise OpError("region must be za: the re-normalise job exists only for ZA")
    apply_raw = env.get("APPLY", "").strip().lower()
    if apply_raw not in {"", "false", "true"}:
        raise OpError("apply must be true or false")
    sources = [s.strip() for s in env.get("SOURCE", "").split(",") if s.strip()]
    if any(not _SOURCE.match(s) for s in sources):
        raise OpError("source must be comma-separated source ids")
    limit_raw = env.get("LIMIT", "").strip()
    if limit_raw and (not limit_raw.isdigit() or not 1 <= int(limit_raw) <= 1_000_000):
        raise OpError("limit must be a whole number from 1")
    after = env.get("AFTER", "").strip()
    if after and not _AFTER.match(after):
        raise OpError("after must be a document_id from an earlier report")
    return {"region": region, "apply": apply_raw == "true", "sources": sources,
            "limit": int(limit_raw) if limit_raw else None, "after": after}


def command(spec: dict) -> str:
    """The exact command the room runs. Every value is validated, then shell-quoted."""
    argv = ["python", "-m", "agents.zenas.pool.renormalise", "--batch-size", str(BATCH_SIZE)]
    for source in spec["sources"]:
        argv += ["--source", source]
    if spec["limit"] is not None:
        argv += ["--limit", str(spec["limit"])]
    if spec["after"]:
        argv += ["--after", spec["after"]]
    argv.append("--apply" if spec["apply"] else "--dry-run")
    return " ".join(shlex.quote(part) for part in argv)


def _ok(code: int) -> bool:
    return 200 <= code < 300


def _room(call, region: str) -> tuple[str, str, str]:
    app, name, nightly = TARGETS[region]
    code, resource = call("GET", f"/applications/{app}")
    if code != 200 or not isinstance(resource, dict) or resource.get("uuid") != app or resource.get("name") != name:
        raise OpError("the ZA Zenas room application could not be verified")
    code, tasks = call("GET", f"/applications/{app}/scheduled-tasks")
    if code != 200 or not isinstance(tasks, list) or any(not isinstance(row, dict) for row in tasks):
        raise OpError("the room's scheduled tasks could not be read")
    night = [row for row in tasks if row.get("uuid") == nightly and row.get("name") == NIGHTLY_NAME]
    if len(night) != 1:
        raise OpError("the nightly task that names the room container was not found")
    container = night[0].get("container")
    if container is not None and not (isinstance(container, str) and _CONTAINER.match(container)):
        raise OpError("the nightly task's container is not a plain name")
    mine = [row for row in tasks if row.get("name") == TASK_NAME]
    if len(mine) > 1:
        raise OpError("more than one renormalise task exists; remove the extra one in Coolify")
    task = str(mine[0].get("uuid") or "") if mine else ""
    if task and not _UUID.match(task):
        raise OpError("the renormalise task uuid is not plain")
    return app, task, container or ""


def _executions(call, app: str, task: str) -> list[dict]:
    code, rows = call("GET", f"/applications/{app}/scheduled-tasks/{task}/executions")
    if code != 200 or not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise OpError("the renormalise executions could not be read")
    return rows


def _key(row: dict) -> str:
    return str(row.get("id") or row.get("uuid") or row.get("created_at") or row.get("started_at") or "")


def _when(row: dict) -> datetime:
    for field in ("started_at", "created_at"):
        value = row.get(field)
        if isinstance(value, str) and value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def report_from_output(output) -> dict | None:
    """The job prints its report as indented JSON last. Return a fixed projection or None."""
    if not isinstance(output, str):
        return None
    lines = output.splitlines()
    for end in range(len(lines) - 1, -1, -1):
        if lines[end].rstrip() != "}":
            continue
        for start in range(end, -1, -1):
            if lines[start].strip() != "{":
                continue
            try:
                data = json.loads("\n".join(lines[start : end + 1]))
            except ValueError:
                continue
            if isinstance(data, dict) and isinstance(data.get("counts"), dict):
                return project(data)
        break
    return None


def project(data: dict) -> dict:
    counts = {str(k): int(v) for k, v in data["counts"].items()
              if isinstance(k, str) and _COUNT_KEY.match(k) and isinstance(v, int) and not isinstance(v, bool)}
    changed = []
    for row in data.get("changed") or []:
        if not isinstance(row, dict) or not _AFTER.match(str(row.get("document_id") or "")):
            continue
        item = {"document_id": str(row["document_id"])}
        for field in ("suspect_spaces_before", "suspect_spaces_after"):
            value = row.get(field)
            item[field] = value if isinstance(value, int) and not isinstance(value, bool) else None
        changed.append(item)
    last = str(data.get("last_document_id") or "")
    return {"dry_run": data.get("dry_run") is True, "counts": counts, "changed": changed[:50],
            "last_document_id": last if _AFTER.match(last) else ""}


def summary(row: dict | None) -> dict:
    if row is None:
        return {"execution": None}
    status = row.get("status") if row.get("status") in ("success", "failed", "running") else "unknown"
    out = {"execution": {"status": status, "started_at": row.get("started_at") if isinstance(row.get("started_at"), str) else None,
                         "finished_at": row.get("finished_at") if isinstance(row.get("finished_at"), str) else None}}
    if status != "running":
        out["report"] = report_from_output(row.get("message"))
    return out


def run(call=api, env=os.environ, sleep=time.sleep, clock=time.monotonic) -> dict:
    spec = inputs(env)
    app, task, container = _room(call, spec["region"])
    body = {"name": TASK_NAME, "command": command(spec), "frequency": FREQUENCY,
            "container": container or None, "timeout": TASK_TIMEOUT, "enabled": False}
    seen: set[str] = set()
    if task:
        rows = _executions(call, app, task)
        if any(row.get("status") == "running" for row in rows):
            raise OpError("a renormalise run is still running; read it with op=zenas-renormalise-report")
        seen = {_key(row) for row in rows}
        code, _ = call("PATCH", f"/applications/{app}/scheduled-tasks/{task}", body)
        if not _ok(code):
            raise OpError(f"updating the renormalise task failed (HTTP {code})")
    else:
        code, created = call("POST", f"/applications/{app}/scheduled-tasks", body)
        task = str((created or {}).get("uuid") or "") if isinstance(created, dict) else ""
        if not _ok(code) or not _UUID.match(task):
            raise OpError(f"creating the renormalise task failed (HTTP {code})")
    code, _ = call("POST", f"/applications/{app}/scheduled-tasks/{task}/execute")
    if not _ok(code):
        raise OpError(f"queuing the renormalise run failed (HTTP {code}); this Coolify may not support execute")
    deadline = clock() + WAIT_SECONDS
    latest = None
    while True:
        new = [row for row in _executions(call, app, task) if _key(row) not in seen]
        latest = max(new, key=_when) if new else None
        if latest is not None and latest.get("status") in ("success", "failed"):
            break
        if clock() >= deadline:
            break
        sleep(POLL_SECONDS)
    result = {"op": "zenas-renormalise", "region": spec["region"], "apply": spec["apply"],
              "command": command(spec), "task_uuid": task, **summary(latest)}
    if latest is None or latest.get("status") == "running":
        result["next"] = "still running: read the result later with op=zenas-renormalise-report"
    return result


def report(call=api, env=os.environ) -> dict:
    region = env.get("REGION", "").strip()
    if region not in TARGETS:
        raise OpError("region must be za: the re-normalise job exists only for ZA")
    app, task, _ = _room(call, region)
    if not task:
        return {"op": "zenas-renormalise-report", "region": region, "task_uuid": "", "execution": None}
    rows = _executions(call, app, task)
    latest = max(rows, key=_when) if rows else None
    return {"op": "zenas-renormalise-report", "region": region, "task_uuid": task, **summary(latest)}


def main(argv=None, call=api) -> int:
    mode = (argv or sys.argv[1:] or [""])[0]
    try:
        if mode == "run":
            result = run(call)
        elif mode == "report":
            result = report(call)
        else:
            raise OpError("mode must be run or report")
    except OpError as exc:
        print(f"::error title=zenas-renormalise::{exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - never print bodies or messages
        print(f"::error title=zenas-renormalise::failed ({type(exc).__name__})")
        return 1
    print(json.dumps(result, sort_keys=True))
    execution = result.get("execution") or {}
    print(f"::notice title=zenas-renormalise::{json.dumps({k: result.get(k) for k in ('apply', 'task_uuid')} | {'status': execution.get('status'), 'counts': (result.get('report') or {}).get('counts')}, sort_keys=True)}")
    return 1 if execution.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
