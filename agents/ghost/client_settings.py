"""Per-client Autumbra apply choices and optional connect hands.

Autumbra is agnostic: Cloudflare, Google Workspace, Shopify, host firewall,
etc. are optional client choices — not required. Three apply choices, stored
per client. Tervory never changes them. Default is "I approve each one".
Shown on every receipt.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplyMode(str, Enum):
    approve_each = "I approve each one"
    auto_when_checks_pass = "Apply automatically when checks pass"
    never = "Never"


DEFAULT_MODE = ApplyMode.approve_each


class ClientAutumbraSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=1, max_length=80)
    site_name: str = Field(default="", max_length=120)
    # Separately for shields and for code fixes.
    shield_mode: ApplyMode = DEFAULT_MODE
    fix_mode: ApplyMode = DEFAULT_MODE
    # When True, a single threat source may trigger a shield (default False = cross-check).
    act_on_single_source: bool = False
    # Client's own CIDRs that must never be blocked.
    own_cidrs: list[str] = Field(default_factory=list, max_length=64)
    # Written-permission flag for red-team exercises against this client.
    red_team_permission: bool = False
    # Optional "hands" — client choice, like linking a tool. Autumbra stays agnostic.
    cloudflare_connected: bool = False
    google_workspace_connected: bool = False
    shopify_connected: bool = False
    host_firewall_connected: bool = False

    def receipt_stamp(self) -> dict[str, str]:
        """What every receipt must show about the client's choice."""
        return {
            "shield_mode": self.shield_mode.value,
            "fix_mode": self.fix_mode.value,
        }


def load_settings(store, tenant_id: str) -> ClientAutumbraSettings:
    raw = store.get_state(tenant_id, "autumbra_client_settings", None)
    if not isinstance(raw, dict):
        return ClientAutumbraSettings(tenant_id=tenant_id)
    try:
        return ClientAutumbraSettings.model_validate({**raw, "tenant_id": tenant_id})
    except Exception:
        return ClientAutumbraSettings(tenant_id=tenant_id)


def save_settings(store, settings: ClientAutumbraSettings) -> ClientAutumbraSettings:
    """Client (or founder-as-client) writes. Tervory automation must not call this."""
    payload: dict[str, Any] = settings.model_dump()
    store.set_state(settings.tenant_id, "autumbra_client_settings", payload)
    return settings


def active_halves(settings: ClientAutumbraSettings) -> dict[str, bool]:
    """Which hands are lit. Stack always works; "block in seconds" needs an edge hand."""
    edge = bool(
        settings.cloudflare_connected
        or settings.host_firewall_connected
        or settings.shopify_connected
    )
    return {
        "edge": edge,
        "mailbox": bool(settings.google_workspace_connected),
        "stack": True,  # inventory / advisories / fix PRs / receipts always available
        "block_in_seconds": edge,  # plain copy: lights up when a hand is connected
    }
