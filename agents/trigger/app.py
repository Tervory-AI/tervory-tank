"""Trigger room. Only authenticated same-box Tank calls; no public page."""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import asyncpg
import httpx
from chassis.tank import TankClient
from fastapi import Depends, FastAPI, Header, HTTPException

from trigger.service import CheckIn, WriteIn, check_text, write
from trigger.voice import Voice, VoiceStore


async def authorized(x_tank_key: str = Header(default="")):
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not hmac.compare_digest(expected.encode(), x_tank_key.encode()):
        raise HTTPException(401, "Room authentication required")


@asynccontextmanager
async def lifespan(app):
    app.state.pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=3)
    await app.state.pool.execute(Path(__file__).with_name("schema.sql").read_text())
    app.state.http = httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False)
    app.state.tank = TankClient("http://tank:8000", os.environ.get("TANK_KEY", ""), "trigger", app.state.http)
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    if not getattr(app.state, "pool", None):
        raise HTTPException(503, "Database unavailable")
    await app.state.pool.fetchval("SELECT 1")
    return {"ok": True, "agent": "trigger"}


@app.put("/voice/{tenant_id}", dependencies=[Depends(authorized)])
async def put_voice(tenant_id: UUID, voice: Voice):
    try:
        await VoiceStore(app.state.pool).put(tenant_id, voice)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"revision": voice.revision}


@app.post("/check", dependencies=[Depends(authorized)])
async def post_check(body: CheckIn):
    return await check_text(body, VoiceStore(app.state.pool), app.state.http, app.state.tank)


@app.post("/write", dependencies=[Depends(authorized)])
async def post_write(body: WriteIn):
    try:
        return await write(body, VoiceStore(app.state.pool), app.state.tank, app.state.http, app.state.tank)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.post("/skala/languagetool", dependencies=[Depends(authorized)])
async def skala_languagetool(body: CheckIn):
    """Transport only: the approved package owns rule/result interpretation."""
    import hashlib
    import json
    response = await app.state.http.post(
        "http://trigger-languagetool:8081/v2/check",
        data={"text": body.text, "language": "en-US"}, timeout=30,
    )
    response.raise_for_status()
    config = Path(__file__).with_name("languagetool.properties").read_bytes()
    pins = json.loads((Path(__file__).parent / "sources/pins.json").read_text())
    return {"result": response.json(), "config_sha256": hashlib.sha256(config).hexdigest(),
            "image": pins["languagetool-image"]}
