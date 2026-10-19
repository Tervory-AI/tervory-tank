"""Clerk organization → tenant id. Same rule as workspace/lib/tenant.ts."""

from __future__ import annotations

import uuid

# Fixed. Changing it would point every organization at a different tenant.
NAMESPACE = uuid.UUID("7f3b1c2e-9a4d-4c1e-8f2a-5b6d7e8f9a0b")


def alias_map(raw: str) -> dict[str, str]:
    """org_new=org_old pairs. Org ids are not secrets. Anything else is ignored."""
    found: dict[str, str] = {}
    for pair in (raw or "").split(","):
        left, sep, right = pair.partition("=")
        if not sep:
            continue
        source = left.strip()
        target = right.strip()
        if source.startswith("org_") and target.startswith("org_"):
            found[source] = target
    return found


def tenant_id_for(org_id: str, aliases: str = "") -> str:
    """Stable UUID for a Clerk organization, after any alias."""
    mapped = alias_map(aliases).get(org_id, org_id)
    return str(uuid.uuid5(NAMESPACE, mapped))
