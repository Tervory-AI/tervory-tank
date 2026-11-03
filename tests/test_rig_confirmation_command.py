"""Offline Rig confirmation through the existing Command Confirm corridor."""
from contextlib import asynccontextmanager
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import access
import command
from trigger_commands import dispatch_confirmed

TENANT, OTHER = UUID(int=11), UUID(int=12)
TOOL = "rig.quote.confirm_payment"


def test_confirmation_tool_is_admin_or_founder_only(monkeypatch):
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "placeholder-founder")
    member = command.Actor(TENANT, "placeholder-member", False, frozenset({"rig"}))
    admin = command.Actor(TENANT, "placeholder-admin", False, tenant_admin=True)
    founder = command.Actor(TENANT, "placeholder-founder", True)
    assert TOOL not in command.allowed_tools(member)
    assert all(TOOL in command.allowed_tools(actor) for actor in (admin, founder))
    action = command.PlannedAction(tool=TOOL, arguments={"quote_id": "placeholder-quote"})
    with pytest.raises(HTTPException) as denied:
        command.validate_action(action, member)
    assert denied.value.status_code == 403
    for actor in (admin, founder):
        assert command.validate_action(action, actor) == action
        for extra in ({"tenant_id": str(OTHER)}, {"amount": "placeholder"}, {"confirmed": True}):
            with pytest.raises(HTTPException) as invalid:
                command.validate_action(command.PlannedAction(tool=TOOL, arguments={**action.arguments, **extra}), actor)
            assert invalid.value.status_code == 422


@pytest.mark.asyncio
async def test_confirm_card_binds_actor_quote_and_writes_zero_code_receipt(monkeypatch, tmp_path):
    from rigbox.service import RigError
    from test_rig_optional_auto_order import auto_shop
    from test_rig_locate_checkout import TENANT as ROOM_TENANT

    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    quote_id = (await service.locate_accept(ROOM_TENANT, body))["request_id"]
    actor = command.Actor(UUID(ROOM_TENANT), "placeholder-admin", False, frozenset({"rig"}), True)
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "placeholder-founder")
    action = command.PlannedAction(tool=TOOL, arguments={"quote_id": quote_id})
    app = FastAPI()
    app.include_router(access.router)
    state = {"cards": {}}
    receipts, requests = [], []
    ledger_id, thread_id = uuid4(), uuid4()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield self

        async def fetchval(self, sql, *args):
            if "command_threads" in sql:
                assert args[1:] == (actor.tenant_id, actor.user_id)
                return state
            assert "INSERT INTO tank.ledger" in sql and "'code',0,0,0" in sql
            receipts.append(args)
            return ledger_id

    pool = Pool()
    monkeypatch.setattr(command, "db", lambda: pool)
    monkeypatch.setattr(command, "authorized_actor", AsyncMock(side_effect=lambda value, *args, **kw: value))
    monkeypatch.setattr(command, "event", AsyncMock())
    monkeypatch.setattr(command, "step", AsyncMock())
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(app=app, TANK_API_KEY="placeholder",
                        pool=lambda: pool, box_region=lambda: "us-east"))
    app.dependency_overrides[access.identity] = lambda: actor

    async def room(request_actor, operation, data):
        requests.append((request_actor.tenant_id, operation, data))
        try:
            return await service.confirm_store_payment(str(request_actor.tenant_id), data["quote_id"])
        except RigError as error:
            raise HTTPException(error.status, "placeholder-refusal") from None

    monkeypatch.setattr(access, "rig_request", room)
    card = await command.propose_action(pool, {"thread_id": thread_id, "tenant_id": actor.tenant_id,
                                       "user_id": actor.user_id}, state, action, actor)
    assert card["status"] == "pending" and card["summary"] == TOOL and card["kind"] == "other"
    assert not command.ADAPTERS[TOOL].paid
    assert not store.locate_orders and not requests and not receipts
    method, path, params, payload = command.adapter_request(action, actor)
    assert method == "POST" and params == {} and payload == {"data": {"quote_id": quote_id}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder.invalid") as client:
        assert (await client.post(path, json=payload)).status_code == 409
    with pytest.raises(HTTPException) as pending:
        await dispatch_confirmed(action, actor, thread_id, card["card_id"])
    assert pending.value.status_code == 409 and not requests
    card["status"] = "executing"  # Existing Confirm handler durably claims this state.
    status, result = await dispatch_confirmed(action, actor, thread_id, card["card_id"])
    assert status == 200 and result["state"] == "supplier_ordered"
    assert result["ledger_id"] == str(ledger_id)
    assert receipts == [(actor.tenant_id, "us-east", TOOL, None, "rig")]
    assert requests == [(actor.tenant_id, "confirm-store-payment", {"quote_id": quote_id})]
    assert len(store.locate_orders) == 1 and len(list(tmp_path.glob("*.eml"))) == 1

    # Even a confirmed card cannot substitute a quote owned by another tenant.
    actor = command.Actor(OTHER, "placeholder-admin", False, frozenset({"rig"}), True)
    status, _ = await dispatch_confirmed(action, actor, thread_id, card["card_id"])
    assert status == 404 and len(receipts) == 1 and len(store.locate_orders) == 1
