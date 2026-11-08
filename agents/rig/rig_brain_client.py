"""Optional Rig worker work uses the shared typed Tank boundary only."""
from __future__ import annotations

import os
import uuid
from typing import Any


def brain_enabled() -> bool:
    return os.environ.get("RIG_BRAIN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


async def brain_then_route(http: Any, tank: Any, *, tenant_id: str, task_type: str,
                           messages: list[dict[str, str]], run_id: str | None = None) -> dict[str, Any]:
    from actor_context import get_verified_actor
    from chassis.user_assertion import SignedUser
    from rigbox.savings import active
    del http  # Private discovery, forwarding and timeouts belong to Tank.
    actor = get_verified_actor()
    meta = {"enabled": brain_enabled(), "free_first": True, "code_first": True, "called": False}
    if brain_enabled() and actor is not None:
        if actor["tenant_id"] != str(tenant_id):
            raise PermissionError("Rig actor scope mismatch")
        current = active.get() or {}
        identity = run_id or current.get("id") or str(uuid.uuid4())
        data = await tank.delegate_task(SignedUser(actor["tenant_id"], actor["user_id"], "member"),
            identity, task_type, {"messages": messages}, [])
        receipt = data["receipt"]
        meta.update(called=True, tasks={"task_id": receipt["task_id"], "status": receipt["status"]})
        # An accepted, pending or failed task must never fall through and pay again.
        if receipt["status"] != "done" or not data.get("result", {}).get("content"):
            raise RuntimeError("Rig brain did not complete; retained Tank receipts describe any work")
        return {"content": data["result"]["content"], "brain": meta,
                "paid_calls": receipt.get("paid_calls", 0),
                "answered_from_memory": receipt.get("answered_from_memory", False),
                "ledger_ids": [r["ledger_id"] for r in receipt.get("model_receipts", [])],
                **{k: receipt.get(k) for k in ("cost_usd", "tokens_in", "tokens_out", "ledger_id")}}
    routed = await tank.route(str(tenant_id), task_type, messages)
    return {**routed, "brain": meta}
