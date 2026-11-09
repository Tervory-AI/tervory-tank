#!/usr/bin/env python3
"""Images built in CI, merges batched, a rollback record (founder, 9 Nov).

Before: every merge to main asked Coolify to rebuild each changed app on Boston (and ZA),
so the box built while it served, and the app was down while the new containers started.
41 deploy runs started on 8 Nov.

Now, for a push to main:
  1. settle: a run waits until main has been quiet for SETTLE_S. A run whose commit is no
     longer the tip of main cancels itself, so a burst of merges becomes one deploy of the
     latest commit. A cancelled run is skipped when the next run looks for the last deployed
     commit, so nothing it carried is lost. MAX_HOLD_S stops a steady stream of merges from
     holding a deploy back for ever.
  2. plan: the changed apps since the last good deploy of EACH app (the deploy record), plus
     everything since the previous deploy run, as today.
  3. build: each changed app's images are built on a GitHub runner and pushed to GHCR as
     <REGISTRY>/<app>-<service>:<commit>. Nothing is built on the server.
  4. promote (deploy_changed.py, just before each Coolify deploy): <commit> becomes :live and
     the old :live becomes :previous; the record keeps both digests for every service.
     Coolify only pulls :live and restarts. A failed deploy puts :live back.
  5. rollback (coolify-ops op=rollback): :live goes back to the recorded previous digests
     (or to any recorded commit) and the app is redeployed, in one step.

Commands (no Coolify call in any of them):
  deploy_images.py dry-run --from A --to B      what a deploy of B after A would build and deploy
  deploy_images.py history --runs runs.json     deploys per day before, and with the new rules
  deploy_images.py plan --out plan.json         (CI) the build list for this run
  deploy_images.py build --compose C --service S --sha X   (CI) build and push one image
  deploy_images.py settle                        (CI) wait, deploy, or cancel this run
  deploy_images.py sync-compose                  add the missing image: lines to compose files
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "ghcr.io/tervory-ai/tervory-tank"
LIVE, PREVIOUS = "live", "previous"
SHA = re.compile(r"[0-9a-f]{40}")
RECORD_NAME = "deploy-record"
# Quiet time before a deploy starts, and the longest a merge waits for a quiet gap.
# Chosen from the 2-9 Nov history (deploy_images.py history): see the pull request.
SETTLE_S = 1200
MAX_HOLD_S = 3600

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
MAIN_COMPOSES = ("docker-compose.yml", "docker-compose.za.yml")


def wanted(paths: Iterable[str]) -> tuple[bool, set[str], bool]:
    """(main changed, room app names changed, every room changed) for these paths."""
    paths = list(paths)
    main = any(p.startswith(MAIN_PREFIXES) for p in paths)
    rooms: set[str] = set()
    every_room = any(p.startswith(ALL_ROOMS_PREFIXES) for p in paths)
    for p in paths:
        parts = p.split("/")
        if len(parts) > 2 and parts[0] == "agents" and not parts[1].startswith("_"):
            rooms.add("agent-" + parts[1].replace("_", "-"))
    return main, rooms, every_room


# ---------------------------------------------------------------- compose files and images

def deployable_composes(root: Path = ROOT) -> list[str]:
    """Every compose file a Coolify app deploys: the two main stacks and each room's files."""
    rooms = sorted(str(p.relative_to(root)) for p in root.glob("agents/*/docker-compose*.yml")
                   if not p.parent.name.startswith("_"))
    return [c for c in MAIN_COMPOSES if (root / c).exists()] + rooms


def compose_for_app(app: dict) -> str:
    """The repo path of the compose file a Coolify application record deploys."""
    base = (app.get("base_directory") or "/").strip("/")
    location = (app.get("docker_compose_location") or "/docker-compose.yml").lstrip("/")
    path = str(PurePosixPath(base) / location) if base else location
    if ".." in PurePosixPath(path).parts:
        raise ValueError("compose path leaves the repository")
    return path


