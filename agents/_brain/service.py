"""One isolated Hermes process per Base task; recall and remember bracket work."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from brain.security import authenticate, scope, tenant_dir

app = FastAPI()
gate = asyncio.Semaphore(1)


class Run(BaseModel):
    tenant_id: uuid.UUID
    task_id: uuid.UUID
    home_region: str
    batch: str = Field(min_length=1, max_length=120)
    count: int = Field(ge=1, le=100000)
    engine: str | None = None


async def memory(client: httpx.AsyncClient, path: str, payload: dict) -> dict:
    response = await client.post(os.environ.get("HERMES_URL", "http://hermes:8000") + path, json=payload)
    if response.status_code not in (200, 201):
        raise RuntimeError("Base memory is unavailable")
    return response.json()


async def run_task(body: Run) -> dict:
    tenant = scope(str(body.tenant_id), body.home_region)
    root = tenant_dir(Path(os.environ.get("DATA_DIR", "/data")), tenant)
    work = root / "runs" / str(body.task_id)
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt = {"task_id": str(body.task_id), "tenant_id": tenant, "room": "base", "region": body.home_region,
               "status": "running", "steps": [], "model_receipts": []}
    failure = None
    async with httpx.AsyncClient(timeout=60, headers={"X-Tank-Key": os.environ.get("TANK_KEY", "")}) as client:
        # A memory outage is a visible failed task, never an empty-memory success.
        recalled = await memory(client, "/recall", {"tenant_id": tenant, "query": "Base batch " + body.batch, "kind": "base.task", "limit": 8})
        memories = recalled.get("memories")
        if not isinstance(memories, list) or any(m.get("tenant_id") != tenant for m in memories):
            raise RuntimeError("Memory tenant boundary failed")
        receipt["steps"].append({"action": "recall", "count": len(memories), "memory_ids": [m["id"] for m in memories]})
        try:
            request = {**body.model_dump(mode="json"), "memories": memories}
            (work / "request.json").write_text(json.dumps(request))
            env = {key: value for key, value in os.environ.items() if key in {
                "PATH", "PYTHONPATH", "LANG", "TANK_URL", "TANK_KEY", "TANK_REGION", "BASE_ROOM_URL",
                "BASE_BROWSER_URL", "DATA_DIR", "DOCKER_HOST", "HERMES_BUNDLED_SKILLS", "HERMES_OPTIONAL_SKILLS"}}
            env.update(HERMES_HOME=str(root / "hermes"), PYTHONUNBUFFERED="1")
            process = await asyncio.create_subprocess_exec(sys.executable, "-m", "brain.runner", str(work),
                env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            try:
                await asyncio.wait_for(process.wait(), timeout=1800)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                process.kill()
                await process.wait()
                raise
            if (work / "receipt.json").exists():
                child = json.loads((work / "receipt.json").read_text())
                if child.get("tenant_id") != tenant or child.get("task_id") != str(body.task_id):
                    raise RuntimeError("Receipt scope mismatch")
                receipt["steps"].extend(child.get("steps", []))
                receipt["model_receipts"] = child.get("model_receipts", [])
                receipt["summary"] = child.get("summary", "")
            if process.returncode != 0:
                raise RuntimeError("Base's brain could not finish; inspect the task receipt")
            receipt["status"] = "done"
        except Exception:
            receipt["status"] = "failed"
            failure = "Base's brain could not finish; the existing pipeline result is retained."
        finally:
            try:
                saved = await memory(client, "/memories", {"tenant_id": tenant,
                    "text": "Base batch " + body.batch + ": " + receipt["status"] + ". " + str(receipt.get("summary", ""))[:5000],
                    "kind": "base.task", "source": "base:task:" + str(body.task_id),
                    "meta": {"task_id": str(body.task_id), "ledger_ids": [r["ledger_id"] for r in receipt["model_receipts"]],
                             "sources": [s["source"] for s in receipt["steps"] if s.get("source")]}})
                receipt["steps"].append({"action": "remember", "memory_id": saved["id"], "source": "base:task:" + str(body.task_id)})
            except Exception:
                receipt["status"] = "failed"
                receipt["steps"].append({"action": "remember", "status": "failed"})
                failure = "Base finished work but could not save its memory."
            receipt["error"] = failure
            (work / "receipt.json").write_text(json.dumps(receipt, indent=2))
    return receipt


@app.get("/health")
async def health():
    return {"ok": True, "room": "base", "hermes_version": "0.22.2"}


@app.post("/tasks")
async def task(body: Run, x_tank_key: str = Header(default="")):
    authenticate(x_tank_key)
    scope(str(body.tenant_id), body.home_region)
    async with gate:
        try:
            return await run_task(body)
        except Exception:
            raise HTTPException(503, "Base's brain prerequisites are unavailable; no task was started.") from None
