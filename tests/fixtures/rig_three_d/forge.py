from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
import hashlib
import json
from rigbox.service import RigError
from rigbox.three_d.contracts import Job, Result, Report

class StubForge:
    """Explicit stand-in only. Never pretends to convert uploaded photos.

    Uses the same submit/poll/artifact interface and wire shapes as BrainForge.
    The fixtures contain a neutral centre and two parts, made by this stub's
    fixture builder. No tool installation or GPU job occurs in the room.
    """
    def __init__(self):
        self.jobs: dict[tuple[UUID, UUID], Job] = {}
        self.root = Path(__file__).with_name("models")

    async def submit(self, job: Job) -> Result:
        if job.product_id not in {"centre", "part-a", "part-b", "part-tall"} or job.cost_cap_usd != 0:
            raise RigError("stand_in", "The stand-in accepts only the three sample models at zero cost.", 422)
        metadata = json.loads((self.root / (job.product_id + ".json")).read_text())
        if job.anchors and job.model_dump(mode="json")["anchors"] != metadata["anchors"]:
            raise RigError("stand_in", "The stand-in uses the sample product's fixed attachment points.", 422)
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
