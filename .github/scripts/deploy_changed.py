"""Deploy only the Coolify apps whose code changed in a push to main.

Runs after CI passes on main. Reads the changed paths between BEFORE and AFTER,
maps them to Coolify app names, looks up each app's uuid by name through the
Coolify API, and queues a deploy. The main app goes first and must finish with
success. The South Africa stack (tervory-tank-za) is next and must finish
before any room is deployed, so a broken main or SA deploy never fans out.
The token comes from COOLIFY_TOKEN and is never printed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

from backup_runtime_scope import verify_main_scope

URL = os.environ["COOLIFY_URL"].rstrip("/")
TOKEN = os.environ["COOLIFY_TOKEN"]
BEFORE = os.environ.get("BEFORE", "")
AFTER = os.environ.get("AFTER", "HEAD")
MAIN_APP = "xnmc0jkz8j9i5jh1jwanbsfv"
SA_APP = "tervory-tank-za"
# Repo variable ZA_OFFLINE=true: the ZA stack is switched off on purpose (box being moved).
# Skip it and every -za room with a notice, and do not fail the run. Unset: today's behaviour.
ZA_OFFLINE = os.environ.get("ZA_OFFLINE", "").strip().lower() == "true"
# The commit at the tip of main when this run started (set by the workflow). Coolify always
# builds the tip of main, so a queued run whose app already finished a deploy of that commit
# would only restart it. Five merges in six minutes (31 Oct) made three queued runs redeploy
# 3f57590c on Boston and ZA again; each ZA restart cut the ZA room's case loads mid-run.
# Empty: unknown, every wanted app deploys as before.
MAIN_HEAD = os.environ.get("MAIN_HEAD", "").strip().lower()

# Paths that rebuild the main stack (Tank, Workspace, LiteLLM, Hermes, SearXNG, site, shared compose).
MAIN_PREFIXES = (
    "tank/", "workspace/", "litellm/", "hermes/", "db/", "searxng/", "tiger/", "site/", "tor/",
    "docker-compose.yml",
    # Backup workers live in the main and ZA stacks (r2-backup, r2-backup-za).
    "docker-compose.za.yml", "jobs/train/backup.py", "jobs/train/r2_archive.py",
    "jobs/train/Dockerfile.backup",
)
# Shared room code: a change here redeploys every room.
ALL_ROOMS_PREFIXES = ("agents/_chassis/", "agents/_template/")


def api(method: str, path: str) -> tuple[int, object]:
    if URL != "https://coolify.tervory.com":
        raise ValueError("COOLIFY_URL must match the fixed https Coolify base")
    req = urllib.request.Request(f"https://coolify.tervory.com/api/v1{path}", method=method,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode() or "null"
            return r.status, json.loads(body)
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode()[:300])


def changed_paths() -> list[str]:
    if not BEFORE or set(BEFORE) == {"0"}:
        rng = [f"{AFTER}~1", AFTER]
    else:
        rng = [BEFORE, AFTER]
    out = subprocess.run(["git", "diff", "--name-only", *rng], capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def wanted(paths: list[str]) -> tuple[bool, set[str], bool]:
    main = any(p.startswith(MAIN_PREFIXES) for p in paths)
    rooms: set[str] = set()
    every_room = any(p.startswith(ALL_ROOMS_PREFIXES) for p in paths)
    for p in paths:
        parts = p.split("/")
        if len(parts) > 2 and parts[0] == "agents" and not parts[1].startswith("_"):
            rooms.add("agent-" + parts[1].replace("_", "-"))
    return main, rooms, every_room


# How long to wait for each Coolify deployment. ZA builds on a slower host: when
# tank/requirements.txt changes, Docker rebuilds the pip layer and downloads the
# models again, and ZA took 19 and 22 minutes (31 Oct, deployments 876 and 882)
# against the old 15-minute wait, so the run failed while ZA was still building.
MAIN_TIMEOUT_S = 1800
ZA_TIMEOUT_S = 2700
ROOM_TIMEOUT_S = 900
POLL_S = 15
# deploy() records the deployment Coolify queued, so wait_for follows that exact
# deployment rather than whichever deployment of the app is newest.
_queued: dict[str, str] = {}


def _rows(body: object) -> list[dict]:
    rows = body.get("deployments", body) if isinstance(body, dict) else body
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def wait_for(uuid: str, name: str, timeout_s: int = ROOM_TIMEOUT_S) -> bool:
    """Wait until the queued deployment ends, then report how it ended.

    A deployment still queued or building when the wait runs out is reported as
    still in progress, with its id, not as a failed deployment.
    """
    started = time.time()
    deadline = started + timeout_s
    deployment = _queued.get(uuid, "")
    status, last_note = "", 0.0
    time.sleep(20)
    while time.time() < deadline:
        if deployment:
            code, body = api("GET", f"/deployments/{deployment}")
            row = body if code == 200 and isinstance(body, dict) else None
        else:
            code, body = api("GET", f"/deployments/applications/{uuid}?take=1")
            rows = _rows(body) if code == 200 else []
            row = rows[0] if rows else None
        if row is not None:
            status = (row.get("status") or "").lower()
            if status in ("finished", "success"):
                print(f"::notice title=deployed::{name} finished after {time.time() - started:.0f}s")
                return True
            if status in ("failed", "cancelled-by-user", "error"):
                print(f"::error title=deploy failed::{name} ended with {status}")
                return False
        if time.time() - last_note >= 120:
            last_note = time.time()
            print(f"{name}: {status or 'no status yet'} after {time.time() - started:.0f}s")
        time.sleep(POLL_S)
    ref = f" (deployment {deployment})" if deployment else ""
    print(f"::error title=deploy timeout::{name} still {status or 'unknown'} after {timeout_s}s{ref}; "
          "it was not cancelled and may still finish in Coolify")
    return False


def last_failed(uuid: str) -> bool:
    """True when the app's most recent Coolify deployment failed, so it is retried on its own."""
    code, body = api("GET", f"/deployments/applications/{uuid}?take=1")
    if code != 200:
        return False
    rows = _rows(body)
    return bool(rows) and (rows[0].get("status") or "").lower() in ("failed", "error")