def compose_key(compose: str) -> str:
    """docker-compose.yml -> main, docker-compose.za.yml -> za,
    agents/zenas/docker-compose.yml -> zenas, agents/zenas/docker-compose.za.yml -> zenas-za."""
    path = PurePosixPath(compose)
    match = re.fullmatch(r"docker-compose(?:\.([a-z0-9-]+))?\.yml", path.name)
    if not match:
        raise ValueError(f"not a compose file name: {compose}")
    if path.parent == PurePosixPath("."):
        base = "main"
        suffix = match[1]
        return suffix if suffix else base
    if len(path.parts) != 3 or path.parts[0] != "agents":
        raise ValueError(f"compose file outside the deployed places: {compose}")
    base = path.parts[1].replace("_", "-")
    return base + (f"-{match[1]}" if match[1] else "")


def image_repo(compose: str, service: str) -> str:
    return f"{REGISTRY}/{compose_key(compose)}-{service.lower()}"


def compose_owns(compose: str, path: str) -> bool:
    """True when a change to this path is a change to the app that deploys this compose file."""
    if compose in MAIN_COMPOSES:
        return path.startswith(MAIN_PREFIXES)
    folder = PurePosixPath(compose).parts[1]
    return path.startswith(ALL_ROOMS_PREFIXES) or (path.startswith(f"agents/{folder}/") and len(path.split("/")) > 2)


@dataclass
class BuildSpec:
    compose: str
    service: str
    context: str
    dockerfile: str
    args: dict[str, str] = field(default_factory=dict)
    target: str = ""
    contexts: dict[str, str] = field(default_factory=dict)

    @property
    def repo(self) -> str:
        return image_repo(self.compose, self.service)


def _norm(base: PurePosixPath, rel: str) -> str:
    parts: list[str] = []
    for part in (base / rel).parts:
        if part == "..":
            if not parts:
                raise ValueError(f"build path leaves the repository: {rel}")
            parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts) or "."


_DEFAULT = re.compile(r"^\$\{([A-Z0-9_]+):?-([^}]*)\}$")


def _arg_value(name: str, value: object, sha: str) -> str:
    """Build args take their compose default; GIT_SHA is the commit being built."""
    if name == "GIT_SHA":
        return sha
    text = "" if value is None else str(value)
    match = _DEFAULT.match(text)
    if match:
        return match[2]
    if "${" in text:
        raise ValueError(f"build arg {name} needs a value at build time: {text}")
    return text


def _yaml(text: str) -> dict:
    import yaml  # only the plan, build and sync steps read compose files

    return yaml.safe_load(text) or {}


def built_services(compose: str, root: Path = ROOT, sha: str = "") -> list[BuildSpec]:
    data = _yaml((root / compose).read_text(encoding="utf-8"))
    base = PurePosixPath(compose).parent
    specs = []
    for name, service in (data.get("services") or {}).items():
        build = (service or {}).get("build")
        if build is None:
            continue
        if isinstance(build, str):
            build = {"context": build}
        context = _norm(base, build.get("context", "."))
        dockerfile = _norm(PurePosixPath(context), build.get("dockerfile", "Dockerfile"))
        args = build.get("args") or {}
        if isinstance(args, list):
            args = dict(item.split("=", 1) if "=" in item else (item, None) for item in args)
        specs.append(BuildSpec(
            compose=compose, service=name, context=context, dockerfile=dockerfile,
            args={k: _arg_value(k, v, sha) for k, v in args.items()},
            target=str(build.get("target") or ""),
            contexts={k: _norm(base, v) for k, v in (build.get("additional_contexts") or {}).items()},
        ))
    return specs


def missing_image_lines(compose: str, root: Path = ROOT) -> list[str]:
    """Built services whose image: is not their GHCR :live name (Coolify would have nothing to pull)."""
    data = _yaml((root / compose).read_text(encoding="utf-8"))
    services = data.get("services") or {}
    return [s.service for s in built_services(compose, root)
            if (services[s.service] or {}).get("image") != f"{s.repo}:{LIVE}"]


