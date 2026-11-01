"""Execute in the existing Tisan room, where the template and offline cache live."""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any


async def run(payload: dict[str, Any], ctx: Any) -> dict[str, Any]:
    tenant = str(uuid.UUID(str(ctx.tenant_id)))
    key = os.environ.get("TANK_KEY_TISAN", "")
    if not key:
        raise RuntimeError("Tisan room key is not configured")
    # Command binds the home region before entering Skala; it is not supplied by input.
    from main import box_region
    headers = {"X-Tank-Key": key, "X-Tervory-Tenant": tenant,
               "X-Tervory-Home-Region": box_region()}
    response = await ctx.http.post("http://agent-tisan:8000/jobs", headers=headers,
                                   json={"tenant_id": tenant, "kind": "build", "input": payload},
                                   timeout=30, follow_redirects=False)
    response.raise_for_status()
    job = response.json()
    if uuid.UUID(str(job.get("tenant_id"))) != uuid.UUID(tenant):
        raise RuntimeError("Tisan job tenant mismatch")
    job_id = str(uuid.UUID(str(job["id"])))
    deadline = time.monotonic() + 660
    while time.monotonic() < deadline:
        response = await ctx.http.get("http://agent-tisan:8000/jobs/" + job_id,
                                      params={"tenant_id": tenant}, headers=headers,
                                      timeout=30, follow_redirects=False)
        response.raise_for_status()
        job = response.json()
        if uuid.UUID(str(job.get("tenant_id"))) != uuid.UUID(tenant) or str(job.get("id")) != job_id:
            raise RuntimeError("Tisan job identity mismatch")
        if job.get("status") == "completed":
            result = job.get("result")
            if isinstance(result, str):
                result = json.loads(result)
            if not isinstance(result, dict):
                raise RuntimeError("Tisan returned no build result")
            return {**result, "job_id": job_id}
        if job.get("status") in {"failed", "uncertain"}:
            return {"ok": False, "job_id": job_id, "detail": job.get("error") or "build job failed"}
        await asyncio.sleep(1)
    return {"ok": False, "job_id": job_id, "detail": "build job did not finish within its deadline"}
