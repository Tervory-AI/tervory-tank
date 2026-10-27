"""RIG-2 boundaries: independent services, authenticated tasks, durable memory."""
import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import HTTPException

from test_agent1_isolation import runner as shared_runner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/rig"))
from rig_brain import room, service  # noqa: E402


def test_rig_is_its_own_box_and_only_the_api_is_public():
    cfg = yaml.safe_load((ROOT / "agents/rig/docker-compose.yml").read_text())
    services = cfg["services"]
    assert set(services) == {"agent-rig", "rig-brain", "rig-browser", "rig-browser-gateway", "rig-sandbox", "rig-forge", "rig-forge-egress"}
    assert cfg["networks"]["gw"] == {"external": True, "name": "tervory-gw-rig"}
    assert services["agent-rig"]["networks"] == ["gw", "proxy"]
    assert cfg["networks"]["proxy"] == {"external": True, "name": "59f8cnpelzwsyte1atyjc4fv"}
    labels = services["agent-rig"]["labels"]
    assert len(labels) == 13
    assert dict(label.split("=", 1) for label in labels) == {
        "traefik.enable": "true",
        "traefik.docker.network": "59f8cnpelzwsyte1atyjc4fv",
        "traefik.http.routers.rig-http.rule": "Host(`rig.tervory.com`)",
        "traefik.http.routers.rig-http.entrypoints": "http",
        "traefik.http.routers.rig-http.middlewares": "redirect-to-https",
        "traefik.http.routers.rig-https.rule": "Host(`rig.tervory.com`)",
        "traefik.http.routers.rig-https.entrypoints": "https",
        "traefik.http.routers.rig-https.tls": "true",
        "traefik.http.routers.rig-https.tls.certresolver": "letsencrypt",
        "traefik.http.routers.rig-https.service": "rig",
        "traefik.http.routers.rig-https.middlewares": "rig-gzip",
        "traefik.http.middlewares.rig-gzip.compress": "true",
        "traefik.http.services.rig.loadbalancer.server.port": "8000",
    }
    assert {name for name, spec in services.items() if spec.get("labels")} == {"agent-rig"}
    assert services["rig-brain"]["networks"] == ["gw", "sandbox", "forge-control"]
    assert services["rig-browser-gateway"]["networks"] == ["gw", "browser"]
    for name in ("sandbox", "browser"):
        assert cfg["networks"][name]["internal"] is True
        assert services["rig-" + name]["networks"] == [name]
    assert {k for k, v in services.items() if v.get("expose")} == {"agent-rig"}
    assert services["agent-rig"]["expose"] == ["8000"]
    assert cfg["volumes"]["agent_rig_data"] == {"external": True, "name": "59f8cnpelzwsyte1atyjc4fv_agent-rig-data"}
    for spec in services.values():
        assert not any(k in spec for k in ("ports", "privileged", "cap_add", "network_mode", "pid", "env_file"))
        assert spec["cap_drop"] == ["ALL"]
        assert spec["security_opt"] == ["no-new-privileges:true"]
        assert spec["mem_limit"] and spec["cpus"] and spec["healthcheck"]
        assert not any("docker.sock" in value or value.startswith("/") for value in spec.get("volumes", []))
    sandbox = services["rig-sandbox"]
    assert sandbox["read_only"] and sandbox["pids_limit"] == 64 and not sandbox.get("volumes")
    assert {n for n, s in services.items() if "SANDBOX_KEY" in s["environment"]} == {"rig-brain", "rig-sandbox"}
    assert {n for n, s in services.items() if any(k.startswith("R2_") for k in s["environment"])} == {"agent-rig", "rig-forge", "rig-forge-egress"}
    assert not any("TANK" in str(k) + str(v) for k, v in services["rig-browser"]["environment"].items())
    assert services["rig-browser"]["environment"]["ACCESS_GATEWAY_URL"] == "http://rig-browser-gateway:3000"
    assert services["rig-browser-gateway"]["environment"]["BROWSER_HOST"] == "rig-browser"


def test_rig_skills_export_rejects_other_rooms_candidates_and_tenants(tmp_path):
    tenant = str(uuid.uuid4())
    skill = {"id": "rig.search", "version": "1.0.1", "name": "rig-search", "agent": "rig",
             "state": "approved", "files": {"SKILL.md": "Read the tenant's catalogue."}}
    bundle = {"tenant_id": tenant, "room": "rig", "region": "us-east", "skills": [skill]}
    assert ("rig.search", "1.0.1") in shared_runner.install_skills(tmp_path, bundle, tenant, room="rig")
    for changed in ({"tenant_id": str(uuid.uuid4())}, {"room": "base"}, {"region": "za"}):
        with pytest.raises(RuntimeError):
            shared_runner.install_skills(tmp_path, {**bundle, **changed}, tenant, room="rig")
    for changed in ({"agent": "base"}, {"state": "candidate"}, {"state": "retired"}, {"name": "../../outside"}):
        with pytest.raises(RuntimeError):
            shared_runner.install_skills(tmp_path, {**bundle, "skills": [{**skill, **changed}]}, tenant, room="rig")


