"""RIG-2 boundaries: independent services, authenticated tasks, durable memory."""
import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx
import pytest
import yaml
from chassis.user_assertion import SignedUser

from test_agent1_isolation import runner as shared_runner

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ORIGIN = "http://rig-brain:8001"
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
    assert len(labels) == 15
    routing = dict(label.split("=", 1) for label in labels)
    # Matcher coverage is exercised by test_rig_product_host, including real Traefik.
    api_rule = routing["traefik.http.routers.rig-https.rule"]
    assert api_rule.startswith("Host(`rig.tervory.com`) && (")
    assert dict(label.split("=", 1) for label in labels) == {
        "traefik.enable": "true",
        "traefik.docker.network": "59f8cnpelzwsyte1atyjc4fv",
        "traefik.http.routers.rig-http.rule": api_rule,
        "traefik.http.routers.rig-http.priority": "1000",
        "traefik.http.routers.rig-http.entrypoints": "http",
        "traefik.http.routers.rig-http.middlewares": "redirect-to-https",
        "traefik.http.routers.rig-https.rule": api_rule,
        "traefik.http.routers.rig-https.priority": "1000",
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

    async def perform(body, actor=None):
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "perform", perform)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url=PRIVATE_ORIGIN) as client:
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
            await client.delete(path, params=params, headers={"X-Tank-Key": key})


@pytest.mark.asyncio
async def test_recall_work_remember_and_tank_receipts(monkeypatch, tmp_path):
    body = room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="Which sample lamp is available?")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_KEY", uuid.uuid4().hex)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY_RIG", uuid.uuid4().hex)
    monkeypatch.setenv("RIG_MEMORY_ENABLED", "true")
    actor = SignedUser(str(body.tenant_id), "placeholder-rig-owner", "member")
    events, receipts = [], []
    original = httpx.AsyncClient
    def remote(request):
        if request.url.path == "/records":
            assert request.url.params["user_id"] == actor.user_id
            return httpx.Response(200, json={"memories": []})
        if request.url.path == "/recall":
            events.append("recall")
            assert json.loads(request.content)["query"] == "rig.build"
            assert json.loads(request.content)["user_id"] == actor.user_id
            return httpx.Response(200, json={"memories": [{"id": str(uuid.uuid4()), "tenant_id": str(body.tenant_id), "text": "old evidence", "meta": {"user_id": actor.user_id}}]})
        if request.url.path == "/memories":
            events.append("remember")
            assert json.loads(request.content)["tenant_id"] == str(body.tenant_id)
            assert json.loads(request.content)["meta"]["user_id"] == actor.user_id
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
        task = json.loads((work / "request.json").read_text())
        assert task["user_id"] == actor.user_id
        assert task["memories"][0]["text"] == "old evidence"
        (work / "child-receipt.json").write_text(json.dumps({"tenant_id": str(body.tenant_id),
            "task_id": str(body.task_id), "steps": [], "model_receipts": [], "summary": "The sample lamp is available."}))
        return Child()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    result = await service.run_task(body, actor)
    assert events == ["recall", "work", "remember"]
    assert result["status"] == "done"
    assert [r["action"] for r in result["tank_receipts"]] == ["recall", "remember"]
    assert json.loads((service.directory(body.tenant_id, body.task_id) / "receipt.json").read_text()) == result


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_scope", ["tenant", "user"])
async def test_foreign_memory_fails_before_starting_hermes(monkeypatch, tmp_path, foreign_scope):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_KEY", "placeholder-rig-memory-key")
    monkeypatch.setenv("RIG_MEMORY_ENABLED", "true")
    body = room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="Question")
    actor = SignedUser(str(body.tenant_id), "placeholder-rig-owner", "member")
    recalled = []
    def remote(request):
        if request.url.path == "/records":
            return httpx.Response(200, json={"memories": []})
        if request.url.path == "/recall":
            recalled.append(json.loads(request.content))
            return httpx.Response(200, json={"memories": [{"id": str(uuid.uuid4()),
                "tenant_id": str(uuid.uuid4()) if foreign_scope == "tenant" else actor.tenant_id,
                "meta": {"user_id": "placeholder-other-owner" if foreign_scope == "user" else actor.user_id},
                "text": "foreign"}]})
        if request.url.path.endswith("/receipts"):
            return httpx.Response(200, json={"receipts": []})
        raise AssertionError("Unexpected request")
    async def child(*args, **kwargs):
        pytest.fail("Foreign memory reached Hermes")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    original = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(remote)))
    result = await service.run_task(body, actor)
    assert len(recalled) == 1 and recalled[0]["user_id"] == actor.user_id
    assert result["status"] == "failed" and "foreign" not in json.dumps(result)


@pytest.mark.asyncio
async def test_tasks_are_durable_deduplicated_and_tenant_scoped(monkeypatch, tmp_path):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    body = room.Question(tenant_id=uuid.uuid4(), task_id=uuid.uuid4(), home_region="us-east", question="Catalogue question")
    started = []
    async def perform(body, actor=None):
        started.append(body.task_id)
        await asyncio.Event().wait()
    monkeypatch.setattr(service, "perform", perform)
    payload = body.model_dump(mode="json")
    params = {"tenant_id": str(body.tenant_id), "home_region": "us-east"}
    path = f"/tasks/{body.task_id}"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),
                                base_url=PRIVATE_ORIGIN, headers={"X-Tank-Key": key}) as client:
        try:
            assert (await client.post("/tasks", json=payload)).status_code == 202
            await asyncio.sleep(0)
            assert (await client.post("/tasks", json=payload)).status_code == 202
            conflict = await client.post("/tasks", json={**payload, "question": "different"})
            assert conflict.status_code == 409 and len(started) == 1
            missing = await client.get(path, params={**params, "tenant_id": str(uuid.uuid4())})
            assert missing.status_code == 404
        finally:
            await client.delete(path, params=params)
        assert (await client.get(path, params=params)).json()["status"] == "failed"
        assert (await client.post("/tasks", json=payload)).json()["status"] == "failed"
        assert len(started) == 1  # A restart never automatically repeats billed work.
