"""C6 chassis unit tests. No database and no network."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tank"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from chassis.cron import cron_matches, is_due  # noqa: E402
from chassis.db import schema_for  # noqa: E402
from chassis.files import UnsafePath, read_file, save_file  # noqa: E402
from chassis.jobs import JobContext, decide_retry, decide_timeout  # noqa: E402

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


# ---------- agent keys ----------

def test_require_key_accepts_the_workspace_key_and_an_agent_key(monkeypatch: pytest.MonkeyPatch):
    _clear_agent_keys(monkeypatch)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", "template-secret-value")
    monkeypatch.setenv("TANK_KEY_TIGER", "tiger-secret-value")

    async def check():
        assert await TANK.require_key(TANK.TANK_API_KEY) is None
        assert await TANK.require_key("template-secret-value") == "template"
        assert await TANK.require_key("tiger-secret-value") == "tiger"
        with pytest.raises(HTTPException) as caught:
            await TANK.require_key("not-a-key")
        assert caught.value.status_code == 401
        assert "not-a-key" not in str(caught.value.detail)

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

    asyncio.run(check())


def test_agent_boxes_do_not_share_a_network():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    template = services["agent-template"]
    assert template["networks"] == ["net_template"]
    assert template["mem_limit"] == "512m"
    assert template["cpus"] in (0.5, "0.5")
    assert "default" not in template["networks"]
    for name in ("tank", "tiger", "postgres"):
        assert "net_template" in services[name]["networks"]
        assert "default" in services[name]["networks"]
    assert "net_template" not in (services["workspace"].get("networks") or [])
    assert "net_template" not in (services["litellm"].get("networks") or [])
    owners: dict[str, str] = {}
    for name, service in services.items():
        if not name.startswith("agent-"):
            continue
        for net in service.get("networks") or []:
            assert net not in owners, f"{name} shares {net} with {owners[net]}"
            owners[net] = name
    assert owners["net_template"] == "agent-template"