def add_image_lines(compose: str, root: Path = ROOT) -> str:
    """The compose text with `image: <repo>:live` just above each built service's build:.

    Only lines are added (and an old image: of a built service replaced); comments and
    every other line stay as they are.
    """
    want = {s.service: f"{s.repo}:{LIVE}" for s in built_services(compose, root)}
    out: list[str] = []
    in_services, service_indent, prop_indent, service = False, None, None, None
    for line in (root / compose).read_text(encoding="utf-8").splitlines(keepends=True):
        body = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if body and not body.startswith("#") and indent == 0:
            in_services, service_indent, prop_indent, service = body == "services:", None, None, None
        elif in_services and body and not body.startswith("#"):
            if service_indent is None:
                service_indent = indent
            if indent == service_indent:
                service, prop_indent = body.split(":", 1)[0].strip("'\""), None
            elif service is not None:
                if prop_indent is None:
                    prop_indent = indent
                if indent == prop_indent and service in want:
                    key = body.split(":", 1)[0]
                    if key == "image":
                        continue
                    if key == "build":
                        out.append(" " * indent + f"image: {want[service]}\n")
        out.append(line)
    return "".join(out)


# ---------------------------------------------------------------- changed apps

def git_paths(before: str, after: str, root: Path = ROOT) -> list[str]:
    rng = [f"{after}~1", after] if not before or set(before) == {"0"} else [before, after]
    out = subprocess.run(["git", "diff", "--name-only", *rng], cwd=root, capture_output=True,
                         text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def has_commit(sha: str, root: Path = ROOT) -> bool:
    return bool(SHA.fullmatch(sha or "")) and subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root, capture_output=True).returncode == 0


def plan(before: str, after: str, record: dict, *, diff: Callable[[str, str], list[str]],
         known: Callable[[str], bool], composes: list[str],
         specs: Callable[[str], list[BuildSpec]]) -> dict:
    """What this run builds and deploys.

    paths: everything since the previous deploy run (today's rule) plus, for each app the
    record knows, the paths that app owns since its own last good deploy. An app whose
    recorded commit is not in this clone counts as changed, so nothing is lost.
    """
    paths = set(diff(before, after))
    for compose in composes:
        last = (record.get("apps", {}).get(compose_key(compose)) or {}).get("live", {}).get("sha", "")
        if not last or last == after:
            continue
        if known(last):
            paths.update(p for p in diff(last, after) if compose_owns(compose, p))
        else:
            paths.add(compose)
    build = [c for c in composes if any(compose_owns(c, p) for p in paths)]
    images = [{"compose": s.compose, "service": s.service, "repo": s.repo}
              for c in build for s in specs(c)]
    return {"before": before, "after": after, "paths": sorted(paths), "build": build, "images": images}


def deploy_names(paths: Iterable[str], room_folders: Iterable[str], za_rooms: Iterable[str] = ()) -> list[str]:
    """Coolify app names a deploy of these paths would touch (main first, as deploy_changed.py does)."""
    main, rooms, every = wanted(paths)
    all_rooms = {"agent-" + f.replace("_", "-") for f in room_folders}
    targets = set(all_rooms) if every else rooms & all_rooms
    targets |= {r for r in za_rooms if r.removesuffix("-za") in targets}
    return (["main", "tervory-tank-za"] if main else []) + sorted(targets)


def repo_rooms(root: Path = ROOT) -> tuple[list[str], list[str]]:
    folders = sorted(p.name for p in (root / "agents").iterdir()
                     if p.is_dir() and not p.name.startswith("_") and (p / "docker-compose.yml").exists())
    za = ["agent-" + f.replace("_", "-") + "-za" for f in folders
          if (root / "agents" / f / "docker-compose.za.yml").exists()]
    return folders, za


# ---------------------------------------------------------------- settle window

def settle_decision(*, after: str, head: str, head_at: float, oldest_at: float, now: float,
                    settle_s: int = SETTLE_S, max_hold_s: int = MAX_HOLD_S) -> str:
    """deploy | wait | superseded.

    superseded: a newer merge is the tip of main; its own run (queued behind this one)
    deploys everything, this one included. deploy: main has been quiet for settle_s, or the
    oldest merge not yet deployed has waited max_hold_s. Unknown head: deploy (today's rule).
    """
    if not SHA.fullmatch(head or ""):
        return "deploy"
    if head != after:
        if oldest_at and now - oldest_at >= max_hold_s:
            return "deploy"
        return "superseded"
    if now - head_at >= settle_s:
        return "deploy"
    if oldest_at and now - oldest_at >= max_hold_s:
        return "deploy"
    return "wait"


