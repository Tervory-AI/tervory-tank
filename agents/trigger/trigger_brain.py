"""Call Trigger's room brain the way Base calls BASE_BRAIN_URL.

Code and free Tank routes run first. The brain is only asked when enabled and
only for gaps code cannot fill, via POST /tasks (when provisioned). Standby
brains expose /health only; callers then continue through Tank routing for
model work, with recall/remember/receipts owned by the memory bracket.
"""
from __future__ import annotations

import os
import uuid
from typing import Any


def brain_enabled() -> bool:
    raw = os.environ.get("TRIGGER_BRAIN_ENABLED", "false").strip().lower()
    return raw not in {"", "0", "false", "no", "off"}


def brain_url() -> str:
    return os.environ.get("TRIGGER_BRAIN_URL", "http://trigger-brain:8001").rstrip("/")


async def ping_brain(http: Any) -> dict[str, Any]:
    """Health probe used before paid work when the brain switch is on."""
    if not brain_enabled():
        return {"ok": False, "enabled": False}
    response = await http.get(brain_url() + "/health")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Trigger brain health was not an object")
    return {**data, "enabled": True}


async def ask_brain_tasks(
    http: Any,
    *,
    tenant_id: str,
    task_type: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Ask the room brain /tasks for gaps only (Base pattern).

    Standby brains have no /tasks API; a 404/405 means fall through to Tank.
    """
    task_id = str(uuid.uuid4())
    payload = {
        "tenant_id": str(tenant_id),
        "task_id": task_id,
        "home_region": os.environ.get("TANK_REGION", "us-east"),
        "task_type": task_type,
        "messages": messages,
        "room": "trigger",
        "batch": task_type,
        "count": 1,
    }
    response = await http.post(brain_url() + "/tasks", json=payload)
    if response.status_code in {404, 405}:
        return {"status": "standby", "task_id": task_id, "gap_filled": False}
    if response.status_code == 202:
        # Poll once; standby never reaches here. Full brains may still be running.
        poll = await http.get(
            brain_url() + "/tasks/" + task_id,
            params={"tenant_id": str(tenant_id), "home_region": payload["home_region"]},
        )
        if poll.status_code == 202:
            return {"status": "running", "task_id": task_id, "gap_filled": False}
        poll.raise_for_status()
        data = poll.json()
        if not isinstance(data, dict):
            raise RuntimeError("Trigger brain task was not an object")
        content = data.get("summary") or data.get("content")
        return {
            "status": data.get("status") or "done",
            "task_id": task_id,
            "gap_filled": bool(content),
            "content": content,
            "receipt": data,
        }
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Trigger brain task was not an object")
    content = data.get("summary") or data.get("content")
    return {
        "status": data.get("status") or "done",
        "task_id": task_id,
        "gap_filled": bool(content),
        "content": content,
        "receipt": data,
    }


async def brain_then_route(
    http: Any,
    tank: Any,
    *,
    tenant_id: str,
    task_type: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Product paid path: free/code first, optional brain /tasks for gaps, then Tank route.

    Matches Base: code and free passes first; the brain only for what code cannot
    do; Tank routing carries model work and receipts. Recall/remember live in the
    memory bracket around this call.
    """
    brain_meta: dict[str, Any] = {
        "enabled": brain_enabled(),
        "free_first": True,
        "code_first": True,
    }
    # Free/code-first: Trigger checkers and house-style are code paths that run
    # around this paid route. No model call happens here for free work.
    if brain_enabled() and http is not None:
        try:
            brain_meta.update(await ping_brain(http))
            gap = await ask_brain_tasks(
                http, tenant_id=str(tenant_id), task_type=task_type, messages=messages
            )
            brain_meta["tasks"] = {
                "status": gap.get("status"),
                "task_id": gap.get("task_id"),
                "gap_filled": bool(gap.get("gap_filled")),
            }
            # A brain-filled gap still settles through Tank routing when the brain
            # did not itself produce a billed Tank receipt. Prefer Tank content.
            if gap.get("gap_filled") and gap.get("content") and not gap.get("receipt", {}).get("model_receipts"):
                brain_meta["gap_content_chars"] = len(str(gap["content"]))
        except Exception as exc:  # paid Tank route still proceeds on brain failure
            brain_meta["error"] = type(exc).__name__
            brain_meta["tasks"] = {"status": "unavailable", "gap_filled": False}
    routed = await tank.route(str(tenant_id), task_type, messages)
    return {**routed, "brain": brain_meta}
