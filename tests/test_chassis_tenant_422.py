"""Rooms: a malformed tenant a caller sends is their error (422), not a 500.

agents/_chassis/chassis/tenant_db.py tenant_scope does UUID(str(tenant)), so a
str-typed tenant argument such as "nope" raised ValueError inside the endpoint
wrapper and the room answered 500. Same rule as Tank's tenant_db (#523).
"""
from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from chassis.tenant_db import bind_tenant_endpoints, tenant_path
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel


class Body(BaseModel):
    tenant_id: str


@pytest.fixture
def app():
    router, app = APIRouter(prefix="/v1"), FastAPI()
    seen = []

    @router.get("/files/{name}")
    async def files(name: str, tenant_id: str):
        seen.append(tenant_id)
        return {"tenant": tenant_id}

    @router.get("/header")
    async def header(tenant: str = ""):
        seen.append(tenant)
        return {"tenant": tenant}

    @router.post("/body")
    async def body(payload: Body):
        seen.append(payload.tenant_id)
        return {"tenant": payload.tenant_id}

    @router.get("/typed")
    async def typed(tenant_id: UUID):
        return {"tenant": str(tenant_id)}

    @router.get("/path")
    @tenant_path("tenant")
    async def path(tenant: str):
        seen.append(tenant)
        return {"tenant": tenant}

    app.include_router(router)
    bind_tenant_endpoints(app)
    app.state.seen = seen
    return app


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["nope", "123", "' OR 1=1 --", "%00"])
async def test_malformed_tenant_is_422_and_never_reaches_the_route(app, bad):
    async with _client(app) as client:
        responses = [
            await client.get("/v1/files/a.txt", params={"tenant_id": bad}),
            await client.get("/v1/header", params={"tenant": bad}),
            await client.post("/v1/body", json={"tenant_id": bad}),
            await client.get("/v1/path", params={"tenant": bad}),
        ]
    for response in responses:
        assert response.status_code == 422, response.text
        assert response.json() == {"detail": "A workspace is required."}
    assert app.state.seen == []


@pytest.mark.asyncio
async def test_valid_missing_and_typed_tenants_are_unchanged(app):
    tenant = str(uuid4())
    async with _client(app) as client:
        assert (await client.get("/v1/files/a.txt", params={"tenant_id": tenant})).json() == {"tenant": tenant}
        assert (await client.post("/v1/body", json={"tenant_id": tenant})).json() == {"tenant": tenant}
        assert (await client.get("/v1/path", params={"tenant": tenant})).json() == {"tenant": tenant}
        assert (await client.get("/v1/header")).json() == {"tenant": ""}
        assert (await client.get("/v1/typed", params={"tenant_id": tenant})).json() == {"tenant": tenant}
        assert (await client.get("/v1/typed", params={"tenant_id": "nope"})).status_code == 422


@pytest.mark.asyncio
async def test_tenant_path_called_directly_rejects_malformed_tenant_with_422():
    """tenant_path's own check (not bind_tenant_endpoints') turns "nope" into a 422."""
    from fastapi import HTTPException

    seen = []

    @tenant_path("tenant")
    async def direct(tenant: str):
        seen.append(tenant)
        return tenant

    with pytest.raises(HTTPException) as raised:
        await direct("nope")
    assert raised.value.status_code == 422
    assert raised.value.detail == "A workspace is required."
    assert seen == []
