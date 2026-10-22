"""Opt-in cloud test: real pinned Hermes, real sample catalogue, fake model only.

RIG2_HERMES_IMAGE=tervory-rig-brain:cloud pytest -q tests/test_rig_box_runtime.py
No production credentials or paid model calls are used.
"""
import asyncio
import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

import agent_skills
from test_agent1_brain_route import Pool

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.environ.get("RIG2_HERMES_IMAGE"), reason="Explicit pinned-Hermes cloud check")
def test_real_hermes_answers_from_standin_catalogue_with_tank_receipts(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "agents/rig"))
    from rigbox.service import Service
    from rigbox.store import MemoryStore
    catalogue = Service(MemoryStore())
    loaded = asyncio.run(catalogue.load_folder(ROOT / "agents/rig/catalogues/second"))
    tenant, task, key = loaded["tenant_id"], str(uuid.uuid4()), uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_RIG", key)
    pool = Pool()
    monkeypatch.setattr(agent_skills.controls, "db", lambda: pool)
    async def policy(kind, own):
        assert kind == "agent.rig.think" and str(own) == tenant
        return {"model": "luna", "rung": 1, "priority": "standard", "max_tokens_out": 4096}
    async def roster():
        return [{"model_name": name, "litellm_params": {"model": "openai/fixture"},
                 "model_info": {"input_cost_per_token": .001, "output_cost_per_token": .002}} for name in ("luna", "baseline")]
    tank = SimpleNamespace(pool=lambda: pool, load_policy=policy, _roster_models=roster,
        model_call_refusal=lambda *a, **kw: None, graduate=SimpleNamespace(router_cannot_serve=lambda model: False),
        LITELLM_MASTER_KEY=uuid.uuid4().hex)
    calls, errors, steps = [], [], []
    skill = {"id": "rig.search", "version": "1.0.1", "name": "rig-search-v1-0-1", "agent": "rig", "state": "approved",
        "files": {"SKILL.md": "Search only this tenant's sample catalogue."},
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def reply(self, data, status=200, content_type="application/json"):
            raw = (data if isinstance(data, str) else json.dumps(data)).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def authorize(self):
            agent_skills.room_key("rig", self.headers.get("Authorization", ""), self.headers.get("X-Tank-Key", ""))
        def do_GET(self):
            try:
                if urlsplit(self.path).path not in {"/v1/agents/rig/skills", "/v1/agents/rig/receipts"}:
                    # Hermes probes backend metadata. Tank has no such routes;
                    # mirror its 404 without pretending the probes are skills.
                    self.reply({"detail": "Not Found"}, 404)
                    return
                self.authorize()
                query = parse_qs(urlsplit(self.path).query)
                assert query["tenant_id"] == [tenant]
                if self.path.startswith("/v1/agents/rig/skills?"):
                    self.reply({"tenant_id": tenant, "room": "rig", "region": "us-east", "skills": [skill]})
                elif self.path.startswith("/v1/agents/rig/receipts?"):
                    assert query["task_id"] == [task]
                    models = [json.loads(args[2]) for sql, args in pool.rows if "INSERT INTO tank.agent_receipts" in sql]
                    self.reply({"receipts": [*steps, *models]})
                else:
                    raise AssertionError("Unexpected GET")
            except Exception as exc:
                errors.append(urlsplit(self.path).path + ":" + type(exc).__name__)
                self.reply({"error": "Fixture request failed"}, 400)
        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                if self.path == "/v1/chat/completions":
                    assert self.headers.get("Authorization") == "Bearer " + tank.LITELLM_MASTER_KEY
                    assert {t["function"]["name"] for t in body["tools"]} == {"skala_run", "browser", "sandbox"}
                    calls.append(body)
                    finished = any(m.get("role") == "tool" for m in body["messages"])
                    message = {"role": "assistant", "content": "The sample catalogue contains Second Desk Lamp." if finished else None}
                    if finished:
                        assert any("Second Desk Lamp" in str(m.get("content")) for m in body["messages"] if m.get("role") == "tool")
                    else:
                        message["tool_calls"] = [{"id": "catalogue_lookup", "type": "function", "function": {"name": "skala_run",
                            "arguments": json.dumps({"skill_id": "rig.search", "version": "1.0.1", "input": {"query": "lamp"}})}}]
                    self.reply({"id": "fixture-model", "object": "chat.completion", "created": 1, "model": "luna",
                        "choices": [{"index": 0, "message": message, "finish_reason": "stop" if finished else "tool_calls"}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
                    return
                self.authorize()
                assert self.headers.get("X-Tenant-ID") == tenant and self.headers.get("X-Task-ID") == task
                if self.path == "/v1/agents/rig/chat/completions":
                    result = asyncio.run(agent_skills.complete(tank, agent_skills.Chat(**body), uuid.UUID(tenant), uuid.UUID(task), "us-east", room="rig"))
                    if body.get("stream"):
                        self.reply("".join(agent_skills.stream_completion(result)), content_type="text/event-stream")
                    else:
                        self.reply(result)
                elif self.path == "/v1/agents/rig/skills/rig.search/run":
                    assert body["tenant_id"] == tenant and body["task_id"] == task and body["version"] == "1.0.1"
                    self.reply(asyncio.run(catalogue.search(tenant, body["input"]["query"], 5)))
                elif self.path == "/v1/agents/rig/steps":
                    assert body["tenant_id"] == tenant and body["task_id"] == task
                    step = {**body, "ledger_id": body["id"], "room": "rig"}
                    steps.append(step)
                    self.reply(step)
                else:
                    raise AssertionError("Unexpected POST")
            except Exception as exc:
                errors.append(urlsplit(self.path).path + ":" + type(exc).__name__)
                self.reply({"error": "Fixture request failed"}, 400)

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    tank.LITELLM_URL = "http://127.0.0.1:" + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Docker's host gateway reaches only this local fixture; no host networking.
    endpoint = "http://rig-test-host:" + str(server.server_port)
    request = {"tenant_id": tenant, "task_id": task, "home_region": "us-east", "question": "Which sample lamp is available?", "memories": []}
    (tmp_path / "request.json").write_text(json.dumps(request))
    docker = os.environ.get("RIG2_DOCKER", "docker")
    container = "rig2-protocol-" + uuid.uuid4().hex[:12]
    env = dict(os.environ, TANK_KEY=key, TANK_URL=endpoint)
    args = [docker, "run", "--name", container, "--add-host", "rig-test-host:host-gateway",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--memory", "2g", "--cpus", "1",
        "-e", "TANK_KEY", "-e", "TANK_URL", "-e", "NO_PROXY=rig-test-host", "-e", "no_proxy=rig-test-host",
        "-e", "HERMES_HOME=/data/hermes", os.environ["RIG2_HERMES_IMAGE"],
        "sh", "-c", "cat > /data/request.json && python -m rig_brain.runner /data"]
    # stdin avoids mounting pytest's permission-restricted directory into the image.
    args.insert(2, "-i")
    try:
        result = subprocess.run(args, env=env, input=json.dumps(request), capture_output=True, text=True, timeout=120)
        safe_log = (result.stdout + result.stderr).replace(key, "[room key]")
        (tmp_path / "runtime.log").write_text(safe_log)
        assert result.returncode == 0, (safe_log[-4000:], errors)
        copied = subprocess.run([docker, "cp", container + ":/data/child-receipt.json", str(tmp_path / "receipt.json")], capture_output=True, text=True)
        assert copied.returncode == 0, copied.stderr
        receipt = json.loads((tmp_path / "receipt.json").read_text())
        assert not errors and len(calls) == 2
        assert "Second Desk Lamp" in receipt["summary"]
        assert [step["action"] for step in receipt["steps"]] == ["skills", "skala_run"]
        assert len(receipt["model_receipts"]) == 2
        assert all(r["task_type"] == "agent.rig.think" and r["tenant_id"] == tenant and r["task_id"] == task for r in receipt["model_receipts"])
    finally:
        subprocess.run([docker, "rm", "-f", container], capture_output=True)
        server.shutdown()
        server.server_close()
