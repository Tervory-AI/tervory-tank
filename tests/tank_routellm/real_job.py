"""Local proof: unmodified uvicorn main:app, Postgres, CPU BERT, fake gateway.

No remote model is called. The simulated gateway's costs are test inputs, not
production savings. The actual Tank writes and reports the resulting receipts.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).parent / "evidence"


class Gateway(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"model_name": name, "litellm_params": {"model": f"openai/{name}"},
            "model_info": {"input_cost_per_token": cost, "output_cost_per_token": cost}}
            for name, cost in [("sol", .002), ("flash-lite", .0002), ("luna", .0001)]]}).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = body["model"]
        answer, cost = {"sol": ("The answer is four.", ".02"),
                        "flash-lite": ("Four.", ".002"), "luna": ("100", ".001")}[model]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("x-litellm-response-cost", cost)
        self.send_header("x-litellm-model-group", model)
        self.end_headers()
        self.wfile.write(json.dumps({"choices": [{"message": {"content": answer}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode())


@contextmanager
def services(database: str):
    gateway = ThreadingHTTPServer(("127.0.0.1", 0), Gateway)
    thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "DATABASE_URL": database, "TANK_API_KEY": "local-routellm-test",
           "LITELLM_MASTER_KEY": "local-provider-stub", "LITELLM_URL": f"http://127.0.0.1:{gateway.server_port}",
           "TERVORY_ADMIN_USER_IDS": "local-founder", "TANK_REGION": "us-east", "REDIS_URL": "redis://127.0.0.1:1/0",
           "TANK_SHADOW_BUDGET_USD": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    OUTPUT.mkdir(exist_ok=True)
    with (OUTPUT / "startup.log").open("w+") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT / "tank", env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=20,
                              headers={"X-Tank-Key": "local-routellm-test", "X-Tervory-Admin": "local-founder"}) as client:
                for _ in range(120):
                    if process.poll() is not None:
                        raise RuntimeError("Tank exited; inspect startup.log")
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.25)
                else:
                    raise RuntimeError("Tank did not become healthy")
                yield client
        finally:
            process.terminate()
            process.wait(timeout=30)
            gateway.shutdown()
            gateway.server_close()
            thread.join(timeout=5)


async def job(url: str):
    if urlsplit(url).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("proof requires local disposable Postgres")
    admin = await asyncpg.connect(url)
    name = "routellm_job_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    target = urlunsplit(urlsplit(url)._replace(path="/" + name))
    try:
        with services(target) as client:
            db = await asyncpg.connect(target)
            try:
                a, b = uuid.uuid4(), uuid.uuid4()
                for tenant in (a, b):
                    await db.execute("INSERT INTO tank.policy(tenant_id,task_type,model,shadow_rate) VALUES($1,'routellm.proof','sol',1)", tenant)
                await db.execute("UPDATE tank.policy SET model='luna' WHERE task_type='tank.judge'")
                body = {"tenant_id": str(a), "routellm_weak_model": "flash-lite", "routellm_threshold": 1}
                response = client.put("/v1/policy/routellm.proof/routellm", json=body)
                assert response.status_code == 200, response.text
                for tenant in (a, b):
                    response = client.post("/v1/route", json={"tenant_id": str(tenant), "task_type": "routellm.proof",
                        "messages": [{"role": "user", "content": "What is two plus two?"}]})
                    assert response.status_code == 200, response.text
                    assert response.json()["model"] == "sol" and response.json()["content"] == "The answer is four."
                for _ in range(120):
                    row = await db.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND task_type='routellm.proof'", a)
                    if row["routellm_status"] in {"sampled", "unavailable", "sample_failed"}:
                        break
                    await asyncio.sleep(.25)
                assert row["routellm_status"] == "sampled", row["routellm_status"]
                first = client.get("/v1/proof", params={"tenant_id": str(a)}).json()
                second = client.get("/v1/proof", params={"tenant_id": str(b)}).json()
                pair = next(t for t in first["tasks"] if t["task_type"] == "routellm.proof")["shadow_pairs"][0]
                assert pair["saved_usd"] == .018 and pair["agreement"] == 1
                assert second["shadows"] == [] and all(not t["shadow_pairs"] for t in second["tasks"])
                assert await db.fetchval("SELECT model FROM tank.policy WHERE tenant_id=$1 AND task_type='routellm.proof'", a) == "sol"
                first.update(tenant_names={str(a): "Tervory", str(b): "Another account"}, tenant_names_note=None)
                (OUTPUT / "report.json").write_text(json.dumps(first, indent=2))
                result = {"result": "passed", "environment": "local, simulated gateway costs", "router": "real CPU BERT",
                    "score": row["routellm_score"], "chosen": row["routellm_model"], "live_model": "sol",
                    "agreement": pair["agreement"], "primary_cost_usd": pair["primary_cost_usd"],
                    "candidate_cost_usd": pair["could_have_cost_usd"], "sample_savings_usd": pair["saved_usd"],
                    "second_tenant_samples": 0, "live_policy_unchanged": True}
                (OUTPUT / "job.json").write_text(json.dumps(result, indent=2)+"\n")
                print(json.dumps(result, indent=2))
            finally:
                await db.close()
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


if __name__ == "__main__":
    asyncio.run(job(os.environ["POOL_SCHEMA_DATABASE_URL"]))
