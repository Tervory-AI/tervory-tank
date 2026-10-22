"""Only the brain can reach the sealed forge. No conversion tools run here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5, NAMESPACE_URL

import httpx

from rigbox.service import RigError
from .contracts import Job, Report, Result


class Forge(Protocol):
    async def submit(self, job: Job) -> Result: ...
    async def poll(self, job: Job) -> Result: ...
    async def artifact(self, job: Job) -> bytes: ...


class BrainForge:
    """Authenticated brain relay; absent RIG-5F wiring fails closed.

    The brain owns the receipt relay and cost-cap enforcement. The public room
    cannot choose an arbitrary forge URL or use a Hugging Face credential.
    """
    def __init__(self, client: httpx.AsyncClient, key: str):
        self.client, self.key = client, key

    async def _call(self, method: str, job: Job, suffix: str = ""):
        if not self.key:
            raise RigError("forge_unavailable", "The model service is not connected.", 503)
        try:
            response = await self.client.request(
                method, "http://rig-brain:8001/forge/jobs" + ("/" + str(job.id) + suffix if method == "GET" else ""),
                headers={"X-Tank-Key": self.key},
                params={"tenant_id": str(job.tenant_id)} if method == "GET" else None,
                json=job.model_dump(mode="json") if method == "POST" else None,
                timeout=30,
            )
            if response.status_code not in {200, 202}:
                raise ValueError("relay failed")
            if len(response.content) > job.max_bytes + 100_000:
                raise ValueError("oversized reply")
            return response
        except (httpx.HTTPError, ValueError):
            raise RigError("forge_unavailable", "The model service is not connected.", 503) from None

    async def submit(self, job: Job) -> Result:
        return self._result(await self._call("POST", job), job)

    async def poll(self, job: Job) -> Result:
        return self._result(await self._call("GET", job), job)

    @staticmethod
    def _result(response, job):
        try:
            result = Result.model_validate(response.json())
            if result.id != job.id or result.tenant_id != job.tenant_id:
                raise ValueError("wrong job")
            return result
        except ValueError:
            raise RigError("forge_invalid", "The model service returned an invalid result.", 502) from None

    async def artifact(self, job: Job) -> bytes:
        return (await self._call("GET", job, "/artifact")).content


class StubForge:
    """Explicit stand-in only. Never pretends to convert uploaded CAD or photos.

    Uses the same submit/poll/artifact interface and wire shapes as BrainForge.
    The fixtures contain a neutral centre and two parts, made by this stub's
    fixture builder. No tool installation or GPU job occurs in the room.
    """
    def __init__(self):
        self.jobs: dict[tuple[UUID, UUID], Job] = {}
        self.root = Path(__file__).with_name("fixtures")

    async def submit(self, job: Job) -> Result:
        if job.product_id not in {"centre", "part-a", "part-b", "part-tall"} or job.cost_cap_usd != 0:
            raise RigError("stand_in", "The stand-in accepts only the three sample models at zero cost.", 422)
        self.jobs[(job.tenant_id, job.id)] = job
        return Result(id=job.id, tenant_id=job.tenant_id, status="queued")

    async def poll(self, job: Job) -> Result:
        data = await self.artifact(job)
        metadata = json.loads((self.root / (job.product_id + ".json")).read_text())
        report = Report(**metadata, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                        receipt_ids=[uuid5(NAMESPACE_URL, f"rig5-stand-in:{job.tenant_id}:{job.id}:{step}")
                                     for step in ("input", "optimise", "check", "validate")])
        return Result(id=job.id, tenant_id=job.tenant_id, status="draft", report=report)

    async def artifact(self, job: Job) -> bytes:
        # Tenant and request are persisted by Engine, so polling survives restart.
        if job.product_id not in {"centre", "part-a", "part-b", "part-tall"}:
            raise RigError("not_found", "No sample model exists.", 404)
        return (self.root / (job.product_id + ".glb")).read_bytes()
