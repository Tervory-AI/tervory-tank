"""Weekly owner-update job entry for Autumbra.

Real schedule registry entry — not a comment. Fixture runner calls the sender
for every client that has an owner_email in settings.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from .client_settings import ClientAutumbraSettings
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


def list_jobs() -> list[dict[str, Any]]:
    return [dict(WEEKLY_OWNER_UPDATE_JOB)]


def run_weekly_owner_updates(
    clients: Iterable[ClientAutumbraSettings],
    *,
    week_stats: dict[str, dict[str, Any]] | None = None,
    transport: Any | None = None,
    receipt_url_for: Callable[[ClientAutumbraSettings], str] | None = None,
) -> list[dict[str, Any]]:
    """Send one weekly email per client. Recipient from client settings only."""
    stats = week_stats or {}
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
        row = stats.get(settings.tenant_id) or {}
        receipt_url = ""
        if receipt_url_for is not None:
            receipt_url = receipt_url_for(settings)
        receipt_url = receipt_url or str(row.get("receipt_url") or "")
        if not receipt_url:
            receipt_url = f"https://protect.tervory.com/receipts/weekly/{settings.tenant_id}"
        email = build_owner_update(
            settings=settings,
            site_name=settings.site_name or "your site",
            threats_found=int(row.get("threats_found") or 0),
            critical=list(row.get("critical") or []),
            shield=row.get("shield"),
            fix_report_url=str(row.get("fix_report_url") or ""),
            pr_url=str(row.get("pr_url") or ""),
            undo_fix_url=str(row.get("undo_fix_url") or ""),
            undo_shield_url=str(row.get("undo_shield_url") or ""),
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
