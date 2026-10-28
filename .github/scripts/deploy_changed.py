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

URL = os.environ["COOLIFY_URL"].rstrip("/")
TOKEN = os.environ["COOLIFY_TOKEN"]
BEFORE = os.environ.get("BEFORE", "")
AFTER = os.environ.get("AFTER", "HEAD")
MAIN_APP = "xnmc0jkz8j9i5jh1jwanbsfv"
SA_APP = "tervory-tank-za"
# Repo variable ZA_OFFLINE=true: the ZA stack is switched off on purpose (box being moved).
# Skip it and every -za room with a notice, and do not fail the run. Unset: today's behaviour.
ZA_OFFLINE = os.environ.get("ZA_OFFLINE", "").strip().lower() == "true"

# Paths that rebuild the main stack (Tank, Workspace, LiteLLM, Hermes, SearXNG, site, shared compose).
MAIN_PREFIXES = (
    "tank/", "workspace/", "litellm/", "hermes/", "db/", "searxng/", "tiger/", "site/", "tor/",
    "docker-compose.yml",
)
# Shared room code: a change here redeploys every room.
ALL_ROOMS_PREFIXES = ("agents/_chassis/", "agents/_template/")


def api(method: str, path: str) -> tuple[int, object]:
    req = urllib.request.Request(f"{URL}/api/v1{path}", method=method,
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


def wait_for(uuid: str, name: str, timeout_s: int = 900) -> bool:
    """Wait until the app has no deployment queued or in progress, then report its last status."""
    deadline = time.time() + timeout_s
    time.sleep(20)
    while time.time() < deadline:
        code, body = api("GET", f"/deployments/applications/{uuid}?take=1")
        if code == 200:
            rows = body.get("deployments", body) if isinstance(body, dict) else body
            if rows:
                status = (rows[0].get("status") or "").lower()
                if status in ("finished", "success"):
                    print(f"::notice title=deployed::{name} finished")
                    return True
                if status in ("failed", "cancelled-by-user", "error"):
                    print(f"::error title=deploy failed::{name} ended with {status}")
                    return False
        time.sleep(15)
    print(f"::error title=deploy timeout::{name} did not finish in {timeout_s}s")
    return False


def deploy(uuid: str, name: str) -> bool:
    code, body = api("POST", f"/deploy?uuid={uuid}&force=false")
    if not 200 <= code < 300:
        print(f"::error title=deploy {name}::HTTP {code} {str(body)[:200]}")
        return False
    print(f"::notice title=queued::{name}")
    return True


def main() -> int:
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
    if not want_main and not targets:
        print("::notice title=nothing to deploy::no app code changed")
        return 0
    if want_main:
        if not deploy(MAIN_APP, "main") or not wait_for(MAIN_APP, "main"):
            print("::error title=stopped::main did not deploy; rooms were not touched")
            return 1
    za_ok = True
    if ZA_OFFLINE:
        skipped = sorted(n for n in targets if n.endswith("-za"))
        targets = {n: u for n, u in targets.items() if not n.endswith("-za")}
        print("::notice title=za offline::ZA_OFFLINE is set: tervory-tank-za"
              + (" and " + ", ".join(skipped) if skipped else "") + " skipped on purpose")
    elif want_main:
        za_uuid = by_name.get(SA_APP)
        if not za_uuid or not deploy(za_uuid, SA_APP) or not wait_for(za_uuid, SA_APP):
            # The ZA box failing (for example a power outage there) must not hold back
            # Boston's rooms. ZA rooms wait until tervory-tank-za deploys again.
            za_ok = False
            print("::error title=za not deployed::tervory-tank-za did not deploy; ZA rooms skipped, Boston rooms continue")
            targets = {n: u for n, u in targets.items() if not n.endswith("-za")}
    ok = za_ok
    # One room at a time: deploy, then wait until it is healthy before the next.
    # Starting every room at once took every product page down together (28 Oct, #403).
    for name, uuid in sorted(targets.items()):
        ok = (deploy(uuid, name) and wait_for(uuid, name)) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
