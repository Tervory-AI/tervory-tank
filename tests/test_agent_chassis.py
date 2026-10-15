"""C6 chassis unit tests. No database and no network."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from chassis.cron import cron_matches, is_due  # noqa: E402
from chassis.db import schema_for  # noqa: E402
from chassis.files import UnsafePath, read_file, save_file  # noqa: E402
from chassis.jobs import JobContext, decide_retry, decide_timeout  # noqa: E402
from chassis.worker import (  # noqa: E402
    _fail,
    enqueue_due,
    retry_backoff_s,
    run_claimed,
    run_with_timeout,
    schedule_is_due,
)

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")


def _load_tank():
    name = "tank_main"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tank" / "main.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_template():
    spec = importlib.util.spec_from_file_location("agent_template_app", ROOT / "agents" / "_template" / "app.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TANK = _load_tank()


def _clear_agent_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("TANK_KEY_"):
            monkeypatch.delenv(name, raising=False)


# ---------- cron ----------

def test_cron_every_five_minutes_is_due_on_the_slot_only():
    slot = datetime(2026, 10, 13, 12, 5, tzinfo=timezone.utc)
    assert cron_matches("*/5 * * * *", slot)
    assert is_due("*/5 * * * *", slot, None)
    assert is_due("*/5 * * * *", slot, datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc))
    assert not is_due("*/5 * * * *", slot, datetime(2026, 10, 13, 12, 5, 30, tzinfo=timezone.utc))
    off = datetime(2026, 10, 13, 12, 6, tzinfo=timezone.utc)
    assert not is_due("*/5 * * * *", off, None)
    assert is_due("*/5 * * * *", datetime(2026, 10, 13, 12, 0, 40, tzinfo=timezone.utc), None)


def test_cron_weekday_and_sunday_zero_or_seven():
    monday = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    tuesday = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
    assert monday.weekday() == 0
    assert is_due("0 9 * * 1", monday, None)
    assert not is_due("0 9 * * 1", tuesday, None)
    sunday = datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc)
    assert is_due("0 0 * * 0", sunday, None)
    assert is_due("0 0 * * 7", sunday, None)
    assert not is_due("0 0 * * 1", sunday, None)


def test_cron_day_of_month_or_weekday_when_both_are_set():
    # 1 October 2026 is a Thursday, not a Monday. Day-of-month still matches.
    first = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    assert first.weekday() == 3
    assert cron_matches("0 0 1 * 1", first)
    assert not cron_matches("0 0 2 * 1", first)


# ---------- jobs ----------

def test_timeout_returns_a_running_job_to_the_queue():
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    kwargs = dict(status="running", now=now, timeout_s=300, attempts=1, max_attempts=3)
    assert decide_timeout(started_at=now - timedelta(seconds=301), **kwargs) == "queued"
    assert decide_timeout(started_at=now - timedelta(seconds=300), **kwargs) is None
    assert decide_timeout(started_at=None, **kwargs) == "queued"
    assert decide_timeout(status="done", started_at=now - timedelta(seconds=999), now=now, timeout_s=300, attempts=1, max_attempts=3) is None


def test_timeout_fails_when_attempts_are_used_up():
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    assert decide_timeout(
        status="running",
        started_at=now - timedelta(seconds=301),
        now=now,
        timeout_s=300,
        attempts=3,
        max_attempts=3,
    ) == "failed"


def test_retry_requeues_until_max_attempts():
    assert decide_retry(attempts=1, max_attempts=3) == "queued"
    assert decide_retry(attempts=2, max_attempts=3) == "queued"
    assert decide_retry(attempts=3, max_attempts=3) == "failed"


def test_retry_backoff_and_a_bad_cron_does_not_block_the_next_row():
    assert retry_backoff_s(1) == 30
    assert retry_backoff_s(2) == 60
    assert retry_backoff_s(3) == 90
    assert "retry_backoff_s" in inspect.getsource(_fail)
    now = datetime(2026, 10, 13, 12, 5, tzinfo=timezone.utc)
    assert schedule_is_due("not a cron", now, None) is False
    assert schedule_is_due("*/5 * * * *", now, None) is True
    assert "FOR UPDATE" in inspect.getsource(enqueue_due)
    assert "run_with_timeout" in inspect.getsource(run_claimed)


def test_schema_name_rejects_anything_that_is_not_an_agent_id():
    assert schema_for("template") == "agent_template"
    with pytest.raises(ValueError):
        schema_for("template;drop")
    with pytest.raises(ValueError):
        schema_for("../template")


# ---------- files ----------

def test_save_file_stays_inside_the_tenant_directory(tmp_path: Path):
    tenant = "11111111-1111-1111-1111-111111111111"
    path = save_file(tenant, "notes/a.txt", b"hello", root=tmp_path)
    assert path == (tmp_path / tenant / "notes" / "a.txt").resolve()
    assert read_file(tenant, "notes/a.txt", root=tmp_path) == b"hello"
    assert path.is_relative_to(tmp_path / tenant)


def test_save_file_rejects_parent_segments(tmp_path: Path):
    tenant = "tenant-a"
    for name in ("../secret", "a/../../secret", "..", "/etc/passwd", "foo/../../../etc/passwd"):
        with pytest.raises(UnsafePath):
            save_file(tenant, name, b"nope", root=tmp_path)
    assert not (tmp_path / "secret").exists()
    assert not (tmp_path / "passwd").exists()


def test_save_file_rejects_a_symlink_that_leaves_the_tenant(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "data"
    tenant = "tenant-a"
    (root / tenant).mkdir(parents=True)
    (root / tenant / "link").symlink_to(outside)
    with pytest.raises(UnsafePath):
        save_file(tenant, "link/pwned.txt", b"nope", root=root)
    assert not (outside / "pwned.txt").exists()


def _request(path: str) -> Request:
    return Request({
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    })


class _CM:
    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self) -> object:
        return self.value

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Conn:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def execute(self, *args: object) -> None:
        self.calls.append(args)

    def transaction(self) -> _CM:
        return _CM(self)


class _Pool:
    def __init__(self) -> None:
        self.conn = _Conn()

    def acquire(self) -> _CM:
        return _CM(self.conn)


# ---------- agent keys ----------

def test_require_key_accepts_the_workspace_key_and_an_agent_key(monkeypatch: pytest.MonkeyPatch):
    _clear_agent_keys(monkeypatch)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", "template-secret-value")
    monkeypatch.setenv("TANK_KEY_TIGER", "tiger-secret-value")
    route = _request("/v1/route")

    async def check():
        assert await TANK.require_key(route, TANK.TANK_API_KEY) is None
        assert await TANK.require_key(route, "template-secret-value") == "template"
        assert await TANK.require_key(route, "tiger-secret-value") == "tiger"
        with pytest.raises(HTTPException) as caught:
            await TANK.require_key(route, "not-a-key")
        assert caught.value.status_code == 401
        assert "not-a-key" not in str(caught.value.detail)
        with pytest.raises(HTTPException) as weird:
            await TANK.require_key(route, "kéy")
        assert weird.value.status_code == 401

    asyncio.run(check())


def test_agent_key_comes_from_env_and_the_table_is_written_once(monkeypatch: pytest.MonkeyPatch):
    _clear_agent_keys(monkeypatch)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", "  template-secret-value  ")
    monkeypatch.setattr(TANK, "_agent_keys_synced", False)
    fake = _Pool()
    monkeypatch.setattr(TANK, "_pool", object())
    monkeypatch.setattr(TANK, "pool", lambda: fake)
    route = _request("/v1/route")
    source = inspect.getsource(TANK.require_key)
    assert "SELECT agent FROM tank.agent_keys" not in source
    assert "DELETE FROM tank.agent_keys" in source

    async def check():
        assert await TANK.require_key(route, "template-secret-value") == "template"
        written = len(fake.conn.calls)
        assert written >= 2
        assert any("DELETE FROM tank.agent_keys" in str(call[0]) for call in fake.conn.calls)
        assert all("template-secret-value" not in repr(call) for call in fake.conn.calls)
        assert await TANK.require_key(route, "template-secret-value") == "template"
        assert len(fake.conn.calls) == written
        monkeypatch.delenv("TANK_KEY_TEMPLATE")
        with pytest.raises(HTTPException) as caught:
            await TANK.require_key(route, "template-secret-value")
        assert caught.value.status_code == 401

    asyncio.run(check())


def test_blank_agent_key_is_ignored(monkeypatch: pytest.MonkeyPatch):
    _clear_agent_keys(monkeypatch)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", "   ")

    async def check():
        with pytest.raises(HTTPException) as caught:
            await TANK.require_key(_request("/v1/route"), "   ")
        assert caught.value.status_code == 401

    asyncio.run(check())


def test_agent_key_is_limited_to_route_skill_run_and_health(monkeypatch: pytest.MonkeyPatch):
    _clear_agent_keys(monkeypatch)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", "template-secret-value")
    allowed = ("/health", "/v1/route", "/v1/skills/base.find_site/run")
    blocked = (
        "/v1/policy",
        "/v1/graduation",
        "/v1/skills/base.find_site/approve",
        "/v1/skills/base.find_site/1.0.0/evals",
        "/v1/base/run",
        "/v1/tasks",
        "/v1/ledger/summary",
    )

    async def check():
        for path in allowed:
            assert await TANK.require_key(_request(path), "template-secret-value") == "template"
        for path in blocked:
            with pytest.raises(HTTPException) as caught:
                await TANK.require_key(_request(path), "template-secret-value")
            assert caught.value.status_code == 403
        assert await TANK.require_key(_request("/v1/policy"), TANK.TANK_API_KEY) is None

    asyncio.run(check())


def test_route_overwrites_agent_with_the_authenticated_caller(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, str] = {}

    async def fake_run_route(req, task_id=None):
        seen["agent"] = req.agent
        return "sent"

    monkeypatch.setattr(TANK, "run_route", fake_run_route)
    body = TANK.RouteRequest(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        agent="tier0",
        messages=[TANK.Message(role="user", content="hello")],
    )

    async def check():
        assert await TANK.route(body, "template") == "sent"
        assert seen["agent"] == "template"
        assert body.agent == "tier0"
        other = body.model_copy(update={"agent": "tiger"})
        assert await TANK.route(other, None) == "sent"
        assert seen["agent"] == "tiger"

    asyncio.run(check())


# ---------- skill gate ----------

def _package(tmp_path: Path, agent: str, shared: list[str] | None = None):
    folder = tmp_path / agent
    folder.mkdir()
    lines = [f"agent: {agent}\n"]
    if shared is not None:
        lines.append("shared_with:\n")
        lines.extend(f"  - {item}\n" for item in shared)
    (folder / "skill.yaml").write_text("".join(lines), encoding="utf-8")
    return SimpleNamespace(agent=agent, path=folder, ref=f"{agent}.demo@1.0.0")


def _body():
    return TANK.SkillRun(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        input={"n": 1},
        version="1.0.0",
    )


def test_skill_gate_blocks_another_agents_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pkg = _package(tmp_path, "tiger")
    monkeypatch.setattr(TANK, "get_package", lambda skill_id, version: pkg)

    async def check():
        with pytest.raises(HTTPException) as caught:
            await TANK.run_one_skill("tiger.demo", _body(), "template")
        assert caught.value.status_code == 403

    asyncio.run(check())


def test_skill_gate_allows_own_skill_and_stamps_the_caller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pkg = _package(tmp_path, "template")
    seen: dict[str, str] = {}
    monkeypatch.setattr(TANK, "get_package", lambda skill_id, version: pkg)

    async def skill_state(skill_id, version):
        return "approved"

    def make_ctx(package, tenant_id, task_id=None, preview=False):
        return SimpleNamespace(agent=package.agent, cost_usd=0.0, tenant_id=tenant_id)

    async def run_skill(package, payload, ctx):
        seen["agent"] = ctx.agent
        return {"ok": True}

    monkeypatch.setattr(TANK, "skill_state", skill_state)
    monkeypatch.setattr(TANK, "make_ctx", make_ctx)
    monkeypatch.setattr(TANK.skala, "run_skill", run_skill)

    async def check():
        out = await TANK.run_one_skill("template.demo", _body(), "template")
        assert out["ok"] is True
        assert seen["agent"] == "template"

    asyncio.run(check())


def test_skill_gate_allows_shared_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pkg = _package(tmp_path, "base", shared=["template"])
    seen: dict[str, str] = {}
    monkeypatch.setattr(TANK, "get_package", lambda skill_id, version: pkg)

    async def skill_state(skill_id, version):
        return "approved"

    def make_ctx(package, tenant_id, task_id=None, preview=False):
        return SimpleNamespace(agent=package.agent, cost_usd=0.0)

    async def run_skill(package, payload, ctx):
        seen["agent"] = ctx.agent
        return {"ok": True}

    monkeypatch.setattr(TANK, "skill_state", skill_state)
    monkeypatch.setattr(TANK, "make_ctx", make_ctx)
    monkeypatch.setattr(TANK.skala, "run_skill", run_skill)

    async def check():
        await TANK.run_one_skill("base.demo", _body(), "template")
        assert seen["agent"] == "template"

    asyncio.run(check())


def test_workspace_key_does_not_change_the_skill_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pkg = _package(tmp_path, "base")
    seen: dict[str, str] = {}
    monkeypatch.setattr(TANK, "get_package", lambda skill_id, version: pkg)

    async def skill_state(skill_id, version):
        return "approved"

    def make_ctx(package, tenant_id, task_id=None, preview=False):
        return SimpleNamespace(agent=package.agent, cost_usd=0.0)

    async def run_skill(package, payload, ctx):
        seen["agent"] = ctx.agent
        return {"ok": True}

    monkeypatch.setattr(TANK, "skill_state", skill_state)
    monkeypatch.setattr(TANK, "make_ctx", make_ctx)
    monkeypatch.setattr(TANK.skala, "run_skill", run_skill)

    async def check():
        await TANK.run_one_skill("base.demo", _body(), None)
        assert seen["agent"] == "base"

    asyncio.run(check())


# ---------- template and compose ----------

def test_template_has_a_ping_job_and_a_five_minute_heartbeat():
    mod = _load_template()
    assert mod.app.state.agent == "template"
    assert mod.app.state.schedules == [
        {
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ]

    async def check():
        ctx = JobContext(
            agent="template",
            tenant_id="00000000-0000-0000-0000-000000000001",
            job_id="job",
            kind="ping",
            input={},
            files=None,
            tank=None,
            memory=None,
            browser=None,
        )
        assert await mod.ping(ctx) == {"pong": True, "agent": "template"}

        class FakeMemory:
            def __init__(self) -> None:
                self.calls: list[tuple] = []

            async def remember(self, tenant_id, text, kind, source):
                self.calls.append((tenant_id, text, kind, source))
                return {"id": "m1", "seen": len(self.calls), "deduped": len(self.calls) > 1}

        class DownMemory:
            async def remember(self, *args, **kwargs):
                raise RuntimeError("hermes unreachable")

        fake = FakeMemory()
        beat = JobContext(
            agent="template",
            tenant_id="00000000-0000-0000-0000-000000000001",
            job_id="job",
            kind="ping",
            input={"heartbeat": True},
            files=None,
            tank=None,
            memory=fake,
            browser=None,
        )
        await mod.ping(beat)
        second = await mod.ping(beat)
        assert second["heartbeats_seen"] == 2
        assert fake.calls[0][2] == "heartbeat"
        assert fake.calls[0][1] == fake.calls[1][1]  # same text, so Hermes folds it

        beat.memory = DownMemory()
        down = await mod.ping(beat)
        assert down["pong"] is True and down["memory"] == "unreachable"

    asyncio.run(check())


def test_handler_timeout_cancels_a_stuck_job():
    async def hang(_ctx):
        await asyncio.sleep(5)
        return {"ok": True}

    async def quick(_ctx):
        return {"pong": True}

    async def check():
        with pytest.raises(TimeoutError):
            await run_with_timeout(hang, None, 0)  # type: ignore[arg-type]
        assert await run_with_timeout(quick, None, 1) == {"pong": True}  # type: ignore[arg-type]

    asyncio.run(check())


def test_agent_boxes_do_not_share_a_network():
    """The box is its own compose project. Only Tank and Postgres join its gateway."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "agent-template" not in services
    networks = compose["networks"]
    assert "net_template" not in networks
    gateway = networks["tervory-gw-template"]
    assert gateway["external"] is True
    assert gateway["name"] == "tervory-gw-template"
    for name in ("tank", "postgres"):
        assert "tervory-gw-template" in services[name]["networks"]
        assert "default" in services[name]["networks"]
    for name in ("tiger", "workspace", "litellm", "redis", "qdrant", "searxng"):
        assert "tervory-gw-template" not in (services[name].get("networks") or [])
    tank = services["tank"]
    assert "command" not in tank
    assert "volumes" not in tank
    assert "AGENT_DB_PASSWORD_TEMPLATE" not in tank["environment"]
    assert "agent-roles" not in (tank.get("depends_on") or {})
    roles = services["agent-roles"]
    assert roles["build"]["context"] == "./agents"
    assert roles["build"]["dockerfile"] == "Dockerfile.roles"
    assert roles["restart"] == "on-failure"
    assert roles["networks"] == ["default"]
    assert "tervory-gw-template" not in roles["networks"]
    assert roles["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "AGENT_DB_PASSWORD_TEMPLATE" in roles["environment"]
    assert "POSTGRES_PASSWORD" in roles["environment"]["DATABASE_URL"]
    image = (ROOT / "agents" / "Dockerfile.roles").read_text(encoding="utf-8")
    assert "asyncpg==0.30.0" in image
    assert "provision_agent_roles.py" in image
    provision = (ROOT / "agents" / "_chassis" / "provision_agent_roles.py").read_text(encoding="utf-8")
    assert "uvicorn" not in provision
    assert "execvp" not in provision

    box_file = ROOT / "agents" / "_template" / "docker-compose.yml"
    template = yaml.safe_load(box_file.read_text(encoding="utf-8"))
    box = template["services"]["agent-template"]
    assert template["networks"]["gw"]["external"] is True
    assert template["networks"]["gw"]["name"] == "tervory-gw-template"
    assert box["networks"] == ["gw"]
    assert box["mem_limit"] == "512m"
    assert box["cpus"] in (0.5, "0.5")
    assert "health" in str(box["healthcheck"]["test"])
    url = box["environment"]["DATABASE_URL"]
    assert url.startswith("postgresql://agent_template:")
    assert "POSTGRES_PASSWORD" not in box["environment"]
    assert "POSTGRES_USER" not in box["environment"]

    script = ROOT / "agents" / "check_isolation.sh"
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!")
    assert os.access(script, os.X_OK)
    for host in ("tank", "postgres", "workspace", "redis", "qdrant", "litellm", "searxng", "tiger"):
        assert host in text
    assert "PASS" in text and "FAIL" in text
    assert ".State.Health.Status" in text
    assert "ping job reaches done" in text
    assert "NetworkSettings.Networks" in text
    assert "docker network inspect" in text
    assert "tervory-gw" in text
    assert "source " not in text
