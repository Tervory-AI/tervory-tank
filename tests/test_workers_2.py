"""WORKERS-2: heartbeat, the workers pause, the /control tile data, and the auto-updater."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import controls  # noqa: E402
import workers_status  # noqa: E402
from workers import tank_status, updater  # noqa: E402
from workers.service import Service  # noqa: E402
from workers.settings import PLATFORM_TENANT, Settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORKER_KEY = "workers-key-" + "x" * 20
FOUNDER = {"x-tank-key": "offline-workspace-key", "x-tervory-admin": "founder-one"}


class Conn:
    def __init__(self) -> None:
        self.paused = False
        self.beat: dict | None = None
        self.writes: list[tuple[str, tuple]] = []
        self.fail = False

    def acquire(self):
        return self

    def transaction(self):
        return self

    async def __aenter__(self):
        if self.fail:
            raise RuntimeError("database unavailable")
        return self

    async def __aexit__(self, *_):
        return False

    async def fetchval(self, sql, *args):
        if "tank.workers_controls" in sql:
            return self.paused
        if "tank.controls" in sql:
            return False
        return None

    async def fetchrow(self, sql, *args):
        return self.beat

    async def fetch(self, sql, *args):
        return []

    async def execute(self, sql, *args):
        self.writes.append((sql, args))
        if "INSERT INTO tank.workers_controls" in sql:
            self.paused = args[1]
        if "INSERT INTO tank.workers_heartbeat" in sql:
            self.beat = {
                "worker": args[0], "state": args[1], "issue": args[2], "commit": args[3],
                "last_error": args[4], "seen_at": datetime.now(timezone.utc),
            }


@pytest.fixture
def conn(monkeypatch):
    value = Conn()
    monkeypatch.setattr(controls, "db", lambda: value)
    monkeypatch.setattr(workers_status, "db", lambda: value)
    return value


@pytest.fixture
def client(monkeypatch, conn):
    monkeypatch.setenv("TANK_API_KEY", "offline-workspace-key")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-one")
    monkeypatch.setenv("TANK_KEY_WORKERS", WORKER_KEY)
    app = FastAPI()
    app.include_router(controls.router)
    app.include_router(workers_status.router)
    app.include_router(workers_status.founder_router)
    return TestClient(app)


# ---------- Tank: heartbeat ----------


def test_heartbeat_needs_the_workers_key(client, conn):
    body = {"state": "running", "commit": "abc1234"}
    for headers in ({}, {"x-tank-key": "wrong"}, {"x-tank-key": "offline-workspace-key"}):
        assert client.post("/v1/workers/heartbeat", json=body, headers=headers).status_code == 401
        assert client.get("/v1/workers/paused", headers=headers).status_code == 401
    assert not conn.writes


def test_heartbeat_upserts_and_redacts(client, conn):
    secret = "ghs_" + "A" * 30
    body = {"state": "running", "issue": 211, "commit": "C379A45", "last_error": f"task 211 failed: token {secret}"}
    resp = client.post("/v1/workers/heartbeat", json=body, headers={"x-tank-key": WORKER_KEY})
    assert resp.status_code == 200
    assert conn.beat and conn.beat["commit"] == "c379a45" and conn.beat["issue"] == 211
    assert secret not in (conn.beat["last_error"] or "") and "[redacted]" in conn.beat["last_error"]
    for bad in ({"state": "dead", "commit": "abc1234"}, {"state": "running", "commit": "not a sha"},
                {"state": "running", "commit": "abc1234", "worker": "Boston Host"}, {"state": "running", "extra": 1}):
        assert client.post("/v1/workers/heartbeat", json=bad, headers={"x-tank-key": WORKER_KEY}).status_code == 422


def test_scrub_catches_tokens_and_keys():
    text = "a ghp_" + "b" * 20 + " Bearer zzz x-tank-key: kkk sk-" + "c" * 20 + " -----BEGIN " + "RSA PRIVATE KEY----- MII"
    out = workers_status.scrub(text) or ""
    for leaked in ("ghp_", "zzz", "kkk", "sk-c", "MII"):
        assert leaked not in out
    assert len(workers_status.scrub("x" * 5000) or "") == workers_status.MAX_ERROR


# ---------- Tank: the workers pause ----------


def test_workers_pause_is_founder_only_and_logged_like_the_paid_pause(client, conn):
    for headers in ({}, {**FOUNDER, "x-tervory-admin": "other"}, {"x-tank-key": WORKER_KEY}):
        assert client.put("/v1/controls/workers-paused", headers=headers, json={"paused": True}).status_code == 404
        assert client.get("/v1/controls/workers", headers=headers).status_code == 404
    assert not conn.writes
    for value in (True, False, False):
        assert client.put("/v1/controls/workers-paused", headers=FOUNDER, json={"paused": value}).json() == {"workers_paused": value}
    audit = [args for sql, args in conn.writes if "INSERT INTO tank.control_log" in sql]
    assert [args[2:] for args in audit] == [(False, True), (True, False), (False, False)]
    assert all(args[:2] == (controls.PLATFORM, "founder-one") for args in audit)
    sql = [sql for sql, _ in conn.writes if "INSERT INTO tank.control_log" in sql][0]
    assert "'workers_paused'" in sql and "(tenant_id,name,by_user,old_value,new_value)" in sql


def test_worker_reads_the_pause_and_it_fails_closed(client, conn):
    conn.paused = True
    assert client.get("/v1/workers/paused", headers={"x-tank-key": WORKER_KEY}).json() == {"paused": True}
    conn.paused = False
    assert client.get("/v1/workers/paused", headers={"x-tank-key": WORKER_KEY}).json() == {"paused": False}
    conn.fail = True
    assert client.get("/v1/workers/paused", headers={"x-tank-key": WORKER_KEY}).status_code == 503


def test_founder_tile_shows_stale_after_three_minutes(client, conn):
    assert client.get("/v1/controls/workers", headers=FOUNDER).json()["worker"] is None
    client.post("/v1/workers/heartbeat", json={"state": "paused", "commit": "abc1234"}, headers={"x-tank-key": WORKER_KEY})
    tile = client.get("/v1/controls/workers", headers=FOUNDER).json()
    assert tile["worker"]["checking_in"] is True and tile["worker"]["state"] == "paused"
    assert tile["stale_after_s"] == 180
    old = {**conn.beat, "seen_at": datetime.now(timezone.utc) - timedelta(minutes=4)}
    assert workers_status.view(old)["checking_in"] is False


def test_storage_is_additive_and_main_only_registers_routes():
    schema = (ROOT / "tank/schema.sql").read_text()
    block = schema.split("-- WORKERS-2:", 1)[1]
    assert "CREATE TABLE IF NOT EXISTS tank.workers_heartbeat" in block
    assert "CREATE TABLE IF NOT EXISTS tank.workers_controls" in block
    assert "ALTER TABLE" not in block and "DROP" not in block
    assert "CHECK (name = 'paid_paused')" in schema
    main = (ROOT / "tank/main.py").read_text()
    assert 'app.include_router(__import__("workers_status").router)' in main
    assert 'app.include_router(__import__("workers_status").founder_router)' in main
    assert main.count("include_router(__import__(\"workers_status\")") == 2
    assert 'return await __import__("workers_status").panel()' in main
    assert "workers_status.py" in (ROOT / "tank/Dockerfile").read_text()


# ---------- worker: heartbeat and pause ----------


def _settings(tmp_path: Path) -> Settings:
    return Settings(link="loopback", tank_url="http://127.0.0.1:8100", tenant_id=PLATFORM_TENANT, code_dir=str(tmp_path))


def test_worker_pause_check_fails_closed_and_heartbeat_is_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("TANK_KEY_WORKERS", WORKER_KEY)
    (tmp_path / "COMMIT").write_text("c379a45aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
    seen: list[httpx.Request] = []
    mode = {"paused": False, "status": 200}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/workers/paused":
            return httpx.Response(mode["status"], json={"paused": mode["paused"]})
        return httpx.Response(200, json={"ok": True})

    async def run() -> list[bool]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            control = tank_status.TankControl(_settings(tmp_path), client)
            results = [await control.paused()]
            mode["paused"] = True
            results.append(await control.paused())
            mode.update(paused=False, status=503)
            results.append(await control.paused())
            assert await control.heartbeat(issue=211, last_error="boom ghs_" + "Z" * 30)
            return results

    assert asyncio.run(run()) == [False, True, True]
    beat = seen[-1]
    assert str(beat.url) == "http://127.0.0.1:8100/v1/workers/heartbeat"
    assert beat.headers["x-tank-key"] == WORKER_KEY
    body = beat.content.decode()
    assert '"state":"paused"' in body.replace(" ", "") and "c379a45" in body and "ghs_Z" not in body


def test_last_error_handler_keeps_one_redacted_line():
    handler = tank_status.LastError()
    logger = logging.getLogger("workers.test-last-error")
    logger.addHandler(handler)
    logger.warning("task %s failed: %s", 211, "token ghs_" + "q" * 20)
    logger.info("ignored")
    logger.removeHandler(handler)
    assert handler.line and "qqqq" not in handler.line and "211" in handler.line


class _GitHub:
    def __init__(self) -> None:
        from workers.issues import WorkerIssue

        self.task = WorkerIssue(number=211, title="first run", body="docs/cursor/WORKER-0.md", brief="docs/cursor/WORKER-0.md")

    async def list_issues(self, token):
        return [{}]

    def malformed(self, payloads):
        return []

    def tasks(self, payloads):
        return [self.task]

    async def open_pulls(self, token, branch):
        return []


class _Pause:
    def __init__(self, paused: bool) -> None:
        self.value = paused
        self.calls = 0

    async def paused(self) -> bool:
        self.calls += 1
        return self.value


def test_service_takes_no_task_while_paused(tmp_path):
    for paused, expected in ((True, set()), (False, {211})):
        pause = _Pause(paused)
        service = Service(_settings(tmp_path), _GitHub(), object(), pause)  # type: ignore[arg-type]
        service._run = lambda task: asyncio.sleep(0)  # type: ignore[method-assign]

        async def go() -> None:
            await service.poll_once("t")
            await asyncio.gather(*service.jobs)

        asyncio.run(go())
        assert pause.calls == 1
        assert service.inflight == expected
    service = Service(_settings(tmp_path), _GitHub(), object())  # type: ignore[arg-type]
    asyncio.run(service.poll_once("t"))
    assert service.inflight == set()


# ---------- auto-update ----------


def test_decide():
    assert updater.decide(deployed_tree="t1", new_tree="t1", has_marker=True).action == "none"
    assert updater.decide(deployed_tree="t1", new_tree="t2", has_marker=True).action == "update"
    assert updater.decide(deployed_tree="", new_tree="t2", has_marker=True).action == "update"
    assert updater.decide(deployed_tree="t1", new_tree="t2", has_marker=False).action == "skip"


def test_git_env_keeps_the_token_out_of_argv_and_urls():
    token = "ghs_" + "T" * 30
    env = updater.git_env(token)
    assert token not in " ".join(env.values())
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    source = (ROOT / "workers/updater.py").read_text()
    assert "x-access-token:{token}@" not in source


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_update_replaces_workers_only_when_main_has_the_host_install(tmp_path, caplog):
    origin = tmp_path / "origin"
    (origin / "workers/host").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main", str(origin))
    (origin / "workers/requirements.txt").write_text("httpx\n")
    (origin / "workers/a.py").write_text("A = 1\n")
    (origin / "workers/run.sh").write_text("#!/bin/sh\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "old main without host install")
    srv = tmp_path / "srv"
    (srv / "app/workers").mkdir(parents=True)
    (srv / "app/workers/a.py").write_text("A = 'deployed'\n")
    (srv / "app/COMMIT").write_text("d" * 40 + "\n")
    (srv / "app/WORKERS_TREE").write_text("e" * 40 + "\n")
    (srv / "venv/bin").mkdir(parents=True)
    import hashlib

    (srv / "venv/.requirements.sha256").write_text(hashlib.sha256(b"httpx\n").hexdigest() + "\n")
    settings = Settings(service_port=_free_port())
    cache = tmp_path / "cache"
    with caplog.at_level(logging.INFO, logger="workers.updater"):
        plan = updater.update(settings, "ghs_" + "x" * 30, srv=srv, cache=cache, restart=False, remote=str(origin))
    assert plan.action == "skip"
    assert (srv / "app/workers/a.py").read_text() == "A = 'deployed'\n"
    (origin / "workers/host/tervory-workers.service").write_text("[Service]\n")
    (origin / "workers/a.py").write_text("A = 2\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "main with host install")
    new = _git(origin, "rev-parse", "HEAD")
    with caplog.at_level(logging.INFO, logger="workers.updater"):
        plan = updater.update(settings, "ghs_" + "x" * 30, srv=srv, cache=cache, restart=False, remote=str(origin))
    assert plan.action == "update"
    assert (srv / "app/workers/a.py").read_text() == "A = 2\n"
    assert (srv / "app/COMMIT").read_text().strip() == new
    assert oct((srv / "app/workers/a.py").stat().st_mode & 0o777) == oct(0o644)
    assert oct((srv / "app/workers/run.sh").stat().st_mode & 0o777) == oct(0o755)
    assert f"workers updated: {'d' * 12} -> {new[:12]}" in caplog.text
    assert "ghs_" not in caplog.text
    again = updater.update(settings, "ghs_" + "x" * 30, srv=srv, cache=cache, restart=False, remote=str(origin))
    assert again.action == "none"


def test_timer_units_and_install_script():
    timer = (ROOT / "workers/host/tervory-workers-update.timer").read_text()
    assert "OnUnitActiveSec=5min" in timer and "WantedBy=timers.target" in timer
    unit = (ROOT / "workers/host/tervory-workers-update.service").read_text()
    for line in ("Type=oneshot", "NoNewPrivileges=yes", "UMask=0077", "ExecStart=/srv/tervory-workers/venv/bin/python -m workers.updater",
                 "EnvironmentFile=/etc/tervory-workers/worker.env"):
        assert line in unit.splitlines()
    script = (ROOT / "workers/host/install.sh").read_text()
    assert "tervory-workers-update.timer" in script and "enable --now" in script
    assert "WORKERS_TREE" in script


def test_control_tile_is_wired():
    control = ROOT / "workspace/app/control"
    view = (control / "view.tsx").read_text()
    assert "WorkersTile" in view and "not checking in" in view
    workers = (control / "workers.ts").read_text()
    assert "STALE_AFTER_S = 180" in workers
    assert "/v1/controls/workers-paused" in workers and "/v1/controls/workers" in workers
    assert "workersPauseAction" in (control / "actions.ts").read_text()
    assert uuid.UUID(str(controls.PLATFORM))


# ---------- Claude review on 39b67d0 (same pass) ----------


def _origin_with_host_install(tmp_path: Path) -> tuple[Path, Path, Settings]:
    origin = tmp_path / "origin"
    (origin / "workers/host").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main", str(origin))
    (origin / "workers/requirements.txt").write_text("httpx\n")
    (origin / "workers/host/tervory-workers.service").write_text("[Service]\n")
    (origin / "workers/a.py").write_text("A = 1\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "main")
    srv = tmp_path / "srv"
    (srv / "app/workers").mkdir(parents=True)
    (srv / "app/workers/a.py").write_text("A = 'deployed'\n")
    (srv / "app/WORKERS_TREE").write_text("e" * 40 + "\n")
    (srv / "venv/bin").mkdir(parents=True)
    import hashlib

    (srv / "venv/.requirements.sha256").write_text(hashlib.sha256(b"httpx\n").hexdigest() + "\n")
    return origin, srv, Settings(service_port=_free_port())


def test_updater_refuses_a_non_fast_forward_main(tmp_path):
    origin, srv, settings = _origin_with_host_install(tmp_path)
    cache = tmp_path / "cache"
    token = "ghs_" + "x" * 30
    assert updater.update(settings, token, srv=srv, cache=cache, restart=False, remote=str(origin)).action == "update"
    deployed = (srv / "app/workers/a.py").read_text()
    # Someone force-pushes main to an unrelated history.
    _git(origin, "checkout", "-q", "--orphan", "rewrite")
    (origin / "workers/a.py").write_text("A = 'rewritten'\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "rewritten main")
    _git(origin, "branch", "-q", "-M", "rewrite", "main")
    plan = updater.update(settings, token, srv=srv, cache=cache, restart=False, remote=str(origin))
    assert plan == updater.Plan("skip", "main did not fast-forward")
    assert (srv / "app/workers/a.py").read_text() == deployed
    source = (ROOT / "workers/updater.py").read_text()
    assert '"+refs/heads/' not in source and "merge-base" in source


def test_update_pending_stops_new_tasks_until_applied(tmp_path, monkeypatch):
    origin, srv, settings = _origin_with_host_install(tmp_path)
    cache = tmp_path / "cache"
    token = "ghs_" + "x" * 30
    monkeypatch.setattr(updater, "busy", lambda port: True)
    plan = updater.update(settings, token, srv=srv, cache=cache, restart=False, remote=str(origin))
    assert plan == updater.Plan("skip", "task running")
    assert (srv / "UPDATE_PENDING").exists()
    # The service, whose code lives in srv/app, takes no new task while the flag is there.
    pause = _Pause(False)
    service = Service(_settings(srv / "app"), _GitHub(), object(), pause)  # type: ignore[arg-type]
    service._run = lambda task: asyncio.sleep(0)  # type: ignore[method-assign]
    asyncio.run(service.poll_once("t"))
    assert service.inflight == set()
    monkeypatch.setattr(updater, "busy", lambda port: False)
    assert updater.update(settings, token, srv=srv, cache=cache, restart=False, remote=str(origin)).action == "update"
    assert not (srv / "UPDATE_PENDING").exists()

    async def go() -> None:
        await service.poll_once("t")
        await asyncio.gather(*service.jobs)

    asyncio.run(go())
    assert service.inflight == {211}


def test_fix_modes_skips_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("secret\n")
    outside.chmod(0o600)
    tree = tmp_path / "tree"
    (tree / "sub").mkdir(parents=True)
    (tree / "sub/a.py").write_text("A = 1\n")
    (tree / "sub/a.py").chmod(0o600)
    (tree / "link").symlink_to(outside)
    (tree / "dirlink").symlink_to(tmp_path)
    updater.fix_modes(tree)
    assert oct((tree / "sub/a.py").stat().st_mode & 0o777) == oct(0o644)
    assert oct(outside.stat().st_mode & 0o777) == oct(0o600)
