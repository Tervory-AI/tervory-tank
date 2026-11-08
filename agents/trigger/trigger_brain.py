"""Keep Trigger model work on Tank's existing policy and receipt path."""
from __future__ import annotations

from typing import Any


def brain_enabled() -> bool:
    """Direct room-brain routing is unavailable until separately integrated."""
    return False


async def brain_then_route(
    http: Any,
    tank: Any,
    *,
    tenant_id: str,
    task_type: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Use Tank for all model calls, including when memory is enabled.

    The memory bracket owns recall and remember. It does not authorize a new
    provider or a second task submission outside Tank's policy and ledger.
    """
    routed = await tank.route(str(tenant_id), task_type, messages)
    return {**routed, "brain": {"enabled": False, "free_first": True, "code_first": True}}


async def ask_brain_tasks(http: Any, *, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    """Legacy standby contract; model execution remains exclusively on Tank."""
    return {"status": "standby", "gap_filled": False}
