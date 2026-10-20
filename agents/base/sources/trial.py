"""Persist trial candidates without changing Base's serving profile."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sources.context_dev import ContextDev


async def store_trial_candidate(
    conn: Any, adapter: ContextDev, record_id: str, public_identity: dict[str, str],
) -> dict[str, Any]:
    identity = {key: public_identity[key] for key in ("name", "domain", "url") if key in public_identity}
    async with conn.transaction():
        row = await conn.fetchrow(
            "SELECT passes FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 AND id=$3 FOR UPDATE",
            uuid.UUID(adapter.tenant_id), uuid.UUID(adapter.run_id), uuid.UUID(record_id),
        )
        if row is None:
            raise ValueError("record not found in this tenant and run")
        passes = row["passes"]
        if isinstance(passes, str):
            passes = json.loads(passes)
        if "context_dev" in passes:
            return passes["context_dev"]
        result = await adapter.lookup(**identity)
        if result["status"] in ("ledger_unavailable", "not_configured", "credit_limit"):
            return result
        await conn.execute(
            "UPDATE agent_base.records SET passes=jsonb_set(passes, '{context_dev}', $4::jsonb), "
            "updated_at=now() WHERE tenant_id=$1 AND task_id=$2 AND id=$3",
            uuid.UUID(adapter.tenant_id), uuid.UUID(adapter.run_id), uuid.UUID(record_id),
            json.dumps(result),
        )
        return result