@pytest.mark.asyncio
async def test_public_api_has_no_brain_task_routes_even_with_room_key(monkeypatch):
    from test_rig import _load_rig_app

    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    app = _load_rig_app().app
    payload = {"tenant_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4()), "home_region": "us-east", "question": "A catalogue question"}
    params = {"tenant_id": payload["tenant_id"], "home_region": "us-east"}
    from http_routes import http_paths

    assert "/v1/rig/search" in http_paths(app.routes)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://rig.tervory.com") as client:
        for headers in ({}, {"X-Rig-Key": uuid.uuid4().hex}, {"X-Tank-Key": key}):
            assert (await client.post("/brain/tasks", json=payload, headers=headers)).status_code == 404
            for method in ("GET", "DELETE"):
                response = await client.request(method, f"/brain/tasks/{payload['task_id']}", params=params, headers=headers)
                assert response.status_code == 404


@pytest.mark.asyncio
async def test_private_brain_tasks_require_room_key_and_local_region(monkeypatch, tmp_path):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    body = room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="A catalogue question")
    payload = body.model_dump(mode="json")
    params = {"tenant_id": str(body.tenant_id), "home_region": "us-east"}
    path = f"/tasks/{body.task_id}"

    async def perform(body):
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "perform", perform)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url="http://rig-brain:8001") as client:
        for headers in ({}, {"X-Rig-Key": uuid.uuid4().hex}, {"X-Tank-Key": uuid.uuid4().hex}):
            assert (await client.post("/tasks", json=payload, headers=headers)).status_code == 401
            for method in ("GET", "DELETE"):
                assert (await client.request(method, path, params=params, headers=headers)).status_code == 401
        headers = {"X-Tank-Key": key}
        assert (await client.post("/tasks", json={**payload, "home_region": "za"}, headers=headers)).status_code == 403
        try:
            assert (await client.post("/tasks", json=payload, headers=headers)).status_code == 202
            assert (await client.get(path, params=params, headers=headers)).status_code == 202
            assert (await client.get(path, params={**params, "tenant_id": str(uuid.uuid4())}, headers=headers)).status_code == 404
            assert (await client.delete(path, params=params, headers=headers)).json() == {"cancelled": True}
        finally:
            await service.cancel(body.task_id, body.tenant_id, "us-east", key)


@pytest.mark.asyncio
async def test_recall_work_remember_and_tank_receipts(monkeypatch, tmp_path):
    body = room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="Which sample lamp is available?")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_KEY", uuid.uuid4().hex)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY_RIG", uuid.uuid4().hex)
    events, receipts = [], []
    original = httpx.AsyncClient
    def remote(request):
        if request.url.path == "/recall":
            events.append("recall")
            assert json.loads(request.content)["kind"] == "rig.task"
            return httpx.Response(200, json={"memories": [{"id": str(uuid.uuid4()), "tenant_id": str(body.tenant_id), "text": "old evidence"}]})
        if request.url.path == "/memories":
            events.append("remember")
            assert json.loads(request.content)["tenant_id"] == str(body.tenant_id)
            return httpx.Response(200, json={"id": str(uuid.uuid4())})
        if request.url.path.endswith("/steps"):
            data = json.loads(request.content)
            row = {**data, "ledger_id": data["id"], "room": "rig"}
            receipts.append(row)
            return httpx.Response(200, json=row)
        if request.url.path.endswith("/receipts"):
            return httpx.Response(200, json={"receipts": receipts})
        raise AssertionError("Unexpected request")
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(remote)))
    class Child:
        returncode = 0
        async def wait(self): return 0
    async def child(*args, **kwargs):
        events.append("work")
        assert "R2_SECRET_ACCESS_KEY_RIG" not in kwargs["env"]
        assert "DATABASE_URL" not in kwargs["env"]
        assert str(body.tenant_id) in kwargs["env"]["HERMES_HOME"]
        work = Path(args[-1])
        (work / "child-receipt.json").write_text(json.dumps({"tenant_id": str(body.tenant_id),
            "task_id": str(body.task_id), "steps": [], "model_receipts": [], "summary": "The sample lamp is available."}))
        return Child()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    result = await service.run_task(body)
    assert events == ["recall", "work", "remember"]
    assert result["status"] == "done"
    assert [r["action"] for r in result["tank_receipts"]] == ["recall", "remember"]
    assert json.loads((service.directory(body.tenant_id, body.task_id) / "receipt.json").read_text()) == result


@pytest.mark.asyncio
async def test_foreign_memory_fails_before_starting_hermes(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    async def memory(*args):
        return {"memories": [{"id": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4()), "text": "foreign"}]}
    async def child(*args, **kwargs):
        pytest.fail("Foreign memory reached Hermes")
    monkeypatch.setattr(service, "memory", memory)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    original = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    result = await service.run_task(room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="Question"))
    assert result["status"] == "failed" and "foreign" not in json.dumps(result)


@pytest.mark.asyncio
async def test_tasks_are_durable_deduplicated_and_tenant_scoped(monkeypatch, tmp_path):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    body = room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="Catalogue question")
    started = []
    async def perform(body):
        started.append(body.task_id)
        await asyncio.Event().wait()
    monkeypatch.setattr(service, "perform", perform)
    try:
        assert (await service.start(body, key)).status_code == 202
        await asyncio.sleep(0)
        assert (await service.start(body, key)).status_code == 202
        with pytest.raises(HTTPException) as conflict:
            await service.start(body.model_copy(update={"question": "different"}), key)
        assert conflict.value.status_code == 409 and len(started) == 1
        with pytest.raises(HTTPException) as missing:
            await service.poll(body.task_id, uuid.uuid4(), "us-east", key)
        assert missing.value.status_code == 404
    finally:
        await service.cancel(body.task_id, body.tenant_id, "us-east", key)
    assert (await service.poll(body.task_id, body.tenant_id, "us-east", key))["status"] == "failed"
    assert (await service.start(body, key))["status"] == "failed"
    assert len(started) == 1  # A restart never automatically repeats billed work.
