"""Local fixture evidence server. Not included in the deployed room image.

Mounts the real Tank proxy and evidence readers over a loopback test database.
No Clerk session, login bypass, public-feed request or model call exists here.
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import asyncpg
import httpx
from fastapi import FastAPI, Header, HTTPException

from core.evidence import answer, document_page, overview
from core.http import RequestBody
from core.jobs import perform_refresh
from core.ledger import PostgresLedger
from market_lab_routes import build_router

ROOT = Path(__file__).resolve().parents[3]
TENANT = "00000000-0000-0000-0000-000000000905"
FIXTURES = ROOT / "tests/fixtures/feeds"


def database_url() -> str:
    target = os.environ.get("DATABASE_URL", "")
    parsed = urlsplit(target)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.endswith("_test"):
        raise RuntimeError("The fixture proof requires a loopback database ending in _test")
    return target


@asynccontextmanager
async def ledger_context():
    conn = await asyncpg.connect(database_url())
    try:
        yield PostgresLedger(conn)
    finally:
        await conn.close()


room = FastAPI()


@room.post("/market/{operation}")
async def fixture_operation(operation: str, body: RequestBody, x_tank_key: str = Header(default="")):
    if not hmac.compare_digest(x_tank_key, os.environ["TANK_KEY_MARKET_LAB"]):
        raise HTTPException(401, "Local fixture request required")
    async with ledger_context() as ledger:
        tenant = str(body.tenant_id)
        if operation == "overview":
            return {**await overview(ledger, tenant, fixtures=True), "refresh_status": "done"}
        if operation == "ask":
            if not body.question.strip():
                raise HTTPException(422, "A question is required")
            return await answer(ledger, tenant, body.question, fixtures=True)
        if operation == "document" and body.document_id:
            result = await document_page(ledger, tenant, str(body.document_id), body.offset, fixtures=True)
            if result is None:
                raise HTTPException(404, "Source not found")
            return result
        if operation == "refresh" and tenant == TENANT:
            await perform_refresh(tenant_id=tenant, engine="ffl", ledger=ledger, fixtures=str(FIXTURES))
            return {"status": "done"}
        raise HTTPException(404, "Not found")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with ledger_context() as ledger:
        await ledger.apply_schema()
        await perform_refresh(tenant_id=TENANT, engine="ffl", ledger=ledger, fixtures=str(FIXTURES))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room)) as downstream:
        app.state.http = downstream
        yield


app = FastAPI(lifespan=lifespan)


async def require_key(x_tank_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_tank_key, os.environ["TANK_API_KEY"]):
        raise HTTPException(401, "Local fixture request required")


app.include_router(build_router(SimpleNamespace(require_key=require_key, shared_http=lambda: app.state.http)))


@app.get("/health")
async def health():
    return {"fixture": True, "label": "local, fixture page"}
