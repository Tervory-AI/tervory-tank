"""A malformed tenant_id on a str-typed route is the caller's error (422), not a 500."""
from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import APIRouter, FastAPI

from tenant_db import bind_tenant_endpoints


@pytest.fixture
def app():
    router, app = APIRouter(prefix="/v1/vaults"), FastAPI()
    seen = []

    @router.get("/{vault}/plugins")
    async def plugins(vault: str, tenant_id: str):
        seen.append(tenant_id)
        return {"tenant": tenant_id}

    @router.get("/typed")
    async def typed(tenant_id: UUID):
        return {"tenant": str(tenant_id)}

    app.include_router(router)
    bind_tenant_endpoints(app)
    app.state.seen = seen
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["nope", "123", "' OR 1=1 --", "%00"])
async def test_malformed_str_tenant_is_422_and_never_reaches_the_route(app, bad):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        response = await client.get("/v1/vaults/lab.vault/plugins", params={"tenant_id": bad})
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "A workspace is required."}
    assert app.state.seen == []


@pytest.mark.asyncio
async def test_valid_and_typed_tenants_are_unchanged(app):
    tenant = str(uuid4())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
        assert (await client.get("/v1/vaults/lab.vault/plugins", params={"tenant_id": tenant})).json() == {"tenant": tenant}
        assert (await client.get("/v1/vaults/typed", params={"tenant_id": tenant})).json() == {"tenant": tenant}
        assert (await client.get("/v1/vaults/typed", params={"tenant_id": "nope"})).status_code == 422
