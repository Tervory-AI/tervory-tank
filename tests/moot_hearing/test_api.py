from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from agents.zenas.core.moot.hearing_api import register_routes
from agents.zenas.core.moot.hearing_store import HearingStore
from .test_hearing import OWNER, HUMANS, problem
from .test_reasoning import trace


def application(monkeypatch, store):
    monkeypatch.setenv("TANK_KEY", "disposable-room-test-key")
    app = FastAPI()
    class Tenants:
        async def get_tenant(self, tenant):
            return {"tenant_id": tenant, "home_region": "us-east"} if tenant == OWNER.tenant_id else None
    register_routes(app, lambda: store.pool, Tenants, lambda: "us-east", lambda: None)
    return app


def headers(actor=OWNER):
    return {"X-Tank-Key": "disposable-room-test-key", "X-Moot-Tenant": actor.tenant_id,
        "X-Moot-Actor": actor.user_id, "X-Moot-Founder": "1" if actor.founder else "0"}


@pytest.mark.asyncio
async def test_room_identity_is_key_bound_tenant_scoped_and_never_json_asserted(monkeypatch, pg_store):
    app = application(monkeypatch, pg_store)
    seats = {seat: {"kind": "human", "user_id": actor.user_id} for seat, actor in HUMANS.items()}
    state = await pg_store.create(OWNER, str(uuid4()), problem(), seats)
    path = f"/moot/hearings/{state['id']}?home_region=us-east&seat=applicant"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(path, headers=headers(HUMANS["applicant"]))).status_code == 200
        assert (await client.get(path, headers={**headers(), "X-Tank-Key": "forged"})).status_code == 401
        assert (await client.get(path, headers={**headers(), "X-Moot-Actor": ""})).status_code == 401
        assert (await client.get(path.replace("us-east", "za"), headers=headers())).status_code == 403
        assert (await client.get(path, headers={**headers(), "X-Moot-Tenant": str(uuid4())})).status_code == 403
        detail = await client.get(path.replace("seat=applicant", "seat=judge"), headers=headers(HUMANS["applicant"]))
        assert detail.status_code == 403
        forged = await client.post(f"/moot/hearings/{state['id']}/lock?home_region=us-east", headers=headers(HUMANS["applicant"]),
            json={"request_id": str(uuid4()), "revision": 0, "payload": {}, "founder": True})
        assert forged.status_code == 422


@pytest.mark.asyncio
async def test_actual_room_turn_retry_is_idempotent_and_privacy_is_projected(monkeypatch, pg_store):
    app = application(monkeypatch, pg_store)
    seats = {seat: {"kind": "human", "user_id": actor.user_id} for seat, actor in HUMANS.items()}
    state = await pg_store.create(OWNER, str(uuid4()), problem(), seats)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for action in ("lock", "start"):
            res = await client.post(f"/moot/hearings/{state['id']}/{action}?home_region=us-east", headers=headers(),
                json={"request_id": str(uuid4()), "revision": state["revision"], "payload": {}})
            assert res.status_code == 200
            state = res.json()["hearing"]
        body = {"request_id": str(uuid4()), "revision": state["revision"], "payload": {
            "kind": "submission", "text": "Supported student submission", "reasoning": trace(), "authority_ids": ["case-1"]}}
        path = f"/moot/hearings/{state['id']}/turn?home_region=us-east"
        first = await client.post(path, headers=headers(HUMANS["applicant"]), json=body)
        repeat = await client.post(path, headers=headers(HUMANS["applicant"]), json=body)
        assert first.status_code == repeat.status_code == 200
        assert len(repeat.json()["hearing"]["transcript"]) == 1
        assert "never counsel" not in first.text and "actor_id" not in first.text
        saved = await HearingStore(pg_store.pool).load(OWNER, state["id"])
        assert saved["transcript"][0]["reasoning"]["opposing_argument"]
