"""Typed room-task scope and receipt validation shared with Tank."""
from __future__ import annotations

import math
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid5


class TaskActor(Protocol):
    tenant_id: str
    user_id: str


def origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise ValueError("Invalid Tank origin")
    _ = parsed.port
    return value.rstrip("/")


def context(actor: TaskActor, run_id: str) -> tuple[str, str]:
    if not isinstance(actor.user_id, str) or not actor.user_id.strip() or len(actor.user_id) > 200:
        raise ValueError("Verified user required")
    return str(UUID(actor.tenant_id)), str(UUID(str(run_id)))


def paid_identity(tenant: str, user: str, run: str) -> str:
    return str(uuid5(UUID(tenant), user + ":" + str(UUID(run))))


def check_receipt(data: dict[str, Any], tenant: str, user: str, run: str, room: str) -> None:
    receipt = data["receipt"]
    if (receipt["tenant_id"] != tenant or receipt["room"] != room
            or receipt["task_id"] != paid_identity(tenant, user, run)
            or receipt["task_type"] != "agent." + room + ".think"):
        raise ValueError("Receipt scope mismatch")
    UUID(receipt["ledger_id"])
    for field in ("tokens_in", "tokens_out"):
        if type(receipt[field]) is not int or receipt[field] < 0:
            raise ValueError("Invalid token receipt")
    cost = receipt["cost_usd"]
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        raise ValueError("Invalid cost receipt")