def already_live(uuid: str, name: str) -> bool:
    """True when the app's latest Coolify deployment finished on MAIN_HEAD, so a deploy would only restart it."""
    if len(MAIN_HEAD) != 40:
        return False
    code, body = api("GET", f"/deployments/applications/{uuid}?take=1")
    if code != 200:
        return False
    rows = _rows(body)
    if not rows:
        return False
    row = rows[0]
    live = (row.get("status") or "").lower() in ("finished", "success") \
        and (row.get("commit") or "").strip().lower() == MAIN_HEAD
    if live:
        print(f"::notice title=already live::{name} already runs {MAIN_HEAD[:8]}; not restarted")
    return live


def deploy(uuid: str, name: str) -> bool:
    code, body = api("POST", f"/deploy?uuid={uuid}&force=false")
    if not 200 <= code < 300:
        print(f"::error title=deploy {name}::HTTP {code} {str(body)[:200]}")
        return False
    queued = [r.get("deployment_uuid") for r in _rows(body) if r.get("deployment_uuid")]
    if queued:
        _queued[uuid] = queued[0]
    print(f"::notice title=queued::{name}" + (f" (deployment {queued[0]})" if queued else ""))
    return True


def main() -> int:
    # GitHub stamps each log line when it arrives; unbuffered lines keep real times.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    paths = changed_paths()
    want_main, rooms, every_room = wanted(paths)
    code, apps = api("GET", "/applications")
    if code != 200 or not isinstance(apps, list):
        print(f"::error title=coolify::could not list applications (HTTP {code})")
        return 1
    by_name = {a.get("name", ""): a.get("uuid") for a in apps}
    room_apps = {n: u for n, u in by_name.items() if n.startswith("agent-") and n != "agent-template"}
    if every_room:
        targets = dict(room_apps)
    else:
        # A room folder deploys its app and any regional copy (e.g. agent-zenas-za).
        targets = {n: u for n, u in room_apps.items() if any(n == r or n.startswith(r + "-") for r in rooms)}
    # An app whose last deployment failed is retried by itself; nothing else is redeployed for it.
    for name, uuid in sorted(room_apps.items()):
        if name not in targets and last_failed(uuid):
            print(f"::notice title=retry::{name} failed last time and is retried")
            targets[name] = uuid
    if not want_main and last_failed(MAIN_APP):
        print("::notice title=retry::main failed last time and is retried")
        want_main = True
    # tervory-tank-za is deployed with main; if its last deployment failed it is
    # retried on its own, as main and the rooms are.
    za_retry = not want_main and not ZA_OFFLINE and bool(by_name.get(SA_APP)) and last_failed(by_name[SA_APP])
    if za_retry:
        print(f"::notice title=retry::{SA_APP} failed last time and is retried")
    if not want_main and not za_retry and not targets:
        print("::notice title=nothing to deploy::no app code changed")
        return 0
    if want_main:
        # Coolify injects the app's runtime .env into every Compose service.
        # Refuse drift before replacing the live stack, rather than losing backups.
        if not verify_main_scope(api):
            return 1
        if already_live(MAIN_APP, "main"):
            pass
        elif not deploy(MAIN_APP, "main") or not wait_for(MAIN_APP, "main", MAIN_TIMEOUT_S):
            print("::error title=stopped::main did not deploy; rooms were not touched")
            return 1
    za_ok = True
    if ZA_OFFLINE:
        skipped = sorted(n for n in targets if n.endswith("-za"))
        targets = {n: u for n, u in targets.items() if not n.endswith("-za")}
        print("::notice title=za offline::ZA_OFFLINE is set: tervory-tank-za"
              + (" and " + ", ".join(skipped) if skipped else "") + " skipped on purpose")
    elif want_main or za_retry:
        za_uuid = by_name.get(SA_APP)
        if za_uuid and already_live(za_uuid, SA_APP):
            pass
        elif not za_uuid or not deploy(za_uuid, SA_APP) or not wait_for(za_uuid, SA_APP, ZA_TIMEOUT_S):
            # The ZA box failing (for example a power outage there) must not hold back
            # Boston's rooms. ZA rooms wait until tervory-tank-za deploys again.
            za_ok = False
            print("::error title=za not deployed::tervory-tank-za did not finish deploying in this run; "
                  "ZA rooms skipped, Boston rooms continue")
            targets = {n: u for n, u in targets.items() if not n.endswith("-za")}
    ok = za_ok
    # One room at a time: deploy, then wait until it is healthy before the next.
    # Starting every room at once took every product page down together (28 Oct, #403).
    for name, uuid in sorted(targets.items()):
        if already_live(uuid, name):
            continue
        ok = (deploy(uuid, name) and wait_for(uuid, name, ROOM_TIMEOUT_S)) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
