"""Same-box Trigger adapter; identity and squad grants come from Command."""
from __future__ import annotations

import json
import os
import re
from types import SimpleNamespace
from typing import Annotated
from uuid import UUID

import httpx
from command import Actor, authorized_actor, identity, require_tool
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1/trigger", tags=["trigger"])


async def code_receipt(tenant_id: UUID, task: str, *, task_id: UUID | None = None) -> UUID:
    from main import box_region, pool
    return await pool().fetchval(
        "INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,"
        "tokens_in,tokens_out,baseline_model,baseline_cost_usd,task_id) "
        "VALUES($1,$2,'trigger',$3,3,'code',0,0,0,'code',0,$4) RETURNING id",
        tenant_id, box_region(), task, task_id)


async def code_plan(actor: Actor, messages: list[dict], task_id: UUID | None):
    """Explicit Trigger check commands need no model to select their one tool.

    Other conversation turns keep the existing planner. Confirmation semantics
    are unchanged: this only proposes a card, and never runs the checker.
    """
    last = messages[-1] if messages else {}
    if last.get("role") != "user":
        return None
    match = re.fullmatch(r"\s*trigger(?:\.check|[, ]+check)(?:\s+(?:this\s+)?paragraph)?\s*:\s*(.+)",
                         last.get("content", ""), re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    actor = await authorized_actor(actor)
    require_tool(actor, "trigger.check")
    if len(match[1]) > 20000:
        raise HTTPException(422, "Text exceeds the checker limit")
    content = json.dumps({"text": "trigger.check", "actions": [
        {"tool": "trigger.check", "arguments": {"text": match[1]}}]})
    return SimpleNamespace(content=content, ledger_id=await code_receipt(actor.tenant_id, "command.turn", task_id=task_id))


async def room(operation: str, body: dict):
    key = os.environ.get("TANK_KEY_TRIGGER", "")
    if not key:
        raise HTTPException(503, "Trigger is not configured")
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=False, trust_env=False) as client:
            response = await client.post("http://agent-trigger:8000/" + operation,
                                         json=body, headers={"X-Tank-Key": key})
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Trigger is unavailable") from None
    if response.status_code >= 400:
        # Do not expose room exceptions, prompts or credentials.
        raise HTTPException(response.status_code if response.status_code in {409,422,503} else 502,
                            "Trigger could not complete this request")
    if not isinstance(data, dict):
        raise HTTPException(502, "Invalid Trigger response")
    return data


async def zenas_draft(body: dict, actor: Actor):
    from main import TANK_API_KEY, app, box_region
    require_tool(actor, "zenas.ask")
    if not body.get("template") or not body.get("jurisdiction"):
        raise HTTPException(422, "Zenas drafting requires a template and jurisdiction")
    payload = {"tenant_id": str(actor.tenant_id), "home_region": box_region(),
               "template": body["template"], "jurisdiction": body["jurisdiction"],
               "terms": body.get("terms", {}), "narrative": body["text"],
               "matter_id": body.get("matter_id")}
    # Zenas's own scope and tenant checks remain authoritative, including criminal refusal.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank", trust_env=False) as client:
        response = await client.post("/v1/zenas/drafts", json=payload, headers={"X-Tank-Key": TANK_API_KEY})
    data = response.json()
    if isinstance(data, dict):
        data.setdefault("notice", "legal information, not legal advice")
        # Existing chat result projection displays text/summary without a new page.
        data.setdefault("summary", data["notice"])
    return JSONResponse(data, status_code=response.status_code)


@router.post("/{operation}")
async def invoke(operation: str, request: Request, actor: Annotated[Actor, Depends(identity)]):
    from command import TriggerCheckArgs, TriggerWriteArgs
    if operation not in {"write", "check"}:
        raise HTTPException(404, "No such Trigger action")
    require_tool(actor, "trigger." + operation)
    raw = await request.body()
    if len(raw) > 60000:
        raise HTTPException(413, "Request too large")
    try:
        body = json.loads(raw)
        tenant = body.pop("tenant_id", str(actor.tenant_id))
        if tenant != str(actor.tenant_id):
            raise HTTPException(403, "Tenant mismatch")
        body = (TriggerWriteArgs if operation == "write" else TriggerCheckArgs).model_validate(body).model_dump(mode="json", exclude_none=True)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, "Invalid Trigger request") from None
    if body.get("voice") is not None and not actor.founder:
        raise HTTPException(403, "Only the founder can set a brand voice")
    data = await room(operation, {**body, "tenant_id": str(actor.tenant_id)})
    if operation == "write" and data.get("delegate") == "zenas.draft":
        return await zenas_draft(body, actor)
    if operation == "check":
        data["ledger_id"] = str(await code_receipt(actor.tenant_id, "trigger.check"))
        data["cost_usd"] = 0
        data["model_calls"] = 0
    return data
