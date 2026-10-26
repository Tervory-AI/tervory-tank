"""Public field evidence and Base training outputs; no industry rules or models."""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from selectolax.parser import HTMLParser

observations: ContextVar[list[dict[str, Any]] | None] = ContextVar("base_field_observations", default=None)
FIELDS = ("website", "phone", "email", "socials")
EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")


def public_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return None
        return urlunsplit((p.scheme, p.netloc, p.path or "/", "", ""))
    except ValueError:
        return None


def phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) == 10 or len(digits) == 11 and digits.startswith("1") else ""


def observe(url: str, html: str) -> None:
    target = observations.get()
    address = public_url(url)
    if target is None or not address:
        return
    tree = HTMLParser(html[:600_000])
    links = []
    for anchor in tree.css("a[href]"):
        href = anchor.attributes.get("href", "")
        if value := public_url(urljoin(url, href)):
            links.append(value)
    for node in tree.css("script,style,noscript,template"):
        node.decompose()
    text = tree.text(separator=" ")
    emails = {match.lower() for match in EMAIL.findall(text)}
    for anchor in tree.css('a[href^="mailto:"]'):
        emails.update(match.lower() for match in EMAIL.findall(anchor.attributes.get("href", "")))
    target.append({"source_url": address, "checked_at": datetime.now(timezone.utc).isoformat(),
                   "emails": sorted(emails), "phones": sorted({phone(match) for match in PHONE.findall(text)} - {""}),
                   "links": list(dict.fromkeys(links))[:200]})


def field(value: Any = None, source: str | None = None, checked: str | None = None, reason: str | None = None) -> dict[str, Any]:
    return {"value": value, "source_url": source, "checked_at": checked, "verified": bool(value and source and checked),
            "reason": reason if reason else None if value and source and checked else "No source and check date were recorded."}


def row_fields(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if row.get("status") not in {None, "done", "failed"}:
        return {name: field(reason="Checks are still running.") for name in FIELDS}
    profile, passes = row.get("profile") or {}, row.get("passes") or {}
    proof = passes.get("2b", {}).get("field_observations") or []
    checks = passes.get("7", {}).get("checks") or {}
    blocked = passes.get("2b", {}).get("access_error")
    blocked_url = blocked.get("url") if isinstance(blocked, dict) and blocked.get("status") == "blocked" else None
    blocked_sites = passes.get("2a", {}).get("blocked_by_check") or []
    if not blocked_url and isinstance(blocked_sites, list) and blocked_sites:
        blocked_url = blocked_sites[0]
    if blocked_url:
        return {name: field(source=public_url(blocked_url), reason="blocked") for name in FIELDS}
    if passes.get("2b", {}).get("archive_date"):
        return {name: field(reason="Only an archived page was available; current details were not verified.") for name in FIELDS}
    result = {name: field(reason="Not found in the public pages checked.") for name in FIELDS}
    website = (profile.get("website") or {}).get("value")
    wanted_phone = (profile.get("phone") or {}).get("value")
    emails = (profile.get("emails") or {}).get("value") or []
    socials = (profile.get("socials") or {}).get("value") or {}
    if not isinstance(emails, list):
        emails = [emails]
    wanted_links = list(socials.values()) if isinstance(socials, dict) else []
    for observed in proof:
        url, checked = public_url(observed.get("source_url")), observed.get("checked_at")
        if not url or not checked:
            continue
        if website and public_url(website) and (urlsplit(url).hostname or "").removeprefix("www.") == (urlsplit(website).hostname or "").removeprefix("www."):
            if not result["website"]["verified"]:
                result["website"] = field(website, url, checked)
        if phone(wanted_phone) and phone(wanted_phone) in observed.get("phones", []) and checks.get("phone_matches_site") is not False:
            result["phone"] = field(wanted_phone, url, checked)
        matches = [email for email in emails if str(email).lower() in observed.get("emails", [])]
        if matches and checks.get("email_domain_matches_site") is not False:
            # Keep each address's own source in items, not a borrowed homepage URL.
            items = result["email"].get("items", [])
            items += [field(email, url, checked) for email in matches if email not in [item["value"] for item in items]]
            result["email"] = {**field([item["value"] for item in items], items[0]["source_url"], items[0]["checked_at"]), "items": items}
        matches = [link for link in wanted_links if public_url(link) in observed.get("links", [])]
        if matches:
            items = result["socials"].get("items", [])
            items += [field(link, url, checked) for link in matches if link not in [item["value"] for item in items]]
            result["socials"] = {**field([item["value"] for item in items], items[0]["source_url"], items[0]["checked_at"]), "items": items}
    for name, check in (("phone", "phone_matches_site"), ("email", "email_domain_matches_site")):
        if checks.get(check) is False:
            result[name] = field(reason="The final cross-check disagreed with the source.")
    contacts = (profile.get("contacts") or {}).get("value") or {}
    if isinstance(contacts, dict) and contacts.get("domain_accepts_mail") is False:
        result["email"] = field(reason="The mail domain does not accept email.")
    social_block = passes.get("4", {}).get("access_error") or {}
    if social_block.get("status") == "blocked":
        result["socials"] = field(source=public_url(social_block.get("url")), reason="blocked")
    if not proof:
        # Legacy rows retain their actual observation, never the current time.
        old = passes.get("2b", {}).get("gold_observation") or {}
        if old.get("status") == 200 and old.get("blocked") is False and not passes.get("2b", {}).get("archive_date"):
            url, checked = public_url(old.get("source_url")), old.get("observed_on")
            if website and url and checked:
                result["website"] = field(website, url, checked)
            if phone(wanted_phone) and phone(wanted_phone) in {phone(v) for v in old.get("phones", [])} and checks.get("phone_matches_site") is not False:
                result["phone"] = field(wanted_phone, url, checked)
    if row.get("status") == "failed":
        for name in FIELDS:
            if not result[name]["verified"]:
                result[name] = field(reason="A pipeline step failed before this field could be checked.")
    return result
