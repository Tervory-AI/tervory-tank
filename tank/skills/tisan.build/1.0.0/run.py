"""Queue the existing room job; its timeout exceeds Command's action timeout."""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any


async def run(payload: dict[str, Any], ctx: Any) -> dict[str, Any]:
    tenant = str(uuid.UUID(str(ctx.tenant_id)))
    key = os.environ.get("TANK_KEY_TISAN", "")
    if not key:
        raise RuntimeError("Tisan room key is not configured")
    from main import box_region
    response = await ctx.http.post(
        "http://agent-tisan:8000/jobs",
        headers={"X-Tank-Key": key, "X-Tervory-Tenant": tenant,
                 "X-Tervory-Home-Region": box_region()},
        json={"tenant_id": tenant, "kind": "build", "input": payload},
        timeout=30, follow_redirects=False,
    )
    response.raise_for_status()
    job = response.json()
    if uuid.UUID(str(job.get("tenant_id"))) != uuid.UUID(tenant) or job.get("kind") != "build":
        raise RuntimeError("Tisan job identity mismatch")
    job_id = str(uuid.UUID(str(job["id"])))
    # Missing-copy refusals complete quickly and should reach the Confirm result.
    # Long npm builds continue under the room's ten-minute timeout.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = await ctx.http.get(
            "http://agent-tisan:8000/jobs/" + job_id,
            params={"tenant_id": tenant},
            headers={"X-Tank-Key": key, "X-Tervory-Tenant": tenant,
                     "X-Tervory-Home-Region": box_region()},
            timeout=10, follow_redirects=False,
        )
        response.raise_for_status()
        job = response.json()
        if uuid.UUID(str(job.get("tenant_id"))) != uuid.UUID(tenant) or str(job.get("id")) != job_id:
            raise RuntimeError("Tisan job identity mismatch")
        if job.get("status") == "done":
            result = job.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("Tisan returned no build result")
            return {**result, "job_id": job_id}
        if job.get("status") == "failed":
            return {"ok": False, "job_id": job_id, "detail": job.get("error") or "build job failed"}
        await asyncio.sleep(1)
    return {"job_id": job_id, "tenant_id": tenant, "status": job["status"], "kind": "build"}
