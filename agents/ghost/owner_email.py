"""Owner update email — built by code from receipts. No model. Plain English only."""
from __future__ import annotations

from typing import Any

from .client_settings import ApplyMode, ClientAutumbraSettings


def _link(label: str, url: str) -> str:
    return f"{label} ({url})" if url else label


def build_owner_update(
    *,
    settings: ClientAutumbraSettings,
    site_name: str,
    threats_found: int,
    critical: list[dict[str, Any]],
    shield: dict[str, Any] | None = None,
    fix_report_url: str = "",
    pr_url: str = "",
    undo_fix_url: str = "",
    undo_shield_url: str = "",
    receipt_url: str = "",
    checks_run: int | None = None,
) -> dict[str, str]:
    """Exact founder wording. Numbers must link to the receipt behind them."""
    site = site_name or settings.site_name or "your site"
    n = int(threats_found)
    c = len(critical)
    subject = f"Autumbra update for {site}: {n} threats found, {c} critical"

    # Quiet week — brief requires this exact shape when nothing fired.
    if n == 0 and c == 0 and not shield:
        checks = int(checks_run if checks_run is not None else 0)
        body = (
            f"Quiet week. {_link(str(checks), receipt_url) if receipt_url else str(checks)} "
            f"checks, 0 threats, 0 actions.\n\n"
            "Nothing from your logs was kept. We read them, acted, and deleted them. "
            f"{_link('Full receipt', receipt_url) if receipt_url else '[Link to the full receipt]'}"
        )
        return {"subject": subject, "body": body}

    stacks = []
    for item in critical:
        name = str(item.get("stack") or item.get("name") or "software")
        stacks.append(name)
    stack_list = ", ".join(stacks) if stacks else "software"
    if len(stacks) >= 2:
        stack_list = ", ".join(stacks[:-1]) + " and " + stacks[-1]

    advisory_bits = []
    for item in critical:
        url = str(item.get("advisory_url") or "")
        label = str(item.get("advisory_id") or "advisory")
        if url:
            advisory_bits.append(_link(label, url))
    if advisory_bits:
        advisory_clause = (
            " (Each one is linked to its public advisory: "
            + "; ".join(advisory_bits)
            + ".)"
        )
    else:
        advisory_clause = ""

    body_lines = [
        f"This week we found {_link(str(n), receipt_url) if receipt_url else str(n)} "
        f"threats to {site}. {_link(str(c), receipt_url) if receipt_url else str(c)} "
        f"were critical: out-of-date {stack_list} with known holes serious enough to "
        f"take down a company's whole IT system.{advisory_clause}",
        "",
    ]

    mode = settings.fix_mode
    if mode is ApplyMode.auto_when_checks_pass:
        body_lines.append(
            f"You chose to let us fix this kind of problem automatically, so we did. "
            f"{stack_list} are now on patched versions and your site passed its own "
            f"checks afterwards. Here is the report; you can send it to your IT manager, "
            f"who can reverse our change with one click. "
            f"{_link('Undo', undo_fix_url) if undo_fix_url else '[Undo link]'}"
        )
    elif mode is ApplyMode.approve_each:
        body_lines.append(
            f"You chose to approve fixes yourself. We have built the fix and it is "
            f"waiting for your approval here. {_link('Approve the fix', pr_url) if pr_url else '[PR link]'} "
            f"Until you approve it, the hole is still open; we have reduced the risk at "
            f"the edge as described below."
        )
    else:  # never
        body_lines.append(
            f"You chose that we never touch your code. Here is exactly what to fix and how. "
            f"{_link('Report', fix_report_url) if fix_report_url else '[Report link]'} "
            f"We have reduced the risk at the edge as described below."
        )

    if shield:
        blocked = int(shield.get("blocked_addresses") or 0)
        source_url = str(shield.get("source_url") or "")
        source_name = str(shield.get("source_name") or "a public campaign list")
        body_lines.extend([
            "",
            f"We also stopped an attack in progress. It was blocking addresses known to be "
            f"part of a widely reported campaign "
            f"({_link(source_name, source_url) if source_url else source_name}). "
            f"We blocked {_link(str(blocked), receipt_url) if receipt_url else str(blocked)} "
            f"addresses that were attacking your site. Your own addresses, your payment "
            f"provider and Cloudflare were never blocked. If this caused any problem, undo "
            f"it here with one tap. "
            f"{_link('Undo', undo_shield_url) if undo_shield_url else '[Undo link]'}",
        ])

    body_lines.extend([
        "",
        "Nothing from your logs was kept. We read them, acted, and deleted them. "
        f"{_link('Full receipt', receipt_url) if receipt_url else '[Link to the full receipt]'}",
    ])

    for item in critical:
        rating = str(item.get("rating") or "").lower()
        if rating and rating not in {"critical", "known_exploited"}:
            raise ValueError("critical paragraph requires a critical public advisory rating")

    return {"subject": subject, "body": "\n".join(body_lines)}


class FixtureEmailTransport:
    """In-memory sender used by tests and dogfood. Records every send."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, *, to: str, subject: str, body: str) -> dict[str, Any]:
        row = {"to": to, "subject": subject, "body": body}
        self.sent.append(row)
        return {"sent": True, "transport": "fixture", "to": to, "subject": subject}


DEFAULT_FIXTURE_TRANSPORT = FixtureEmailTransport()


def send_owner_update(
    email: dict[str, str],
    *,
    to: str,
    transport: Any | None = None,
) -> dict[str, Any]:
    """Call the sender. Weekly/quiet-week paths use the same door."""
    sender = transport or DEFAULT_FIXTURE_TRANSPORT
    result = sender.send(to=to, subject=email["subject"], body=email["body"])
    return {
        "sent": bool(result.get("sent")),
        "transport": result.get("transport") or type(sender).__name__,
        "to": to,
        "subject": email["subject"],
        "body": email["body"],
        "receipt": {
            "product": "Autumbra",
            "kind": "owner_email",
            "to": to,
            "subject": email["subject"],
            "transport": result.get("transport") or type(sender).__name__,
        },
    }
