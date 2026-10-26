"""Per-client Enforce containers. Coolify API by name only — never type/see/store secrets.

Watch stays shared and tenant-scoped. Each client gets its own Enforce container on an
internal network, holding only that client's zone-scoped Cloudflare credential as a
named Coolify secret, with its own ThreatPayload queue and receipts. Disconnect
destroys the container and its secret name binding.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Soft cap. Hard refuse above. Founder must decide the final number.
DEFAULT_CONTAINER_CAP = 20
FOUNDER_MUST_DECIDE_CAP = (
    "Cap Enforce containers per host at 20 (soft). Refuse create above the cap. "
    "Founder must decide whether to raise the cap or add a second test host "
    "(smallest option: separate Coolify compose resource on the existing test host, "
    "never live Boston apps)."
)

TENANT_RE = re.compile(r"^[0-9a-f-]{36}$", re.I)
PROJECT_PREFIX = "autumbra-enforce"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def project_name(tenant_id: str) -> str:
    if not TENANT_RE.fullmatch(tenant_id):
        raise ValueError("tenant_id must be a UUID.")
    return f"{PROJECT_PREFIX}-{tenant_id.lower()}"


def tenant_slug(tenant_id: str) -> str:
    """Stable Coolify slug from tenant UUID. Never a secret value."""
    if not TENANT_RE.fullmatch(tenant_id):
        raise ValueError("tenant_id must be a UUID.")
    return tenant_id.lower().replace("-", "_")


def credential_secret_name(tenant_id: str) -> str:
    """Coolify secret NAME only. Pattern agreed 2026-10-26: AUTUMBRA_CF_API_TOKEN_<tenant_slug>."""
    return f"AUTUMBRA_CF_API_TOKEN_{tenant_slug(tenant_id)}"


def queue_name(tenant_id: str) -> str:
    if not TENANT_RE.fullmatch(tenant_id):
        raise ValueError("tenant_id must be a UUID.")
    return f"autumbra-threatpayload-{tenant_id.lower()}"


def network_name(tenant_id: str) -> str:
    if not TENANT_RE.fullmatch(tenant_id):
        raise ValueError("tenant_id must be a UUID.")
    return f"autumbra-enforce-net-{tenant_id.lower()}"


def plan_create(
    tenant_id: str,
    *,
    existing_count: int,
    cap: int = DEFAULT_CONTAINER_CAP,
) -> dict[str, Any]:
    """Dry plan to create one Enforce container for this client. No Coolify call here."""
    if existing_count >= cap:
        raise RuntimeError(
            f"Enforce container cap ({cap}) reached. {FOUNDER_MUST_DECIDE_CAP}"
        )
    return {
        "action": "create_enforce",
        "tenant_id": tenant_id,
        "project": project_name(tenant_id),
        "network": {"name": network_name(tenant_id), "internal": True},
        "credential_secret_name": credential_secret_name(tenant_id),
        "threat_payload_queue": queue_name(tenant_id),
        "compose": "agents/ghost/docker-compose.enforce.yml",
        "coolify": "by name only — Autumbra room creates the resource; no secret values in code",
        "isolation": {
            "shares_network_with_tank": False,
            "shares_network_with_workspace": False,
            "shares_network_with_other_clients": False,
            "shares_volume_with_tervory": False,
            "public_internet": False,
            "routes_to_watch": False,
            "routes_to_queue_only": True,
            "cloudflare_api_only_egress": True,
        },
        "cap": {"current": existing_count, "max": cap},
        "founder_must_decide": FOUNDER_MUST_DECIDE_CAP,
    }


def plan_destroy(tenant_id: str) -> dict[str, Any]:
    return {
        "action": "destroy_enforce",
        "tenant_id": tenant_id,
        "project": project_name(tenant_id),
        "credential_secret_name": credential_secret_name(tenant_id),
        "threat_payload_queue": queue_name(tenant_id),
        "network": network_name(tenant_id),
        "note": "Destroy container, named secret binding, queue and internal network.",
    }


def receipt_for(plan: dict[str, Any], *, outcome: str = "planned") -> dict[str, Any]:
    """Founder-visible receipt for create/destroy. Never includes secret values."""
    return {
        "id": str(uuid4()),
        "product": "Autumbra",
        "role": "Enforce lifecycle",
        "at": now_iso(),
        "outcome": outcome,
        "action": plan["action"],
        "tenant_id": plan["tenant_id"],
        "project": plan["project"],
        "credential_secret_name": plan["credential_secret_name"],
        # Explicitly absent: any token value.
        "secret_value_present": False,
    }


def assert_tenant_isolation(plan_a: dict[str, Any], plan_b: dict[str, Any]) -> None:
    """Two fixture clients must not share project, network, queue or secret name."""
    if plan_a["tenant_id"] == plan_b["tenant_id"]:
        raise AssertionError("fixture clients must differ")
    for key in ("project", "threat_payload_queue", "credential_secret_name"):
        if plan_a[key] == plan_b[key]:
            raise AssertionError(f"shared {key}")
    if plan_a["network"]["name"] == plan_b["network"]["name"]:
        raise AssertionError("shared network")
