"""WORKERS-2 auto-update, run every 5 minutes by the tervory-workers-update user timer.

1. Mint a GitHub App installation token (contents read) and fetch main into a cache repo.
   The token goes to git only through GIT_CONFIG_* environment, never argv, a URL or a log.
2. Compare main's workers/ tree with the deployed one (WORKERS_TREE next to the code).
   Same tree: nothing to do. Different: update, unless main does not have the host install
   yet (workers/host/tervory-workers.service), so an older main never replaces this code.
   main must move forward: a non-fast-forward main (force-push) is refused, never applied.
3. Write UPDATE_PENDING next to the code first, so the service takes no new task, then check
   busy. While a task is running (the service's /health says busy), keep it and try again next
   time. Busy is checked again just before the swap. Never kill a task. Every other outcome
   (refused fast-forward, skip, error, done) clears UPDATE_PENDING.
4. Extract workers/ at main into app.new, fix modes, refresh the venv if requirements changed,
   swap it in, write COMMIT and WORKERS_TREE, restart tervory-workers.service.
Each update logs one line: old -> new commit. No secrets are logged.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import httpx

from workers.github_api import GitHub
from workers.redact import install as install_redact
from workers.redact import redact
from workers.settings import Settings, SettingsError, from_env

log = logging.getLogger("workers.updater")
MARKER = "workers/host/tervory-workers.service"
SERVICE = "tervory-workers.service"
PENDING = "UPDATE_PENDING"
BRANCH = "main"


@dataclass(frozen=True)
class Plan:
    action: str  # "none" | "update" | "skip"
    reason: str


def decide(*, deployed_tree: str, new_tree: str, has_marker: bool) -> Plan:
    if deployed_tree and deployed_tree == new_tree:
        return Plan("none", "workers/ unchanged")
    if not has_marker:
        return Plan("skip", "main does not have the host install yet; keeping the deployed code")
    return Plan("update", "workers/ changed")


def git_env(token: str) -> dict[str, str]:
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
    }


def git(repo: Path, *args: str, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(["git", "-C", str(repo), *args], env=env, text=True, capture_output=True, check=False)
    if check and done.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {redact(done.stderr.strip())[-300:]}")
    return done


def busy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:  # noqa: S310 - loopback only
            return bool(json.loads(resp.read()).get("busy"))
    except (OSError, ValueError):
        # Service down or old: nothing is running in it, so updating is safe.
        return False


def fix_modes(root: Path) -> None:
    """The task image COPYs this tree: files must stay world-readable despite UMask=0077.

    Symlinks are skipped (chmod would follow them out of the tree).
    """
    for current, dirs, files in os.walk(root, followlinks=False):
        here = Path(current)
        if not here.is_symlink():
            here.chmod(0o755)
        for name in files + [d for d in dirs if (here / d).is_symlink()]:
            path = here / name
            if path.is_symlink():
                continue
            path.chmod(0o755 if path.suffix == ".sh" else 0o644)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def update(settings: Settings, token: str, *, srv: Path, cache: Path, restart: bool = True, remote: str | None = None) -> Plan:
    pending = srv / PENDING
    keep_pending = False
    try:
        plan, keep_pending = _update(settings, token, srv=srv, cache=cache, restart=restart, remote=remote, pending=pending)
        return plan
    finally:
        # UPDATE_PENDING only stays while an update really waits for a running task. Refused
        # fast-forwards, skips, errors and finished updates all clear it, so the service never
        # stays stuck taking no new task.
        if not keep_pending:
            pending.unlink(missing_ok=True)


def _update(settings: Settings, token: str, *, srv: Path, cache: Path, restart: bool, remote: str | None, pending: Path) -> tuple[Plan, bool]:
    env = git_env(token)
    if not (cache / ".git").is_dir():
        cache.mkdir(parents=True, exist_ok=True)
        git(cache, "init", "-q", env=env)
        git(cache, "remote", "add", "origin", remote or f"https://github.com/{settings.repo}.git", env=env)
    before = git(cache, "rev-parse", "-q", "--verify", f"refs/remotes/origin/{BRANCH}", env=env, check=False).stdout.strip()
    # No "+" in the refspec: git itself refuses a non-fast-forward update of main.
    fetched = git(cache, "fetch", "-q", "--no-tags", "--filter=blob:none", "origin", f"refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", env=env, check=False)
    if fetched.returncode != 0:
        log.warning("workers update refused: main did not fast-forward (or fetch failed): %s", redact(fetched.stderr.strip())[-200:])
        return Plan("skip", "main did not fast-forward"), False
    new = git(cache, "rev-parse", f"refs/remotes/origin/{BRANCH}", env=env).stdout.strip()
    if before and before != new and git(cache, "merge-base", "--is-ancestor", before, new, env=env, check=False).returncode != 0:
        log.warning("workers update refused: main %s is not a fast-forward of %s", new[:12], before[:12])
        return Plan("skip", "main did not fast-forward"), False
    new_tree = git(cache, "rev-parse", f"{new}:workers", env=env).stdout.strip()
    has_marker = git(cache, "cat-file", "-e", f"{new}:{MARKER}", env=env, check=False).returncode == 0
    app = srv / "app"
    old = read(app / "COMMIT") or "unknown"
    plan = decide(deployed_tree=read(app / "WORKERS_TREE"), new_tree=new_tree, has_marker=has_marker)
    if plan.action != "update":
        if plan.action == "skip":
            log.info("workers update skipped: %s (deployed %s, main %s)", plan.reason, old[:12], new[:12])
        return plan, False
    # Written before the busy check: the service sees this file and takes no new task, so no task
    # can start between "not busy" and the swap.
    pending.write_text(new + "\n", encoding="utf-8")
    if busy(settings.service_port):
        log.info("workers update pending: a task is running; no new task until it is applied (deployed %s, main %s)", old[:12], new[:12])
        return Plan("skip", "task running"), True
    stage = srv / "app.new"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()
    archive = subprocess.run(["git", "-C", str(cache), "archive", new, "workers"], env=env, capture_output=True, check=False)
    if archive.returncode != 0:
        raise RuntimeError(f"git archive failed: {redact(archive.stderr.decode(errors='replace'))[-300:]}")
    subprocess.run(["tar", "-x", "-C", str(stage)], input=archive.stdout, check=True)
    (stage / "COMMIT").write_text(new + "\n", encoding="utf-8")
    (stage / "WORKERS_TREE").write_text(new_tree + "\n", encoding="utf-8")
    fix_modes(stage)
    venv = srv / "venv"
    requirements = stage / "workers/requirements.txt"
    want = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if read(venv / ".requirements.sha256") != want:
        subprocess.run([str(venv / "bin/pip"), "install", "-q", "--disable-pip-version-check", "-r", str(requirements)], check=True)
        (venv / ".requirements.sha256").write_text(want + "\n", encoding="utf-8")
    # Re-check just before the swap: never replace the code under a running task.
    if busy(settings.service_port):
        shutil.rmtree(stage, ignore_errors=True)
        log.info("workers update pending: a task started before the swap; trying again next time (deployed %s, main %s)", old[:12], new[:12])
        return Plan("skip", "task running"), True
    previous = srv / "app.old"
    shutil.rmtree(previous, ignore_errors=True)
    if app.exists():
        app.rename(previous)
    stage.rename(app)
    shutil.rmtree(previous, ignore_errors=True)
    pending.unlink(missing_ok=True)
    log.info("workers updated: %s -> %s", old[:12], new[:12])
    if restart:
        subprocess.run(["systemctl", "--user", "restart", SERVICE], check=True)
    return plan, False


async def _token(settings: Settings) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        return await GitHub(settings.repo, client).mint_installation_token(
            app_id=settings.app_id, installation_id=settings.installation_id, key_file=settings.private_key_file
        )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    install_redact()
    try:
        settings = from_env()
    except SettingsError as exc:
        log.warning("workers update: settings refused: %s", exc)
        return 1
    if not settings.github_ready or not Path(settings.private_key_file).is_file():
        log.warning("workers update: GitHub App is not configured")
        return 1
    srv = Path(os.environ.get("WORKER_SRV_DIR", "/srv/tervory-workers"))
    cache = Path(os.environ.get("WORKER_UPDATE_CACHE", str(Path.home() / ".cache/tervory-workers/repo")))
    try:
        update(settings, asyncio.run(_token(settings)), srv=srv, cache=cache)
    except Exception as exc:  # noqa: BLE001 - one redacted line, then the timer tries again
        log.warning("workers update failed: %s", redact(str(exc))[:300])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
