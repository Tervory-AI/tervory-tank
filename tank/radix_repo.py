"""Client archive scans through Command confirmation and Radix's existing jobs."""
from __future__ import annotations

import base64
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException


async def scan(actor, body):
    from command import db, MAX_ATTACHMENT_BYTES
    from ghost_routes import call_room
    from trigger_commands import confirmation

    confirmation(actor, "radix.repo.scan", body.model_dump(mode="json"))
    async with db().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name,content FROM tank.command_attachments WHERE attachment_id=$1 AND tenant_id=$2 AND user_id=$3",
            body.attachment_id, actor.tenant_id, actor.user_id)
    if row is None:
        raise HTTPException(404, "Attachment not found")
    raw = bytes(row["content"])
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Attachment exceeds 5 MiB")
    # Same signature check as ghost_routes; extraction remains in Radix.
    if not (raw.startswith((b"PK\x03\x04", b"\x1f\x8b")) or raw[257:262] == b"ustar"):
        raise HTTPException(422, "Hand over a tar or zip archive.")
    response = await call_room("POST", "radix", "/jobs", body={
        "tenant_id": str(actor.tenant_id), "kind": "scan",
        "input": {"tenant_id": str(actor.tenant_id), "source": "b64:" + base64.b64encode(raw).decode("ascii"),
                  "ref": row["name"]},
    })
    if response.status_code != 201:
        raise HTTPException(503, "Radix did not accept the scan.")
    data = response.json()
    if data.get("tenant_id") != str(actor.tenant_id) or data.get("kind") != "scan":
        raise HTTPException(503, "Radix did not accept the scan.")
    return {"scan_id": str(UUID(data["id"])), "status": "pending"}


async def findings(actor, scan_id: UUID):
    from ghost_routes import call_room

    response = await call_room("GET", "radix", f"/jobs/{scan_id}", params={"tenant_id": str(actor.tenant_id)})
    if response.status_code != 200:
        raise HTTPException(404 if response.status_code == 404 else 503, "Radix results are unavailable.")
    data = response.json()
    if (data.get("tenant_id") != str(actor.tenant_id) or data.get("id") != str(scan_id)
            or data.get("kind") != "scan"):
        raise HTTPException(404, "Radix results are unavailable.")
    status = {"queued": "pending", "running": "running", "done": "complete", "failed": "failed"}.get(data.get("status"))
    if status is None:
        raise HTTPException(503, "Radix results are unavailable.")
    public = {"scan_id": str(scan_id), "status": status}
    if status == "complete":
        result = data.get("result")
        if (not isinstance(result, dict) or result.get("tenant_id") != str(actor.tenant_id)
                or result.get("scan_id") != str(scan_id)):
            raise HTTPException(404, "Radix results are unavailable.")
        public.update({key: result.get(key) for key in
                       ("summary", "critical", "tools", "tool_status", "scan_complete")})
        public["findings"] = [
            {**{key: row[key] for key in ("rule", "severity", "tool", "file", "line") if key in row},
             **({"explanation": row["explanation"]} if row.get("explanation") else {}),
             **({"remediation": row["fix"]} if row.get("fix") else {})}
            for row in result.get("findings", []) if isinstance(row, dict)]
    return public


async def with_receipt(actor, tool, operation):
    from main import RouteRequest, _record_local

    status = 200
    try:
        result = await operation()
    except HTTPException as exc:
        status, result = exc.status_code, {"detail": exc.detail}
    # Existing code receipt writer; no uploaded source or finding text is stored here.
    receipt = await _record_local(RouteRequest(tenant_id=actor.tenant_id, agent="radix", task_type=tool, messages=[]),
                                  {}, model="code", rung=3, content="",
                                  outcome="delivered" if status < 300 else "failed")
    from fastapi.responses import JSONResponse
    return JSONResponse({**result, "ledger_id": str(receipt.ledger_id), "cost_usd": 0}, status_code=status,
                        headers={"Cache-Control": "private, no-store"})


def build_router():
    from command import Actor, UploadRef, identity, require_tool
    router = APIRouter(prefix="/radix/repo")

    @router.post("/scan")
    async def start(body: UploadRef, actor: Actor = Depends(identity)):
        require_tool(actor, "radix.repo.scan")
        from trigger_commands import confirmation
        confirmation(actor, "radix.repo.scan", body.model_dump(mode="json"))
        return await with_receipt(actor, "radix.repo.scan", lambda: scan(actor, body))

    @router.get("/findings")
    async def read(scan_id: UUID, actor: Actor = Depends(identity)):
        require_tool(actor, "radix.repo.findings")
        return await with_receipt(actor, "radix.repo.findings", lambda: findings(actor, scan_id))

    return router
