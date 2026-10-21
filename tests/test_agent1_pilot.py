"""Opt-in managed-cloud ATF fixture pilot; no live model, provider key or site.

AGENT1_PILOT=1 POOL_SCHEMA_DATABASE_URL=<throwaway admin DSN> pytest -q -s ...
AGENT1_PILOT_OUTPUT optionally names the directory for sanitized evidence.
The four tervory-agent1-*:cloud images must already exist. The harness starts the
real Tank app, Base pipeline/callbacks, Hermes memory API and pinned brain. Only
LiteLLM answers, outbound site responses and memory embeddings/store are fixtures.
"""
import asyncio
import json
import os
import secrets
import socket
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

from test_agent1_container_runtime import docker, ready

pytestmark = pytest.mark.skipif(not os.environ.get("AGENT1_PILOT"), reason="Explicit managed-cloud fixture pilot")
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "agents/base/pilot/atf-fixture.json"


@pytest.mark.asyncio
async def test_recorded_atf_fixture_through_real_tank(monkeypatch, tmp_path):
    import asyncpg
    import httpx
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    for path in (ROOT, ROOT / "agents/base"):
        monkeypatch.syspath_prepend(str(path))
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    import base_brain
    import room
    from pipeline import skill_ids

    prefix = "agent1-pilot-" + uuid.uuid4().hex[:10]
    corridor, browser_net, sandbox_net = [prefix + suffix for suffix in ("-gw", "-browser-net", "-sandbox-net")]
    brain, browser, gateway, executor = [prefix + suffix for suffix in ("-brain", "-browser", "-gateway", "-sandbox")]
    data_volume, browser_volume = prefix + "-data", prefix + "-browser-data"
    key, workspace_key, fake_master = (secrets.token_urlsafe(32) for _ in range(3))
    env = dict(os.environ, TANK_KEY=key)
    tenant, other_tenant = uuid.uuid4(), uuid.uuid4()
    events, completions, site_requests = [], [], []
    output = Path(os.environ.get("AGENT1_PILOT_OUTPUT", str(tmp_path / "evidence")))
    output.mkdir(parents=True, exist_ok=True)
    admin = await asyncpg.connect(os.environ["POOL_SCHEMA_DATABASE_URL"])
    db = "agent1_pilot_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{db}"')
    dsn = urlunsplit(urlsplit(os.environ["POOL_SCHEMA_DATABASE_URL"])._replace(path="/" + db))
    tank = server = server_task = skill_http = None
    try:
        for network in (corridor, browser_net, sandbox_net):
            docker("network", "create", "--internal", network)
        for volume in (data_volume, browser_volume):
            docker("volume", "create", volume)
        host = json.loads(docker("network", "inspect", corridor))[0]["IPAM"]["Config"][0]["Gateway"]
        with socket.socket() as sock:
            sock.bind((host, 0))
            port = sock.getsockname()[1]
        origin = f"http://{host}:{port}"
        monkeypatch.setenv("NO_PROXY", "*")
        monkeypatch.setenv("no_proxy", "*")
        for name, value in {"DATABASE_URL": dsn, "LITELLM_MASTER_KEY": fake_master, "TANK_API_KEY": workspace_key,
                            "TANK_KEY_BASE": key, "TANK_KEY": key, "TANK_REGION": "us-east",
                            "LITELLM_URL": origin + "/litellm", "REDIS_URL": "redis://127.0.0.1:1/0"}.items():
            monkeypatch.setenv(name, value)
        import main as tank
        import agent_skills
        monkeypatch.setattr(tank, "DATABASE_URL", dsn)
        monkeypatch.setattr(tank, "LITELLM_URL", origin + "/litellm")
        monkeypatch.setattr(tank, "LITELLM_MASTER_KEY", fake_master)
        monkeypatch.setattr(tank, "TANK_API_KEY", workspace_key)
        monkeypatch.setattr(tank, "SKILL_ENV", {})
        monkeypatch.setattr(tank, "_roster_cache", None)
        monkeypatch.setattr(agent_skills, "SUBMISSIONS", tmp_path / "submissions")
        await tank._startup()
        # Registry fixture, only in this newly created throwaway database. This
        # does not approve or edit packages in any deployment or source tree.
        versions = {}
        async with tank.pool().acquire() as conn:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS agent_base")
            await room.ensure_tables(conn)
            for identity in skill_ids("ffl"):
                version = max((v for i, v in tank._packages if i == identity), key=tank._vkey)
                versions[identity] = version
                await conn.execute("UPDATE tank.skills SET state='approved',approved_at=now() WHERE id=$1 AND version=$2", identity, version)
            await conn.execute("UPDATE tank.policy SET model='fixture-recorded',baseline_model='fixture-baseline' WHERE task_type='agent.base.think'")
            original_skills = await conn.fetch("SELECT * FROM tank.skills ORDER BY id,version")

        # No outbound internet from the skill context: deterministic missing-site
        # fixtures. Internal service calls still go over real HTTP.
        wire = httpx.AsyncHTTPTransport()
        async def outbound(request):
            if request.url.host == host:
                return await wire.handle_async_request(request)
            site_requests.append({"method": request.method, "url": str(request.url), "status": 404})
            return httpx.Response(404, text="Recorded fixture: no public site available", request=request)
        await tank._http.aclose()
        tank._http = httpx.AsyncClient(transport=httpx.MockTransport(outbound), timeout=10)

        class FixtureEmbedding:
            def embed(self, text):
                return [1.0, 0.0] if "previous fixture" in text else [0.0, 1.0]
        memory_app = create_app(InMemoryStore(), FixtureEmbedding())
        base_app, fake = FastAPI(), FastAPI()
        base_brain.register(base_app)
        sandbox_command = """python - <<'CODE'
import json, os
from pathlib import Path
blocked = False
try:
 import socket
 socket.socket()
except (ImportError, OSError): blocked = True
absent = not any(k in os.environ for k in ('TANK_KEY','OPENAI_API_KEY','DOCKER_HOST'))
assert blocked and absent
proof = {'disallowed_host':'1.1.1.1:443','connection_refused':blocked,'credentials_absent':absent,'network':'none','work_volume':'Base only'}
Path('/workspace/sandbox-proof.json').write_text(json.dumps(proof))
print(json.dumps(proof))
CODE"""
        answers = [
            {"tool": "pipeline_run", "arguments": {}},
            {"tool": "browser", "arguments": {"url": "http://169.254.169.254"}},
            {"tool": "sandbox", "arguments": {"command": sandbox_command}},
            {"content": "Processed two synthetic Delaware ATF-format rows through Base's existing pipeline. No public websites were found in the recorded fixtures. Browser refusal and sandbox isolation were checked; no live data enrichment is claimed."},
        ]

        @fake.get("/model/info")
        async def roster():
            return {"data": [{"model_name": name, "litellm_params": {"model": name},
                    "model_info": {"input_cost_per_token": rate, "output_cost_per_token": rate * 2}}
                    for name, rate in (("fixture-recorded", 0.000001), ("fixture-baseline", 0.000002))]}

        @fake.post("/v1/chat/completions")
        async def completion(request: Request):
            assert request.headers["authorization"] == "Bearer " + fake_master
            body = await request.json()
            assert body["model"] == "fixture-recorded"
            index = len(completions)
            assert index < len(answers), "Unexpected extra model call"
            answer = answers[index]
            message = {"role": "assistant", "content": answer.get("content")}
            if "tool" in answer:
                message["tool_calls"] = [{"id": "fixture_call_" + str(index), "type": "function", "function": {
                    "name": answer["tool"], "arguments": json.dumps(answer["arguments"])}}]
            completions.append({"request": body, "recorded_answer": message})
            return JSONResponse({"id": "fixture_" + str(index), "object": "chat.completion", "created": 1,
                "model": body["model"], "choices": [{"index": 0, "message": message,
                "finish_reason": "tool_calls" if "tool" in answer else "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}},
                headers={"x-litellm-response-cost": "0.000140"})

        api = FastAPI()
        @api.middleware("http")
        async def record(request, call_next):
            # Never write credentials; compare them in memory and record a bool.
            event = {"sequence": len(events) + 1, "method": request.method, "path": request.url.path,
                     "room_key_valid": request.headers.get("x-tank-key") == key or request.headers.get("authorization") == "Bearer " + key}
            if request.headers.get("x-tenant-id"):
                event["tenant_id"] = request.headers["x-tenant-id"]
            events.append(event)
            response = await call_next(request)
            event["status"] = response.status_code
            return response
        api.mount("/memory", memory_app)
        api.mount("/base", base_app)
        api.mount("/litellm", fake)
        api.mount("/", tank.app)
        server = uvicorn.Server(uvicorn.Config(api, host=host, port=port, access_log=False, log_level="warning", lifespan="off"))
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            if server_task.done():
                await server_task
            await asyncio.sleep(0.05)

        docker("run", "-d", "--name", executor, "--network", sandbox_net, "--network-alias", "base-sandbox",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--pids-limit", "64",
               "--memory", "512m", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m",
               "--tmpfs", "/work:rw,nosuid,nodev,size=128m,uid=1000,gid=1000,mode=0700", "tervory-agent1-sandbox:cloud")
        await asyncio.to_thread(ready, executor, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health')"])
        for name, alias, image, volume in ((browser, "base-browser", "browser", browser_volume), (gateway, "base-browser-gateway", "gateway", None)):
            args = ["run", "-d", "--name", name, "--network", browser_net, "--network-alias", alias,
                    "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-e", "TANK_KEY",
                    "-v", str(ROOT / "agents/_brain") + ":/app/brain:ro"]
            if volume:
                args += ["-v", volume + ":/browser-data"]
            docker(*args, "tervory-agent1-" + image + ":cloud", env=env)
        docker("network", "connect", corridor, gateway)
        for container in (browser, gateway):
            await asyncio.to_thread(ready, container, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/health')"])
        docker("run", "-d", "--name", brain, "--network", corridor, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "-e", "TANK_KEY", "-e", "TANK_URL=" + origin, "-e", "BASE_ROOM_URL=" + origin + "/base",
               "-e", "HERMES_URL=" + origin + "/memory", "-e", "BASE_BROWSER_URL=http://base-browser-gateway:3000",
               "-e", "BASE_SANDBOX_URL=http://base-sandbox:8002", "-v", data_volume + ":/data",
               "-v", str(ROOT / "agents/_brain") + ":/app/brain:ro", "tervory-agent1-brain:cloud", env=env)
        docker("network", "connect", sandbox_net, brain)
        await asyncio.to_thread(ready, brain, ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health')"])
        inspect = {name: json.loads(docker("inspect", name))[0] for name in (brain, browser, gateway, executor)}
        brain_url = "http://" + inspect[brain]["NetworkSettings"]["Networks"][corridor]["IPAddress"] + ":8001"
        monkeypatch.setenv("BASE_BRAIN_URL", brain_url)
        skill_http = httpx.AsyncClient(timeout=120)
        skills = room.SkillClient(skill_http, origin, key)
        fixture = json.loads(FIXTURE.read_text())
        async with tank.pool().acquire() as conn:
            row = await room.insert_batch(conn, tenant, "cloud-fixture", "Delaware ATF-format sandbox fixture", fixture["records"], "", False, "ffl", 1, None)
        task = row["id"]
        async with tank.pool().acquire() as conn:
            cfg = json.loads(await conn.fetchval("SELECT input FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2", tenant, task))
        cfg["refs"] = {i: i + "@" + v for i, v in versions.items()}
        cfg["engine_data_version"] = versions["ffl.profile"]
        # Seed one memory for this tenant and one decoy for another tenant.
        async with httpx.AsyncClient(headers={"X-Tank-Key": key}) as client:
            for owner in (tenant, other_tenant):
                result = await client.post(origin + "/memory/memories", json={"tenant_id": str(owner),
                    "text": "previous fixture: preserve unknown websites", "kind": "base.task", "source": "fixture:previous"})
                assert result.status_code == 201
            exported = (await client.get(origin + "/v1/agents/base/skills", params={"tenant_id": str(tenant)})).json()
        # Drop setup events from the task recording; recall must now be first.
        events.clear()
        try:
            await base_brain.drive_batch(tank.pool(), skills, task, cfg, skills.bind(versions, False, str(tenant)))
        except Exception:
            debug = json.dumps({"cfg": cfg, "events": events, "model_exchanges": completions}, indent=2, default=str)
            assert all(secret not in debug for secret in (key, workspace_key, fake_master))
            (tmp_path / "failure.json").write_text(debug)
            raise
        receipt = cfg["brain_receipt"]
        assert receipt["status"] == "done", receipt
        assert receipt["steps"][0]["action"] == "recall" and receipt["steps"][0]["count"] == 1
        assert receipt["steps"][-1]["action"] == "remember"
        assert len(completions) == 4
        chat_calls = [e for e in events if e["path"] == "/v1/agents/base/chat/completions"]
        assert len(chat_calls) == 4 and all(e["room_key_valid"] and e["status"] == 200 for e in chat_calls)
        assert events[0]["path"] == "/memory/recall" and events[-1]["path"] == "/memory/memories"
        assert all(r["baseline_cost_usd"] == pytest.approx(0.00028) and r["cost_usd"] == pytest.approx(0.00014) for r in receipt["model_receipts"])
        exported_ids = sorted(s["id"] + "@" + s["version"] for s in exported["skills"])
        assert sorted(receipt["steps"][1]["approved"]) == exported_ids
        disk_skills = json.loads(docker("exec", brain, "python", "-c",
            "import json; from pathlib import Path; print(json.dumps(sorted(p.parent.name for p in Path('/data/tenants/" + str(tenant) + "/hermes/skills').glob('*/SKILL.md'))))"))
        assert disk_skills == sorted(s["name"] for s in exported["skills"])
        sandbox_proof = json.loads(docker("exec", brain, "cat", f"/data/tenants/{tenant}/runs/{task}/work/sandbox-proof.json"))
        assert sandbox_proof["connection_refused"] and sandbox_proof["credentials_absent"]
        browser_proof = json.loads(docker("exec", browser, "python", "-c", """import asyncio,json
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True)
  page=await b.new_page(); await page.set_content('<h1>Base private fixture browser</h1>')
  assert await page.locator('h1').inner_text()=='Base private fixture browser'
  print(json.dumps({'chromium_started':True,'fixture_page_rendered':True})); await b.close()
asyncio.run(main())"""))
        browser_gateway_url = "http://" + inspect[gateway]["NetworkSettings"]["Networks"][corridor]["IPAddress"] + ":3000"
        async with httpx.AsyncClient() as client:
            refused = await client.post(browser_gateway_url + "/render", headers={"X-Tank-Key": key,
                "X-Tenant-ID": str(tenant), "X-Home-Region": "us-east", "X-Task-ID": str(task)},
                json={"url": "http://169.254.169.254"})
        assert refused.status_code == 403
        browser_proof["disallowed_url"] = "http://169.254.169.254"
        browser_proof["refused_status"] = refused.status_code
        assert set(inspect[browser]["NetworkSettings"]["Networks"]) == {browser_net}
        assert all("tiger" not in network for entry in inspect.values() for network in entry["NetworkSettings"]["Networks"])
        async with tank.pool().acquire() as conn:
            ledger = [dict(r) for r in await conn.fetch("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND task_id=$2 ORDER BY ts", tenant, task)]
            transcripts = [dict(r) for r in await conn.fetch(
                "SELECT t.ledger_id,t.tenant_id,t.task_type,jsonb_array_length(t.messages) AS message_count "
                "FROM tank.transcripts t JOIN tank.ledger l ON l.id=t.ledger_id "
                "WHERE t.tenant_id=$1 AND l.tenant_id=$1 AND l.task_id=$2", tenant, task)]
            records = [dict(r) for r in await conn.fetch("SELECT id,raw,profile,passes,confidence,status FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 ORDER BY created_at", tenant, task)]
            assert original_skills == await conn.fetch("SELECT * FROM tank.skills ORDER BY id,version")
        assert len(transcripts) == 4 and {r["ledger_id"] for r in transcripts} == {r["id"] for r in ledger}
        assert len(ledger) == 4 and len(records) == 2 and all(r["status"] == "done" for r in records)
        containers = []  # Never include raw Docker environment values.
        for role, name in (("brain", brain), ("browser", browser), ("browser_gateway", gateway), ("sandbox", executor)):
            entry = inspect[name]
            assert not entry["HostConfig"]["Privileged"] and not entry["HostConfig"].get("CapAdd")
            assert entry["HostConfig"].get("PidMode", "") in {"", "private"}
            assert entry["HostConfig"].get("NetworkMode") != "host"
            assert not any(v.split("=",1)[0] in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LITELLM_MASTER_KEY"} for v in entry["Config"]["Env"])
            containers.append({"role": role, "name": name, "image": entry["Config"]["Image"], "image_id": entry["Image"],
                "networks": list(entry["NetworkSettings"]["Networks"]),
                "volumes": [{"name": m.get("Name"), "destination": m["Destination"]} for m in entry["Mounts"] if m["Type"] == "volume"],
                "privileged": False, "cap_add": [], "read_only": entry["HostConfig"]["ReadonlyRootfs"],
                "pid_mode": entry["HostConfig"].get("PidMode", ""), "provider_credentials_absent": True})
        recording = {"recorded_at": datetime.now(timezone.utc).isoformat(), "kind": "sandbox fixture; not a live ATF run",
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "fixture": fixture["description"], "tenant_id": str(tenant), "task_id": str(task),
            "substitutions": ["Recorded LiteLLM answers and synthetic prices; real provider spend is zero", "Recorded missing-site HTTP responses", "Hermes InMemoryStore and deterministic local embeddings", "Skala approved registry seeded only in a fresh throwaway database"],
            "events": list(events), "model_exchanges": completions, "ledger": ledger, "transcripts": transcripts, "approved_export": exported,
            "loaded_skill_folders": disk_skills, "existing_skill_versions_unchanged": True,
            "records": records, "site_fixtures": site_requests, "containers": containers,
            "sandbox": sandbox_proof, "browser": browser_proof}
        # Real default-pipeline fallback with the brain endpoint unavailable.
        # It must process the rows without another model call or a second start.
        monkeypatch.setenv("BASE_BRAIN_URL", origin + "/unavailable-brain")
        fallback_start = len(events)
        async with tank.pool().acquire() as conn:
            fallback_task = await room.insert_batch(conn, tenant, "cloud-fixture", "Brain unavailable fallback fixture",
                fixture["records"], "", False, "ffl", 1, None)
            fallback_cfg = json.loads(await conn.fetchval("SELECT input FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2", tenant, fallback_task["id"]))
        fallback_cfg["refs"] = cfg["refs"]
        fallback_cfg["engine_data_version"] = cfg["engine_data_version"]
        await base_brain.drive_batch(tank.pool(), skills, fallback_task["id"], fallback_cfg,
            skills.bind(versions, False, str(tenant)))
        async with tank.pool().acquire() as conn:
            fallback_count = await conn.fetchval("SELECT count(*) FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 AND status='done'",tenant,fallback_task["id"])
            fallback_status = await conn.fetchval("SELECT status FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2",tenant,fallback_task["id"])
        assert fallback_status == "done" and fallback_count == 2 and len(completions) == 4
        fallback = {"task_id": str(fallback_task["id"]), "tenant_id": str(tenant), "status": fallback_status,
            "processed": fallback_count, "receipt": fallback_cfg["brain_receipt"], "events": events[fallback_start:],
            "additional_model_calls": 0}
        assert fallback["receipt"]["status"] == "fallback"
        for name, value in (("recording.json", recording), ("receipt.json", receipt), ("fallback.json", fallback)):
            content = json.dumps(value, indent=2, default=str) + "\n"
            assert all(secret not in content for secret in (key, workspace_key, fake_master))
            (output / name).write_text(content)
        print("Pilot recorded:", output)
    finally:
        if skill_http:
            await skill_http.aclose()
        if server:
            server.should_exit = True
        if server_task:
            await server_task
        if tank and tank._pool:
            await tank._shutdown()
        if "wire" in locals():
            await wire.aclose()
        for container in (brain, browser, gateway, executor):
            subprocess.run(["docker", "rm", "-fv", container], capture_output=True)
        for volume in (data_volume, browser_volume):
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
        for network in (corridor, browser_net, sandbox_net):
            subprocess.run(["docker", "network", "rm", network], capture_output=True)
        await admin.execute(f'DROP DATABASE "{db}" WITH (FORCE)')
        await admin.close()