@dataclass
class Merge:
    at: datetime
    sha: str
    apps: frozenset[str]


def simulate(merges: list[Merge], *, settle_s: int, max_hold_s: int,
             cost_s: Callable[[frozenset[str]], float]) -> list[tuple[datetime, frozenset[str]]]:
    """Deploys the settle rule would start for these merges (one Coolify queue, as today).

    A deploy starts when main has been quiet for settle_s (or the oldest pending merge has
    waited max_hold_s) and no deploy is running; it takes cost_s(apps); it deploys the union
    of the apps of every merge since the last deploy.
    """
    merges = sorted(merges, key=lambda m: m.at)
    deploys: list[tuple[datetime, frozenset[str]]] = []
    busy_until = datetime.min.replace(tzinfo=timezone.utc)
    pending: list[Merge] = []
    i = 0
    while i < len(merges) or pending:
        if not pending:
            pending.append(merges[i])
            i += 1
            continue
        start = max(busy_until, min(pending[-1].at + timedelta(seconds=settle_s),
                                    pending[0].at + timedelta(seconds=max_hold_s)))
        if i < len(merges) and merges[i].at < start:
            pending.append(merges[i])
            i += 1
            continue
        apps = frozenset().union(*(m.apps for m in pending))
        pending = []
        if apps:
            deploys.append((start, apps))
            busy_until = start + timedelta(seconds=cost_s(apps))
    return deploys


# ---------------------------------------------------------------- registry and record

