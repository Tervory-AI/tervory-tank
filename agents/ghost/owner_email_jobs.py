"""Weekly owner-update job entry for Autumbra.

Real schedule registry entry — not a comment. Builds every count from receipts
(never from a request body). Sends when Autumbra acts, and weekly for every
tenant with a stored owner_email. Every link points to a page that exists.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from .client_settings import ClientAutumbraSettings, load_settings
from .owner_email import (
    DEFAULT_FIXTURE_TRANSPORT,
    build_owner_update,
    send_owner_update,
)

# Real job entry (discovered by ops / hermes-style schedulers).
WEEKLY_OWNER_UPDATE_JOB: dict[str, Any] = {
    "id": "autumbra_weekly_owner_update",
    "product": "Autumbra",
    "kind": "schedule",
    "cadence": "weekly",
    "entrypoint": "ghost.owner_email_jobs.run_weekly_owner_updates",
    "description": (
        "Build the owner update email from receipts (code only) and send it "
        "to each client's owner_email. Quiet week when nothing fired."
    ),
}

PROTECT_HOST = "https://protect.tervory.com"


def default_receipt_url(tenant_id: str) -> str:
    """Weekly receipt page that exists under /autumbra on protect.tervory.com."""
    return f"{PROTECT_HOST}/autumbra/receipts/weekly/{tenant_id}"


def default_undo_url(receipt_id: str) -> str:
    """Undo landing page with a real Undo button."""
    return f"{PROTECT_HOST}/autumbra/undo/{receipt_id}"


def list_jobs() -> list[dict[str, Any]]:
    return [dict(WEEKLY_OWNER_UPDATE_JOB)]


def list_clients_with_owner(store) -> list[ClientAutumbraSettings]:
    """Every tenant that has stored Autumbra settings with an owner_email."""
    rows = store.db.execute(
        "SELECT tenant, value FROM ghost_state WHERE key=?",
        ("autumbra_client_settings",),
    ).fetchall()
    out: list[ClientAutumbraSettings] = []
    for tenant, _value in rows:
        settings = load_settings(store, str(tenant))
        if (settings.owner_email or "").strip():
            out.append(settings)
    return out


def week_stats_from_receipts(
    receipts: Iterable[dict[str, Any]],
    *,
    tenant_id: str,
) -> dict[str, Any]:
    """Derive owner-email counts from receipts only — never from a request body."""
    threats = 0
    critical: list[dict[str, Any]] = []
    blocked = 0
    shield_source_url = ""
    shield_source_name = ""
    undo_receipt_id = ""
    checks = 0
    seen_critical: set[str] = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("tenant_id") and str(receipt.get("tenant_id")) != tenant_id:
            continue
        kind = str(receipt.get("kind") or "")
        outcome = str(receipt.get("outcome") or "")
        role = str(receipt.get("role") or "")
        if kind == "queue_quarantine":
            continue
        if role in {"Watch", "Enforce"} or outcome in {
            "queued", "applied", "undone", "awaiting_approval", "report_only",
            "auto_apply", "refused", "burned",
        }:
            checks += 1
        applied = bool(receipt.get("applied"))
        if applied or outcome in {"applied", "awaiting_approval", "report_only"}:
            threats += 1
            if applied and receipt.get("undo", {}).get("rule_id"):
                blocked += 1
                undo_receipt_id = str(receipt.get("id") or undo_receipt_id)
            sev = str(receipt.get("severity") or "").lower()
            url = str(receipt.get("advisory_url") or "").strip()
            if sev in {"critical", "known_exploited"} and url:
                key = url
                if key not in seen_critical:
                    seen_critical.add(key)
                    critical.append({
                        "stack": str(
                            receipt.get("stack")
                            or receipt.get("component")
                            or "software"
                        ),
                        "rating": sev,
                        "advisory_url": url,
                        "advisory_id": (receipt.get("cve_ids") or [None])[0],
                    })
                if not shield_source_url:
                    shield_source_url = url
                    shield_source_name = str(
                        receipt.get("source_name") or "public advisory"
                    )
    shield = None
    if blocked:
        shield = {
            "blocked_addresses": blocked,
            "source_name": shield_source_name or "public advisory",
            "source_url": shield_source_url or default_receipt_url(tenant_id),
        }
    return {
        "threats_found": threats,
        "critical": critical,
        "shield": shield,
        "checks_run": checks,
        "undo_shield_url": default_undo_url(undo_receipt_id) if undo_receipt_id else "",
        "receipt_url": default_receipt_url(tenant_id),
        "fix_report_url": default_receipt_url(tenant_id),
        "pr_url": default_receipt_url(tenant_id),
        "undo_fix_url": default_undo_url(undo_receipt_id) if undo_receipt_id else default_receipt_url(tenant_id),
    }


def build_owner_update_from_receipts(
    *,
    settings: ClientAutumbraSettings,
    receipts: Iterable[dict[str, Any]],
    receipt_url: str = "",
    undo_shield_url: str = "",
    fix_report_url: str = "",
    pr_url: str = "",
    undo_fix_url: str = "",
) -> dict[str, str]:
    """Build the owner email entirely from receipts + stored settings."""
    stats = week_stats_from_receipts(receipts, tenant_id=settings.tenant_id)
    return build_owner_update(
        settings=settings,
        site_name=settings.site_name or "your site",
        threats_found=int(stats["threats_found"]),
        critical=list(stats["critical"]),
        shield=stats.get("shield"),
        fix_report_url=fix_report_url or str(stats.get("fix_report_url") or ""),
        pr_url=pr_url or str(stats.get("pr_url") or ""),
        undo_fix_url=undo_fix_url or str(stats.get("undo_fix_url") or ""),
        undo_shield_url=undo_shield_url or str(stats.get("undo_shield_url") or ""),
        receipt_url=receipt_url or str(stats.get("receipt_url") or default_receipt_url(settings.tenant_id)),
        checks_run=stats.get("checks_run"),
    )


def run_weekly_owner_updates(
    clients: Iterable[ClientAutumbraSettings],
    *,
    week_stats: dict[str, dict[str, Any]] | None = None,
    receipts_by_tenant: dict[str, list[dict[str, Any]]] | None = None,
    transport: Any | None = None,
    receipt_url_for: Callable[[ClientAutumbraSettings], str] | None = None,
) -> list[dict[str, Any]]:
    """Send one weekly email per client. Recipient from client settings only.

    Prefer receipts_by_tenant (real counts). week_stats is accepted only when it
    was itself derived from receipts by the caller.
    """
    stats = week_stats or {}
    by_receipts = receipts_by_tenant or {}
    sender = transport or DEFAULT_FIXTURE_TRANSPORT
    results: list[dict[str, Any]] = []
    for settings in clients:
        to = (settings.owner_email or "").strip()
        if not to:
            results.append({
                "tenant_id": settings.tenant_id,
                "sent": False,
                "skipped": "no owner_email in client settings",
            })
            continue
        if settings.tenant_id in by_receipts:
            row = week_stats_from_receipts(
                by_receipts[settings.tenant_id], tenant_id=settings.tenant_id
            )
        else:
            row = stats.get(settings.tenant_id) or {}
            # If caller passed empty stats and no receipts, quiet week with real zeros.
            if not row:
                row = week_stats_from_receipts([], tenant_id=settings.tenant_id)
        receipt_url = ""
        if receipt_url_for is not None:
            receipt_url = receipt_url_for(settings)
        receipt_url = receipt_url or str(row.get("receipt_url") or "")
        if not receipt_url:
            receipt_url = default_receipt_url(settings.tenant_id)
        shield = row.get("shield")
        undo_shield = str(row.get("undo_shield_url") or "")
        if shield and not undo_shield:
            # Still a real page (weekly receipts); never invent a dead undo link.
            undo_shield = receipt_url
        email = build_owner_update(
            settings=settings,
            site_name=settings.site_name or "your site",
            threats_found=int(row.get("threats_found") or 0),
            critical=list(row.get("critical") or []),
            shield=shield,
            fix_report_url=str(row.get("fix_report_url") or receipt_url),
            pr_url=str(row.get("pr_url") or receipt_url),
            undo_fix_url=str(row.get("undo_fix_url") or receipt_url),
            undo_shield_url=undo_shield,
            receipt_url=receipt_url,
            checks_run=row.get("checks_run"),
        )
        sent = send_owner_update(email, to=to, transport=sender)
        results.append({
            "tenant_id": settings.tenant_id,
            "job_id": WEEKLY_OWNER_UPDATE_JOB["id"],
            **sent,
        })
    return results
