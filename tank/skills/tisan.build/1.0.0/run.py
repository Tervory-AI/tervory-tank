"""Queue the existing room job; its timeout exceeds Command's action timeout."""
from __future__ import annotations

import os
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
    return {"job_id": job_id, "tenant_id": tenant, "status": job["status"], "kind": "build"}
