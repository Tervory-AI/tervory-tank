"""Product paid path: Base brain HTTP task, then Tank agent receipts.

Mirrors the live drive_batch brain poll. Offline tests inject fakes; production
uses skills._headers / skills._http against BASE_BRAIN_URL and Tank.
"""
from __future__ import annotations

import os
import json
from typing import Any

import httpx

try:
    from network import BoundedHTTP
except ModuleNotFoundError:
    from agents.base.network import BoundedHTTP

try:
    from gates_memory import usage_from_model_receipts
except ModuleNotFoundError:
    from agents.base.gates_memory import usage_from_model_receipts


def brain_url() -> str:
    return os.environ.get("BASE_BRAIN_URL", "").rstrip("/")


def brain_enabled() -> bool:
    return bool(brain_url())


async def fetch_tank_agent_receipts(skills: Any, tenant_id: str, task_id: str) -> list[dict[str, Any]]:
    response = await skills._http.get(
        skills._base + "/v1/agents/base/receipts",
        headers=skills._headers(),
        params={"tenant_id": str(tenant_id), "task_id": str(task_id)},
        timeout=15,
    )
    if response.status_code != 200:
        return []
    data = response.json()
    rows = data.get("receipts") if isinstance(data, dict) else None
    return list(rows) if isinstance(rows, list) else []


async def invoke_brain_task(
    skills: Any,
    *,
    tenant_id: str,
    task_id: str,
    batch: str,
    count: int,
    engine: str | None = None,
    home_region: str | None = None,
    user_id: str | None = None,
    evidence: list[dict] | None = None,
) -> dict[str, Any]:
    """POST/poll BASE_BRAIN_URL/tasks then attach Tank model receipts + usage."""
    url = brain_url()
    if not url:
        raise RuntimeError("BASE_BRAIN_URL is not set")
    region = home_region or os.environ.get("TANK_REGION", "us-east")
    from chassis.user_assertion import SignedUser, sign_assertion
    if not user_id:
        raise PermissionError("Verified Base planning owner required")
    actor = SignedUser(str(tenant_id), user_id, 'member')
    key = skills._headers()['X-Tank-Key']
    path = '/personal/tasks'
    payload = dict(tenant_id=str(tenant_id), user_id=user_id, task_id=str(task_id),
                   home_region=region, batch=batch, count=count, engine=engine, evidence=evidence or [])
    raw = json.dumps(payload, separators=(',', ':')).encode()
    headers = {**skills._headers(), 'Content-Type': 'application/json',
        'X-Tervory-User-Assertion': sign_assertion('base', actor, 'POST', path, raw, key=key)}
    async with httpx.AsyncClient(timeout=70) as raw_client:
        client = BoundedHTTP(raw_client)
        response = await client.post(url + path, content=raw, headers=headers, timeout=70,
                                     follow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError("Base brain unavailable")
    receipt = response.json()
    if not isinstance(receipt, dict):
        raise RuntimeError("Brain receipt was not an object")
    if receipt.get("tenant_id") != str(tenant_id) or receipt.get("task_id") != str(task_id):
        raise RuntimeError("Brain receipt scope mismatch")
    if receipt.get("status") != "done":
        raise RuntimeError("Brain did not finish")
    model_receipts = list(receipt.get("model_receipts") or [])
    if not model_receipts:
        model_receipts = await fetch_tank_agent_receipts(skills, tenant_id, task_id)
        receipt["model_receipts"] = model_receipts
    usage = usage_from_model_receipts(model_receipts)
    return {
        "cost_usd": usage["cost_usd"],
        "tokens_in": usage["tokens_in"],
        "tokens_out": usage["tokens_out"],
        "tokens_total": usage["tokens_total"],
        "result": receipt,
        "brain": {"url": url, "status": receipt.get("status"), "steps": receipt.get("steps") or []},
    }
