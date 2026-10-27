"""Owner update email — built by code from receipts. No model. Plain English only.

Exact founder wording (item 8 phrases). Founder brief is in-repo byte-identical.
"critical" only with a linked advisory rating. No literal "[...]" placeholders in
a sent body. Recipient from client settings. Weekly schedule is a real job entry.
"""
from __future__ import annotations

import re
from typing import Any

from .client_settings import ApplyMode, ClientAutumbraSettings

_PLACEHOLDER_RE = re.compile(r"\[[^\]]+\]")


def _link(label: str, url: str) -> str:
    url = (url or "").strip()
    label = (label or "").strip()
    if not url:
        raise ValueError(f"missing URL for link label {label!r}")
    return f"{label} ({url})"


def _fmt_count(n: int) -> str:
    return f"{int(n):,}"


def _assert_no_placeholders(body: str) -> None:
    if _PLACEHOLDER_RE.search(body or ""):
        raise ValueError("owner email body must not contain [...] placeholders")


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

    cleaned_critical: list[dict[str, Any]] = []
    for item in critical or []:
        if not isinstance(item, dict):
            raise ValueError("critical item must be an object")
        rating = str(item.get("rating") or "").lower()
        url = str(item.get("advisory_url") or "").strip()
        if rating and rating not in {"critical", "known_exploited"}:
            raise ValueError("critical paragraph requires a critical public advisory rating")
        if not rating or not url:
            raise ValueError(
                "critical means a public advisory rates it critical and the link proves it"
            )
        cleaned_critical.append(item)
    c = len(cleaned_critical)
    subject = f"Autumbra update for {site}: {n} threats found, {c} critical"

    if not receipt_url:
        raise ValueError("owner update requires receipt_url (no placeholders)")

    # Quiet week — brief: "Quiet week. [1,204] checks, 0 threats, 0 actions."
    if n == 0 and c == 0 and not shield:
        checks = int(checks_run if checks_run is not None else 0)
        body = (
            f"Quiet week. {_link(_fmt_count(checks), receipt_url)} "
            f"checks, 0 threats, 0 actions.\n\n"
            "Nothing from your logs was kept. We read them, acted, and deleted them. "
            f"{_link('Full receipt', receipt_url)}"
        )
        _assert_no_placeholders(body)
        return {"subject": subject, "body": body}

    stacks: list[str] = []
    linked_stacks: list[str] = []
    for item in cleaned_critical:
        name = str(item.get("stack") or item.get("name") or "software")
        stacks.append(name)
        linked_stacks.append(_link(name, str(item["advisory_url"])))
    if not stacks:
        stack_list = "software"
        stack_list_linked = "software"
    elif len(stacks) == 1:
        stack_list = stacks[0]
        stack_list_linked = linked_stacks[0]
    else:
        stack_list = ", ".join(stacks[:-1]) + " and " + stacks[-1]
        stack_list_linked = ", ".join(linked_stacks[:-1]) + " and " + linked_stacks[-1]

    advisory_clause = " (Each linked to its public advisory.)"

    body_lines = [
        f"This week we found {_link(str(n), receipt_url)} "
        f"threats to {site}. {_link(str(c), receipt_url)} "
        f"were critical: out-of-date {stack_list_linked} with known holes serious enough to "
        f"take down a company's whole IT system.{advisory_clause}",
        "",
    ]

    mode = settings.fix_mode
    if mode is ApplyMode.auto_when_checks_pass:
        if not undo_fix_url:
            raise ValueError("auto fix paragraph requires undo_fix_url (no placeholders)")
        body_lines.append(
            f"You chose to let us fix this kind of problem automatically, so we did. "
            f"{stack_list} are now on patched versions and your site passed its own "
            f"checks afterwards. Here is the report; you can send it to your IT manager, "
            f"who can reverse our change with one click. "
            f"{_link('Undo', undo_fix_url)}"
        )
    elif mode is ApplyMode.approve_each:
        if not pr_url:
            raise ValueError("approve-each paragraph requires pr_url (no placeholders)")
        body_lines.append(
            f"You chose to approve fixes yourself. We have built the fix and it is "
            f"waiting for your approval here. {_link('Approve the fix', pr_url)} "
            f"Until you approve it, the hole is still open; we have reduced the risk at "
            f"the edge as described below."
        )
    else:
        if not fix_report_url:
            raise ValueError("never paragraph requires fix_report_url (no placeholders)")
        body_lines.append(
            f"You chose that we never touch your code. Here is exactly what to fix and how. "
            f"{_link('Report', fix_report_url)} "
            f"We have reduced the risk at the edge as described below."
        )

    if shield:
        blocked = int(shield.get("blocked_addresses") or 0)
        source_url = str(shield.get("source_url") or "").strip()
        source_name = str(shield.get("source_name") or "public source").strip()
        if not source_url:
            raise ValueError("shield paragraph requires source_url (no placeholders)")
        if not undo_shield_url:
            raise ValueError("shield paragraph requires undo_shield_url (no placeholders)")
        public_source = _link(source_name, source_url)
        body_lines.extend([
            "",
            f"We also stopped an attack in progress. It was part of a widely reported "
            f"campaign ({public_source}). "
            f"We blocked {_link(str(blocked), receipt_url)} "
            f"addresses that were attacking your site. Your own addresses, your payment "
            f"provider and Cloudflare were never blocked. If this caused any problem, undo "
            f"it here with one tap. "
            f"{_link('Undo', undo_shield_url)}",
        ])

    body_lines.extend([
        "",
        "Nothing from your logs was kept. We read them, acted, and deleted them. "
        f"{_link('Full receipt', receipt_url)}",
    ])

    body = "\n".join(body_lines)
    _assert_no_placeholders(body)
    return {"subject": subject, "body": body}


class FixtureEmailTransport:
    """In-memory sender used by tests and dogfood. Records every send."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, *, to: str, subject: str, body: str) -> dict[str, Any]:
        if not to:
            raise ValueError("recipient must come from the client's settings")
        if to == "owner@example.test":
            raise ValueError("recipient must come from the client's settings")
        _assert_no_placeholders(body)
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
    if not to:
        raise ValueError("recipient must come from the client's settings")
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
