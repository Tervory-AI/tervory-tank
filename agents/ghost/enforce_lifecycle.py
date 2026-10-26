"""Per-client Enforce containers. Coolify API by name only — never type/see/store secrets.

Watch stays shared and tenant-scoped. Each client gets its own Enforce container on an
internal network, with its own ThreatPayload queue and receipts. Optional edge
credentials are named only after a real connected hand exists (agnostic — hold CF
secret names until a real CF client). Disconnect destroys the container and any
secret name binding.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Founder correction: hold until measured dogfood / Boston RSS — do not guess 6/8/20.
DEFAULT_CONTAINER_CAP: int | None = None
FOUNDER_MUST_DECIDE_CAP = (
    "Enforce container cap is HELD until dogfood/Boston RSS is measured "
    "(ops/autumbra-enforce-memory-measure.sh on Coolify test host). "
    "Do not guess. Never live Boston. Smallest option: separate Coolify compose "
    "resource on the existing test host."
)
# Edge secret NAME pattern held until a real connected edge client (agnostic).
EDGE_SECRET_NAME_HELD = True

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


def credential_secret_name(tenant_id: str) -> str | None:
    """Coolify secret NAME only.

    Founder correction: no Cloudflare secret names yet — hold until a real edge
    client. Returns None while held. When a real CF client lands, pattern will be
    chosen then (names only in git).
    """
    # Validate tenant even while held so callers still fail on bad UUIDs.
    tenant_slug(tenant_id)
    if EDGE_SECRET_NAME_HELD:
        return None
    return f"AUTUMBRA_EDGE_CREDENTIAL_{tenant_slug(tenant_id)}"


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
    cap: int | None = DEFAULT_CONTAINER_CAP,
) -> dict[str, Any]:
    """Dry plan to create one Enforce container for this client. No Coolify call here."""
    if cap is not None and existing_count >= cap:
        raise RuntimeError(
            f"Enforce container cap ({cap}) reached. {FOUNDER_MUST_DECIDE_CAP}"
        )
    return {
        "action": "create_enforce",
        "tenant_id": tenant_id,
        "project": project_name(tenant_id),
        "network": {"name": network_name(tenant_id), "internal": True},
        "credential_secret_name": credential_secret_name(tenant_id),
        "edge_secret_name_held": EDGE_SECRET_NAME_HELD,
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
            # No assumed Cloudflare egress until a real edge hand is connected.
            "edge_api_egress": False,
        },
        "cap": {
            "current": existing_count,
            "max": cap,
            "status": "held_until_measured" if cap is None else "set",
        },
        "mem_limit_status": "provisional_compose_placeholder — measure with ops/autumbra-enforce-memory-measure.sh",
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
    for key in ("project", "threat_payload_queue"):
        if plan_a[key] == plan_b[key]:
            raise AssertionError(f"shared {key}")
    # Secret names are held (None) until a real edge client — still must not collide
    # once set; while held, both None is expected and not a share of a credential.
    a_secret, b_secret = plan_a.get("credential_secret_name"), plan_b.get("credential_secret_name")
    if a_secret is not None and b_secret is not None and a_secret == b_secret:
        raise AssertionError("shared credential_secret_name")
    if plan_a["network"]["name"] == plan_b["network"]["name"]:
        raise AssertionError("shared network")
