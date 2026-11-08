"""Typed Tiger task adapter; reuse room policy, accounting and signed forwarding.

A proposal for Head review. No new provider path or deployment configuration.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from task_contract import check_receipt, origin, paid_identity
from command_tools._user_assertion import PostgresNonces, signed_user
from product_identity import actor_scope


class TaskScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    user_id: str = Field(min_length=1, max_length=200)
    run_id: UUID


class RoomTask(TaskScope):
    messages: list[dict[str, Any]] = Field(min_length=1, max_length=512)


class DelegatedTask(TaskScope):
    task_key: str = Field(min_length=1, max_length=120)
    input: dict[str, Any]
    recall: list[dict[str, Any]]


def install(router, tank) -> None:
    from agent_skills import Chat, complete, local_region, room_key

    async def actor_for(room: str, body: TaskScope, request: Request):
        if room not in {"tiger", "ghost"}:
            raise HTTPException(403, "Room task unavailable")
        room_key(room, request.headers.get("authorization", ""), request.headers.get("x-tank-key", ""))
        setting = "TIGER_BRAIN_ENABLED" if room == "tiger" else "GHOST_BRAIN_ENABLED"
        if os.environ.get(setting, "false").lower() not in {"true", "1", "yes"}:
            raise HTTPException(409, "Tiger brain is off" if room == "tiger" else "GHOST_BRAIN_ENABLED is off.")
        local_region(tank, request.headers.get("x-home-region"), room=room)
        actor = await signed_user(request, tenant_id=str(body.tenant_id), product=room,
                                  required=True, nonces=PostgresNonces(tank.pool(), "tank"))
        if actor.user_id != body.user_id:
            raise HTTPException(403, "Actor mismatch")
        return actor

    @router.post("/v1/agents/{room}/tasks")
    async def room_task(room: str, body: RoomTask, request: Request):
        actor = await actor_for(room, body, request)
        identity = UUID(paid_identity(actor.tenant_id, actor.user_id, str(body.run_id)))
        # Same room policy, paid admission/checkpoint, ledger and agent_receipts
        # as the existing chat handler. The adapter never fabricates a receipt.
        return await complete(tank, Chat(messages=body.messages, paid_run_id=identity),
                              body.tenant_id, identity,
                              local_region(tank, request.headers.get("x-home-region"), room=room), room=room)

    @router.post("/v1/agents/{room}/delegate")
    async def delegate_task(room: str, body: DelegatedTask, request: Request):
        actor = await actor_for(room, body, request)
        unavailable = "Tiger task unavailable" if room == "tiger" else "Autumbra task unavailable"
        try:
            # Only Tank knows the private Autumbra origin; no new URL setting.
            host = "tiger-brain" if room == "tiger" else "autumbra-brain"
            base = origin(os.environ.get("TIGER_BRAIN_URL", "http://tiger-brain:8001") if room == "tiger" else "http://autumbra-brain:8001")
            parsed = urlsplit(base)
            # Private service only; this directory never accepts a caller URL.
            if parsed.scheme != "http" or parsed.hostname != host or parsed.port != 8001:
                raise ValueError("Invalid private origin")
        except ValueError:
            raise HTTPException(503, unavailable) from None
        target = "/tasks?" + urlencode({"tenant_id": actor.tenant_id, "user_id": actor.user_id})
        content = json.dumps({"task_key": body.task_key, "input": body.input,
                              "recall": body.recall, "run_id": str(body.run_id)}).encode()
        if len(content) > 1_000_000:
            raise HTTPException(413, "Task is too large")
        try:
            # Reuse Tank's production paid_http signing hook with the exact
            # configured origin, verified actor, raw target and body.
            with actor_scope(actor):
                response = await tank._http.post(base + target, content=content,
                    headers={"Content-Type": "application/json", "X-Tank-Key": os.environ["TANK_KEY_" + room.upper()]},
                    extensions={"tervory_product_origin": (room, (parsed.scheme, parsed.hostname, parsed.port))},
                    timeout=70, follow_redirects=False)
            response.raise_for_status()
            data = response.json()
            check_receipt(data, actor.tenant_id, actor.user_id, str(body.run_id), room)
            return data
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise HTTPException(status if 400 <= status < 600 else 502, unavailable) from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
            raise HTTPException(502, unavailable) from None
