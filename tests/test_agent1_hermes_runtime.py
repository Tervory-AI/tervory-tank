"""Opt-in cloud smoke test using the actual pinned Hermes image and a fake model.

AGENT1_HERMES_IMAGE=tervory-agent1-brain:cloud pytest -q tests/test_agent1_hermes_runtime.py
This is protocol evidence, never a claimed live model/ATF pilot.
"""
import asyncio
import json
import os
import subprocess
import threading
import uuid
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_skills


@pytest.mark.skipif(not os.environ.get("AGENT1_HERMES_IMAGE"), reason="Pinned Hermes image is an explicit cloud check")
def test_actual_hermes_calls_pipeline_via_tank_with_receipts(tmp_path, monkeypatch):
    tenant, task, key = str(uuid.uuid4()), str(uuid.uuid4()), uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_BASE", key)
    calls, errors, rows = [], [], []

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield self
        @asynccontextmanager
        async def transaction(self):
            yield
        async def execute(self, sql, *args):
            rows.append((sql, args))

    pool = Pool()
    async def policy(*args):
        return {"model": "policy", "rung": 1, "priority": "standard", "max_tokens_out": 4096}
    async def roster():
        return [{"model_name": "policy", "model_info": {"input_cost_per_token": 0, "output_cost_per_token": 0}}]
    tank = SimpleNamespace(pool=lambda: pool, load_policy=policy, _roster_models=roster,
        graduate=SimpleNamespace(router_cannot_serve=lambda m: False), LITELLM_MASTER_KEY=uuid.uuid4().hex)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, value, status=200, extra=None):
            content = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(content)
        def do_GET(self):
            if self.path.startswith("/v1/agents/base/skills?"):
                self.reply({"room": "base", "tenant_id": tenant, "region": "us-east", "skills": []})
            elif self.path.startswith("/v1/agents/base/receipts?"):
                self.reply({"receipts": [json.loads(a[2]) for sql, a in rows if "agent_receipts" in sql]})
            elif self.path.endswith(("/models", "/version", "/api/tags", "/props")):
                # Hermes probes localhost custom endpoints for capabilities. Tank
                # intentionally does not expose these optional discovery routes.
                self.reply({}, 404)
            else:
                errors.append("Unexpected GET " + self.path.split("?")[0])
                self.reply({}, 404)
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            try:
                if self.path == "/v1/agents/base/chat/completions":
                    agent_skills.room_key("base", self.headers.get("Authorization", ""))
                    assert self.headers["X-Tenant-ID"] == tenant
                    assert self.headers["X-Task-ID"] == task
                    result = asyncio.run(agent_skills.complete(tank, agent_skills.Chat(**body), uuid.UUID(tenant), uuid.UUID(task), "us-east"))
                    if body.get("stream"):
                        content = "".join(agent_skills.stream_completion(result)).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Content-Length", str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                    else:
                        self.reply(result)
                elif self.path == "/v1/chat/completions":
                    names = {tool["function"]["name"] for tool in body["tools"]}
                    expected = {"pipeline_run", "skala_run", "browser", "sandbox", "candidate_submit", "retry_record"}
                    if names != expected:
                        raise AssertionError("Actual Hermes tools: " + repr(sorted(names)))
                    calls.append(body)
                    done = any(m.get("role") == "tool" for m in body["messages"])
                    message = {"role": "assistant", "content": "The pipeline completed." if done else None}
                    if not done:
                        message["tool_calls"] = [{"id": "call_pipeline", "type": "function", "function": {"name": "pipeline_run", "arguments": "{}"}}]
                    self.reply({"id": "mock-model", "object": "chat.completion", "created": 1, "model": "policy",
                        "choices": [{"index": 0, "message": message, "finish_reason": "stop" if done else "tool_calls"}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}, extra={"x-litellm-response-cost": "0"})
                elif self.path == "/brain/pipeline":
                    assert body in ({"tenant_id": tenant, "task_id": task}, {"tenant_id": tenant, "task_id": task, "finish": True})
                    self.reply({"pipeline_status": "done", "summary": "Cloud fixture processed", "unresolved": [], "cost_usd": 0})
                else:
                    raise AssertionError("Unexpected POST " + self.path)
            except Exception as exc:
                errors.append(type(exc).__name__ + ": " + str(exc))
                self.reply({"error": {"message": "Cloud test request failed"}}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    endpoint = "http://127.0.0.1:" + str(server.server_port)
    tank.LITELLM_URL = endpoint
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    work = tmp_path / "tenants" / tenant / "runs" / task
    work.mkdir(parents=True)
    (work / "request.json").write_text(json.dumps({"tenant_id": tenant, "task_id": task, "batch": "cloud protocol fixture", "count": 1, "memories": []}))
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, TANK_KEY=key, TANK_URL=endpoint, BASE_ROOM_URL=endpoint, NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    args = ["docker", "run", "--rm", "--network=host", "-v", str(tmp_path) + ":/data",
            "-v", str(root / "agents/_brain") + ":/app/brain:ro", "-e", "TANK_KEY", "-e", "TANK_URL", "-e", "BASE_ROOM_URL",
            "-e", "NO_PROXY", "-e", "no_proxy", "-e", "HERMES_HOME=/data/tenants/" + tenant + "/hermes",
            os.environ["AGENT1_HERMES_IMAGE"], "python", "-m", "brain.runner", "/data/tenants/" + tenant + "/runs/" + task]
    try:
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
        (tmp_path / "runtime.log").write_text((result.stdout + result.stderr).replace(key, "[room-key]"))
        (tmp_path / "requests.json").write_text(json.dumps({"errors": errors, "calls": calls}, indent=2))
        assert result.returncode == 0, (result.stderr[-5000:], errors)
        receipt = json.loads((work / "receipt.json").read_text())
        assert errors == []
        assert len(calls) == 2
        assert len(receipt["model_receipts"]) == 2
        assert [r["action"] for r in receipt["steps"][-2:]] == ["pipeline_run", "pipeline_continue"]
        assert all(r["tenant_id"] == tenant and r["task_id"] == task for r in receipt["model_receipts"])
    finally:
        server.shutdown()
        server.server_close()
