"""Room memory, skills and network boundaries without model or browser downloads."""
import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("brain", ROOT / "agents/_brain/__init__.py", submodule_search_locations=[str(ROOT / "agents/_brain")])
brain = importlib.util.module_from_spec(spec)
sys.modules["brain"] = brain
spec.loader.exec_module(brain)

from brain import browser, runner, security, service  # noqa: E402


def test_browser_and_sandbox_have_no_direct_egress_or_cross_room_network():
    compose = yaml.safe_load((ROOT / "agents/base/docker-compose.yml").read_text())
    assert compose["networks"]["browser"]["internal"] is True
    assert compose["networks"]["sandbox"]["internal"] is True
    assert compose["services"]["base-browser"]["networks"] == ["browser"]
    assert compose["services"]["base-sandbox"]["networks"] == ["sandbox"]
    assert compose["services"]["base-browser"]["volumes"] == ["base_browser_data:/browser-data"]
    assert "TIGER_URL" not in compose["services"]["agent-base"]["environment"]
    for item in compose["services"].values():
        assert not any("docker.sock" in v for v in item.get("volumes", []))
        assert not item.get("ports")
        assert not any(k in item.get("environment", {}) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"))


@pytest.mark.parametrize("url", ["https://evil.example", "http://www.atf.gov", "https://www.atf.gov:444", "https://u:p@www.atf.gov", "https://www.atf.gov.evil.example"])
def test_exact_host_allowlist(url):
    with pytest.raises(ValueError):
        security.allowed_url(url, frozenset({"www.atf.gov"}))


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1", "fc00::1", "224.0.0.1"])
def test_proxy_refuses_private_metadata_and_multicast(address):
    assert not security.public_address(address)


def test_human_check_is_recorded():
    assert browser.human_check('<div class="g-recaptcha">verify you are human</div>')
    assert not browser.human_check("A public business page")


def test_retired_and_candidate_skills_cannot_enter_hermes(tmp_path):
    tenant = str(uuid.uuid4())
    bundle = {"tenant_id": tenant, "room": "base", "region": "us-east", "skills": [{
        "id": "base.normalize", "version": "1.0.0", "name": "base-normalize", "state": "candidate", "agent": "base", "files": {"SKILL.md": "candidate"}}]}
    with pytest.raises(RuntimeError, match="Unapproved"):
        runner.install_skills(tmp_path, bundle, tenant)
    bundle["skills"][0]["state"] = "approved"
    runner.install_skills(tmp_path, bundle, tenant)
    assert len(list((tmp_path / "skills").glob("*/SKILL.md"))) == 1
    bundle["skills"] = []
    runner.install_skills(tmp_path, bundle, tenant)
    assert list((tmp_path / "skills").glob("*/SKILL.md")) == []


@pytest.mark.asyncio
async def test_recall_precedes_work_and_remember_closes_task(monkeypatch, tmp_path):
    tenant, task = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    events = []

    async def memory(client, path, payload):
        assert payload["tenant_id"] == str(tenant)
        events.append(path)
        if path == "/recall":
            return {"memories": [{"id": "memory", "tenant_id": str(tenant), "text": "old evidence", "sources": ["public source"]}]}
        assert payload["source"] == "base:task:" + str(task)
        return {"id": "saved"}

    class Child:
        returncode = 0
        async def wait(self):
            return 0

    async def child(*args, **kwargs):
        assert events == ["/recall"]
        assert str(tenant) in kwargs["env"]["HERMES_HOME"]
        assert "OPENAI_API_KEY" not in kwargs["env"]
        directory = Path(args[-1])
        (directory / "receipt.json").write_text(json.dumps({"tenant_id": str(tenant), "task_id": str(task),
            "steps": [{"action": "pipeline_run", "status": "done"}], "model_receipts": []}))
        events.append("work")
        return Child()

    monkeypatch.setattr(service, "memory", memory)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    receipt = await service.run_task(service.Run(tenant_id=tenant, task_id=task, home_region="us-east", batch="public pilot", count=1))
    assert events == ["/recall", "work", "/memories"]
    assert [s["action"] for s in receipt["steps"]] == ["recall", "pipeline_run", "remember"]


@pytest.mark.asyncio
async def test_foreign_memory_never_reaches_work(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    async def memory(*args):
        return {"memories": [{"tenant_id": str(uuid.uuid4()), "id": "foreign", "text": "private"}]}
    monkeypatch.setattr(service, "memory", memory)
    with pytest.raises(RuntimeError, match="tenant boundary"):
        await service.run_task(service.Run(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", batch="public pilot", count=1))
