"""Tenant-private drafts. Only approved bytes are served by the public route.

The CDN must forward X-Rig-Key and respect private/no-store. Never publish a
draft bucket or a signed URL. The browser caches approved bytes in its own
short-lived, tenant-partitioned kiosk cache instead.
"""
from pathlib import Path
from uuid import UUID

from chassis.storage import Storage, StorageError
import httpx


class ForgeFiles(Storage):
    """Use only this tenant/job's RIG-5F prefix with the existing Rig signer."""
    def prefix(self, job):
        if self.region != "us-east":
            raise StorageError("This conversion is available on the US box only")
        return f"forge/{job.tenant_id}/{job.id}/"

    async def stage(self, job):
        prefix = self.prefix(job)
        try:
            for source in job.inputs:
                name = source.rsplit("/", 1)[1]
                data = await self.get(str(job.tenant_id), "uploads", name)
                key = prefix + "inputs/" + name
                path = "/" + self.bucket + "/" + key
                headers = self._sign("PUT", path, "", data)
                headers["If-None-Match"] = "*"
                response = await self._http.put(f"https://{self.host}{path}", headers=headers, content=data)
                if response.status_code == 412:
                    if await self._request("GET", key) != data:
                        raise StorageError("This job already has different input files")
                elif response.status_code not in {200, 204}:
                    raise StorageError("Input files could not be prepared")
        except httpx.HTTPError:
            raise StorageError("Input storage is unavailable") from None

    async def draft(self, job):
        data = await self._request("GET", self.prefix(job) + "drafts/model.glb")
        if len(data) > job.max_bytes:
            raise StorageError("The product file exceeds its size limit")
        return data


def asset_name(job_id):
    return f"rig-3d/{UUID(str(job_id))}.glb"


class R2Assets:
    def __init__(self, storage: Storage):
        self.storage = storage

    async def put(self, tenant, job_id, data):
        return await self.storage.put(str(tenant), "work", asset_name(job_id), data)

    async def get(self, tenant, job_id):
        return await self.storage.get(str(tenant), "work", asset_name(job_id))


class LocalAssets:
    """Explicit cloud test-page storage, never an automatic R2 fallback."""
    def __init__(self, root: Path):
        self.root = root

    def path(self, tenant, job_id):
        return self.root / str(UUID(str(tenant))) / asset_name(job_id)

    async def put(self, tenant, job_id, data):
        path = self.path(tenant, job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Immutable job outputs: a retry may confirm, never replace, the bytes.
        try:
            with path.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError("The saved model differs from this job") from None

    async def get(self, tenant, job_id):
        return self.path(tenant, job_id).read_bytes()
