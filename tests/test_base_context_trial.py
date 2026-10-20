"""The trial entry point requires Base's room key and explicit public input."""

import uuid
from unittest.mock import AsyncMock

import httpx
import pytest

from test_b3_base_room import ROOT, _load


@pytest.mark.asyncio
async def test_trial_auth_and_public_input(monkeypatch):
    base = _load("base_context_trial_app", ROOT / "agents/base/app.py")
    monkeypatch.setenv("TANK_KEY", "base-placeholder")
    runner = AsyncMock(return_value={"results": []})
    monkeypatch.setattr(base, "run_trial", runner)
    monkeypatch.setattr(base.app.state, "pool", object(), raising=False)
    monkeypatch.setattr(base.app.state, "http", object(), raising=False)
    body = {
        "tenant_id": str(uuid.uuid4()), "run_id": str(uuid.uuid4()),
        "records": [{"record_id": str(uuid.uuid4()), "public": True, "domain": "stripe.com"}],
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app), base_url="http://base.test") as client:
        for headers in ({}, {"X-Tank-Key": "workspace-placeholder"}):
            assert (await client.post("/context-dev/trial", json=body, headers=headers)).status_code == 401
        headers = {"X-Tank-Key": "base-placeholder"}
        for changes in (
            {"public": False}, {"email": "not-sent"}, {"domain": "http://localhost"},
            {"checked_answers": {"person": "not-sent"}},
        ):
            invalid = {**body, "records": [{**body["records"][0], **changes}]}
            assert (await client.post("/context-dev/trial", json=invalid, headers=headers)).status_code == 422
        runner.assert_not_called()
        assert (await client.post("/context-dev/trial", json=body, headers=headers)).status_code == 200
        assert runner.await_args.args[2:4] == (body["tenant_id"], body["run_id"])