class Registry:
    """GHCR through docker buildx imagetools (the runner is logged in with GITHUB_TOKEN)."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["docker", "buildx", "imagetools", *args], capture_output=True, text=True)

    def digest(self, ref: str) -> str:
        out = self._run("inspect", ref)
        if out.returncode != 0:
            return ""
        found = re.search(r"^Digest:\s*(sha256:[0-9a-f]{64})\s*$", out.stdout, re.M)
        return found[1] if found else ""

    def tag(self, source: str, target: str) -> None:
        out = self._run("create", "--tag", target, source)
        if out.returncode != 0:
            raise RuntimeError(f"could not tag {target}: {out.stderr.strip()[:300]}")


class MissingImage(RuntimeError):
    pass


def promote(compose: str, sha: str, registry, record: dict, *,
            specs: Callable[[str], list[BuildSpec]] = built_services) -> dict:
    """<sha> becomes :live for every image of this app; the old :live is kept as :previous.

    Every image is checked before any tag moves, so an app never runs half old, half new.
    Returns the app's record entry (also written into record).
    """
    services = specs(compose)
    new = {s.service: registry.digest(f"{s.repo}:{sha}") for s in services}
    missing = sorted(name for name, digest in new.items() if not digest)
    if missing:
        raise MissingImage(f"{compose_key(compose)}: no image for {sha[:8]}: {', '.join(missing)}")
    old = {s.service: registry.digest(f"{s.repo}:{LIVE}") for s in services}
    for s in services:
        if old[s.service] and old[s.service] != new[s.service]:
            registry.tag(f"{s.repo}@{old[s.service]}", f"{s.repo}:{PREVIOUS}")
        registry.tag(f"{s.repo}:{sha}", f"{s.repo}:{LIVE}")
    apps = record.setdefault("apps", {})
    entry = apps.get(compose_key(compose)) or {}
    if any(old.values()) and old != new:
        # What was really live before this deploy; its commit is known when the record matches.
        recorded = entry.get("live") or {}
        previous = {"sha": recorded.get("sha", "") if recorded.get("images") == old else "",
                    "images": {k: v for k, v in old.items() if v}}
    else:
        previous = entry.get("previous") or {}
    entry = {"compose": compose, "live": {"sha": sha, "images": new}, "previous": previous or {},
             "state": "promoted", "at": _now_iso()}
    apps[compose_key(compose)] = entry
    return entry


def restore(compose: str, registry, record: dict) -> bool:
    """After a failed deploy, :live goes back to the recorded previous digests. False: nothing to go back to."""
    entry = (record.get("apps") or {}).get(compose_key(compose)) or {}
    previous = entry.get("previous") or {}
    images = previous.get("images") or {}
    if not images:
        return False
    for service, digest in sorted(images.items()):
        repo = image_repo(compose, service)
        registry.tag(f"{repo}@{digest}", f"{repo}:{LIVE}")
    entry["failed"] = entry.get("live")
    entry["live"], entry["state"], entry["at"] = previous, "restored", _now_iso()
    return True


def rollback(compose: str, registry, record: dict, to: str = "", *,
             specs: Callable[[str], list[BuildSpec]] = built_services) -> dict:
    """One step back: :live becomes the recorded previous digests (or commit `to`); the
    current :live becomes :previous, so a second rollback goes forward again."""
    entry = (record.get("apps") or {}).get(compose_key(compose)) or {}
    current = entry.get("live") or {}
    if to:
        if not SHA.fullmatch(to):
            raise ValueError("rollback target must be a full 40-character commit")
        target = {"sha": to, "images": {}}
        for s in specs(compose):
            digest = registry.digest(f"{s.repo}:{to}")
            if not digest:
                raise MissingImage(f"{compose_key(compose)}: no {s.service} image for {to[:8]}")
            target["images"][s.service] = digest
    else:
        target = entry.get("previous") or {}
        if not target.get("images"):
            raise MissingImage(f"{compose_key(compose)}: the record has no previous image to go back to")
    for service, digest in sorted(target["images"].items()):
        repo = image_repo(compose, service)
        if (current.get("images") or {}).get(service):
            registry.tag(f"{repo}@{current['images'][service]}", f"{repo}:{PREVIOUS}")
        registry.tag(f"{repo}@{digest}", f"{repo}:{LIVE}")
    entry = {"compose": compose, "live": target, "previous": current, "state": "rolled-back", "at": _now_iso()}
    record.setdefault("apps", {})[compose_key(compose)] = entry
    return entry


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_record(repo: str, token: str, out_dir: Path) -> dict:
    """The deploy record of the last run that wrote one (an Actions artifact). {} when none."""
    def get(url: str, accept: str = "application/vnd.github+json") -> bytes:
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": accept})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(50_000_001)
    try:
        listing = json.loads(get(f"https://api.github.com/repos/{repo}/actions/artifacts"
                                 f"?name={RECORD_NAME}&per_page=20"))
        rows = [a for a in listing.get("artifacts", []) if not a.get("expired")
                and (a.get("workflow_run") or {}).get("head_branch") == "main"]
        if not rows:
            return {}
        rows.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        import io
        import zipfile
        data = get(rows[0]["archive_download_url"])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            record = json.loads(archive.read("deploy-record.json"))
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "deploy-record.json").write_text(json.dumps(record, indent=2, sort_keys=True))
        return record if isinstance(record, dict) else {}
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        print(f"::warning title=deploy record::no previous record could be read ({type(exc).__name__}); "
              "today's rule (changes since the previous deploy run) decides alone")
        return {}


# ---------------------------------------------------------------- build one image

def build_command(spec: BuildSpec, sha: str) -> list[str]:
    command = ["docker", "buildx", "build", "--push", "--provenance=false", "--platform", "linux/amd64",
               "--tag", f"{spec.repo}:{sha}",
               "--label", f"org.opencontainers.image.revision={sha}",
               "--label", "org.opencontainers.image.source=https://github.com/Tervory-AI/tervory-tank",
               "--cache-from", f"type=registry,ref={spec.repo}:buildcache",
               "--cache-to", f"type=registry,ref={spec.repo}:buildcache,mode=max",
               "--file", spec.dockerfile]
    for name, value in sorted(spec.args.items()):
        command += ["--build-arg", f"{name}={value}"]
    for name, path in sorted(spec.contexts.items()):
        command += ["--build-context", f"{name}={path}"]
    if spec.target:
        command += ["--target", spec.target]
    return command + [spec.context]


# ---------------------------------------------------------------- CLI

def _history(runs_path: Path, settle_s: int, max_hold_s: int, durations: dict[str, float]) -> None:
    runs = json.loads(runs_path.read_text())
    runs = runs.get("workflow_runs", runs) if isinstance(runs, dict) else runs
    runs = sorted((r for r in runs if r.get("event", "push") == "push"), key=lambda r: r["created_at"])
    folders, za = repo_rooms()
    merges: list[Merge] = []
    prev = ""
    for run in runs:
        sha = run["head_sha"]
        if not has_commit(sha):
            continue
        apps = deploy_names(git_paths(prev, sha) if prev else git_paths("", sha), folders, za)
        merges.append(Merge(datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")), sha, frozenset(apps)))
        prev = sha

    def cost(apps: frozenset[str]) -> float:
        boston = sum(durations.get(a, 180) for a in apps if not a.endswith("-za") and a != "tervory-tank-za")
        return boston + 60

    before: dict[str, list[int]] = {}
    for run in runs:
        day = run["created_at"][:10]
        before.setdefault(day, [0, 0])[0] += 1
    for merge in merges:
        if "main" in merge.apps:
            before[merge.at.strftime("%Y-%m-%d")][1] += 1
    after: dict[str, list[int]] = {}
    for at, apps in simulate(merges, settle_s=settle_s, max_hold_s=max_hold_s, cost_s=cost):
        row = after.setdefault(at.strftime("%Y-%m-%d"), [0, 0, 0])
        row[0] += 1
        row[1] += "main" in apps
        row[2] += len(apps)
    print(f"settle {settle_s}s, max hold {max_hold_s}s")
    print("day          runs  main-changed | deploys  main-deploys  app-deploys")
    for day in sorted(before):
        b, a = before[day], after.get(day, [0, 0, 0])
        print(f"{day}   {b[0]:4}  {b[1]:12} | {a[0]:7}  {a[1]:12}  {a[2]:11}")
    total_b = [sum(v[i] for v in before.values()) for i in (0, 1)]
    total_a = [sum(v[i] for v in after.values()) for i in (0, 1, 2)]
    print(f"total        {total_b[0]:4}  {total_b[1]:12} | {total_a[0]:7}  {total_a[1]:12}  {total_a[2]:11}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    dry = sub.add_parser("dry-run", help="print what a deploy of --to after --from would build and deploy")
    dry.add_argument("--from", dest="before", default="")
    dry.add_argument("--to", dest="after", default="HEAD")
    dry.add_argument("--record", default="", help="a deploy-record.json (optional)")
    hist = sub.add_parser("history", help="deploys per day before vs with the settle rule")
    hist.add_argument("--runs", required=True, type=Path, help="deploy-on-merge runs JSON from the Actions API")
    hist.add_argument("--settle", type=int, default=SETTLE_S)
    hist.add_argument("--max-hold", type=int, default=MAX_HOLD_S)
    hist.add_argument("--durations", type=Path, help="JSON {app: seconds} (default 180 s an app)")
    pl = sub.add_parser("plan")
    pl.add_argument("--out", required=True, type=Path)
    bd = sub.add_parser("build")
    bd.add_argument("--compose", required=True)
    bd.add_argument("--service", required=True)
    bd.add_argument("--sha", required=True)
    sub.add_parser("settle")
    sub.add_parser("sync-compose")
    args = parser.parse_args(argv)

    if args.command == "dry-run":
        after = subprocess.run(["git", "rev-parse", args.after], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.strip()
        before = subprocess.run(["git", "rev-parse", args.before], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip() if args.before else ""
        record = json.loads(Path(args.record).read_text()) if args.record else {}
        result = plan(before, after, record, diff=git_paths, known=has_commit,
                      composes=deployable_composes(), specs=built_services)
        folders, za = repo_rooms()
        print(f"deploy {after[:12]} after {before[:12] or after[:12] + '~1'} (dry run: no build, no Coolify call)")
        print(f"changed paths: {len(result['paths'])}")
        print("apps that would deploy, in order: " + (", ".join(deploy_names(result["paths"], folders, za)) or "none"))
        print(f"images that would build: {len(result['images'])}")
        for image in result["images"]:
            print(f"  {image['repo']}:{after}   ({image['compose']} {image['service']})")
        return 0
    if args.command == "history":
        durations = json.loads(args.durations.read_text()) if args.durations else {}
        _history(args.runs, args.settle, args.max_hold, durations)
        return 0
    if args.command == "sync-compose":
        for compose in deployable_composes():
            text = add_image_lines(compose)
            if text != (ROOT / compose).read_text(encoding="utf-8"):
                (ROOT / compose).write_text(text, encoding="utf-8")
                print("updated " + compose)
        return 0
    if args.command == "plan":
        after, before = os.environ["AFTER"], os.environ.get("BEFORE", "")
        record = latest_record(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], args.out.parent)
        result = plan(before, after, record, diff=git_paths, known=has_commit,
                      composes=deployable_composes(), specs=built_services)
        args.out.write_text(json.dumps(result, indent=2))
        print(f"::notice title=plan::{len(result['build'])} apps, {len(result['images'])} images to build for {after[:8]}")
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a", encoding="utf-8") as stream:
                stream.write("images=" + json.dumps([{"compose": i["compose"], "service": i["service"]}
                                                     for i in result["images"]]) + "\n")
        return 0
    if args.command == "build":
        if not SHA.fullmatch(args.sha):
            raise SystemExit("--sha must be a full commit")
        specs = [s for s in built_services(args.compose, sha=args.sha) if s.service == args.service]
        if len(specs) != 1:
            raise SystemExit(f"{args.compose} has no built service {args.service}")
        command = build_command(specs[0], args.sha)
        print(" ".join(command))
        return subprocess.run(command, cwd=ROOT).returncode
    if args.command == "settle":
        return _settle()
    return 2


def _github(path: str, method: str = "GET") -> object:
    request = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}",
                                     method=method, headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                                             "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(5_000_001)
        return json.loads(body) if body else None


def _settle() -> int:
    """Wait for a quiet main, then deploy; or cancel this run when a newer merge will deploy it."""
    after = os.environ["AFTER"]
    before = os.environ.get("BEFORE", "")
    settle_s = int(os.environ.get("SETTLE_S") or SETTLE_S)
    max_hold_s = int(os.environ.get("MAX_HOLD_S") or MAX_HOLD_S)
    oldest_at = 0.0
    try:
        # The oldest merge not yet deployed: the first commit after BEFORE.
        if has_commit(before):
            first = subprocess.run(["git", "log", "--reverse", "--format=%ct", f"{before}..{after}"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.split()
            oldest_at = float(first[0]) if first else 0.0
    except (subprocess.CalledProcessError, ValueError):
        oldest_at = 0.0
    while True:
        try:
            tip = _github("/commits/main")
            head = tip["sha"] if isinstance(tip, dict) else ""
            head_at = datetime.fromisoformat(tip["commit"]["committer"]["date"].replace("Z", "+00:00")).timestamp()
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
            head, head_at = "", 0.0
        decision = settle_decision(after=after, head=head, head_at=head_at, oldest_at=oldest_at,
                                   now=time.time(), settle_s=settle_s, max_hold_s=max_hold_s)
        if decision == "deploy":
            print(f"::notice title=settle::deploying {after[:8]}" + (" (tip unknown)" if not head else ""))
            return 0
        if decision == "superseded":
            print(f"::notice title=batched::{head[:8]} merged after {after[:8]}; its run deploys both. "
                  "This run cancels itself, so the next run still counts its changes.")
            try:
                _github(f"/actions/runs/{os.environ['GITHUB_RUN_ID']}/cancel", method="POST")
            except (OSError, urllib.error.URLError) as exc:
                # Could not cancel: deploy instead of failing, so no change is ever dropped.
                print(f"::warning title=settle::cancel failed ({type(exc).__name__}); deploying {after[:8]} now")
                return 0
            time.sleep(300)  # the cancel lands within seconds; this step never returns normally
            print("::warning title=settle::still running after the cancel request; deploying instead")
            return 0
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
