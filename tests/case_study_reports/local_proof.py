"""Run the real Tank on disposable local PostgreSQL; no model or live service."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[2]
A = "ca5e0000-0000-4000-8000-000000000001"
B = "ca5e0000-0000-4000-8000-000000000002"


async def sql(dsn, statement, *args):
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.execute(statement, *args)
    finally:
        await conn.close()


def run():
    admin = os.environ["POOL_SCHEMA_DATABASE_URL"]
    parts = urlsplit(admin)
    assert parts.hostname in {"127.0.0.1", "localhost"}
    name = "case_study_proof_" + uuid.uuid4().hex
    dsn = urlunsplit((parts.scheme, parts.netloc, "/" + name, "", ""))
    asyncio.run(sql(admin, f'CREATE DATABASE "{name}"'))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = None
    with tempfile.TemporaryFile(mode="w+") as log:
        try:
            env = {"PATH": os.environ["PATH"], "DATABASE_URL": dsn, "TANK_API_KEY": "dummy-proof",
                   "LITELLM_MASTER_KEY": "dummy-unused", "LITELLM_URL": "http://127.0.0.1:9",
                   "REDIS_URL": "redis://127.0.0.1:9/0", "TERVORY_ADMIN_USER_IDS": "offline-founder",
                   "TANK_REGION": "us-east", "PYTHONUNBUFFERED": "1"}
            proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
                                    cwd=ROOT / "tank", env=env, stdout=log, stderr=subprocess.STDOUT)
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=10) as client:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("Tank exited during startup")
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.2)
                else:
                    raise RuntimeError("Tank startup timed out")
                def request(method, path, tenant=A, user="offline-client", **kwargs):
                    return client.request(method, path, headers={"X-Tank-Key": "dummy-proof",
                        "X-Tervory-Tenant": tenant, "X-Tervory-User": user}, **kwargs)
                for tenant in (A, B):
                    assert request("POST", "/v1/case-studies/ensure", tenant).status_code == 200
                    assert request("PUT", "/v1/command/squads/base", tenant, "offline-founder", json={"enabled": True}).status_code == 200
                empty = request("GET", "/v1/case-studies/base").json()
                assert all(f["value"] == 0 for f in [*empty["tank"], *empty["figures"]] if f["type"] == "number")
                asyncio.run(sql(dsn, """INSERT INTO tank.ledger(tenant_id,agent,task_type,rung,model,cost_usd)
                    VALUES($1,'base','base.offline',2,'offline',2)""", uuid.UUID(A)))
                first = request("GET", "/v1/case-studies/base").json()
                second = request("GET", "/v1/case-studies/base", B).json()
                spend = lambda report: next(f["value"] for f in report["tank"] if f["id"] == "tank.spend")
                assert spend(first) == 2 and spend(second) == 0
                refused = request("GET", "/v1/case-studies/base", params={"tenant_id": B})
                assert refused.status_code == 403
                assert request("GET", "/v1/case-studies/base", A, "offline-founder", params={"tenant_id": B}).status_code == 200
                index = request("GET", "/v1/case-studies/clients", A, "offline-founder").json()
                assert {row["tenant_id"] for row in index["clients"]} == {A, B}
                print(json.dumps({"real_tank": True, "initial_numbers_zero": True,
                    "tenant_a_spend": spend(first), "tenant_b_spend": spend(second),
                    "cross_tenant_status": refused.status_code, "founder_clients": len(index["clients"]),
                    "report": first}, indent=2))
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            log.seek(0)
            output = log.read()
            print("Tank startup and request tail:")
            print("\n".join(output.splitlines()[-28:]))
            asyncio.run(sql(admin, f'DROP DATABASE "{name}" WITH (FORCE)'))
    assert "Application startup complete" in output
    assert "Traceback" not in output


if __name__ == "__main__":
    run()
