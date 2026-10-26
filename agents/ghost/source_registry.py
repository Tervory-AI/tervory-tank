"""Public, legitimate threat sources. Free first. No dark web. No onion crawl."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# First free entries. Credit line appears on every receipt a source contributes to.
SOURCES: list[dict[str, Any]] = [
    {"id": "ransomware_live", "name": "ransomware.live", "owner": "ransomware.live",
     "licence": "public research feed", "url": "https://ransomware.live",
     "kind": "leak_tracker", "free": True, "refresh": "hourly",
     "credit": "ransomware.live", "accepts_support": True},
    {"id": "ransomlook", "name": "RansomLook", "owner": "RansomLook",
     "licence": "public research feed", "url": "https://www.ransomlook.io",
     "kind": "leak_tracker", "free": True, "refresh": "hourly",
     "credit": "RansomLook", "accepts_support": True},
    {"id": "ransomwatch", "name": "ransomwatch", "owner": "joshhighet",
     "licence": "MIT", "url": "https://github.com/joshhighet/ransomwatch",
     "kind": "leak_tracker", "free": True, "refresh": "hourly",
     "credit": "ransomwatch", "accepts_support": True},
    {"id": "urlhaus", "name": "abuse.ch URLhaus", "owner": "abuse.ch",
     "licence": "CC0", "url": "https://urlhaus.abuse.ch",
     "kind": "attacking_addresses", "free": True, "refresh": "hourly",
     "credit": "abuse.ch URLhaus", "accepts_support": True},
    {"id": "threatfox", "name": "abuse.ch ThreatFox", "owner": "abuse.ch",
     "licence": "CC0", "url": "https://threatfox.abuse.ch",
     "kind": "attacking_addresses", "free": True, "refresh": "hourly",
     "credit": "abuse.ch ThreatFox", "accepts_support": True},
    {"id": "feodo", "name": "abuse.ch Feodo Tracker", "owner": "abuse.ch",
     "licence": "CC0", "url": "https://feodotracker.abuse.ch",
     "kind": "attacking_addresses", "free": True, "refresh": "hourly",
     "credit": "abuse.ch Feodo", "accepts_support": True},
    {"id": "malwarebazaar", "name": "abuse.ch MalwareBazaar", "owner": "abuse.ch",
     "licence": "CC0", "url": "https://bazaar.abuse.ch",
     "kind": "malware", "free": True, "refresh": "hourly",
     "credit": "abuse.ch MalwareBazaar", "accepts_support": True},
    {"id": "spamhaus_drop", "name": "Spamhaus DROP", "owner": "Spamhaus",
     "licence": "Spamhaus terms", "url": "https://www.spamhaus.org/drop/",
     "kind": "attacking_addresses", "free": True, "refresh": "daily",
     "credit": "Spamhaus DROP", "accepts_support": True},
    {"id": "shadowserver", "name": "Shadowserver daily reports", "owner": "Shadowserver",
     "licence": "register ranges", "url": "https://www.shadowserver.org",
     "kind": "reports", "free": True, "refresh": "daily",
     "credit": "Shadowserver", "accepts_support": True},
    {"id": "tor_exits", "name": "Tor exit list", "owner": "Tor Project",
     "licence": "public", "url": "https://check.torproject.org/exit-addresses",
     "kind": "attacking_addresses", "free": True, "refresh": "hourly",
     "credit": "Tor Project exit list", "accepts_support": False},
    {"id": "cisa_kev", "name": "CISA Known Exploited Vulnerabilities", "owner": "CISA",
     "licence": "public domain (US gov)", "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
     "kind": "vulnerability", "free": True, "refresh": "hourly",
     "credit": "CISA KEV", "accepts_support": False},
    {"id": "osv", "name": "OSV", "owner": "Google Open Source Insights",
     "licence": "Apache-2.0 / public API", "url": "https://osv.dev",
     "kind": "vulnerability", "free": True, "refresh": "on_inventory",
     "credit": "OSV", "accepts_support": False},
    {"id": "ghsa", "name": "GitHub Advisory Database", "owner": "GitHub",
     "licence": "CC-BY-4.0", "url": "https://github.com/advisories",
     "kind": "vulnerability", "free": True, "refresh": "hourly",
     "credit": "GitHub Advisory Database", "accepts_support": False},
    {"id": "nvd", "name": "NVD", "owner": "NIST",
     "licence": "public domain (US gov)", "url": "https://nvd.nist.gov",
     "kind": "vulnerability", "free": True, "refresh": "hourly",
     "credit": "NVD", "accepts_support": False},
    {"id": "hibp_domain", "name": "Have I Been Pwned domain search", "owner": "Troy Hunt",
     "licence": "HIBP terms", "url": "https://haveibeenpwned.com",
     "kind": "breach", "free": True, "refresh": "daily",
     "credit": "Have I Been Pwned", "accepts_support": True},
    {"id": "researcher_leads", "name": "Founder-approved researcher leads", "owner": "Tervory founder list",
     "licence": "public posts / RSS only", "url": "",
     "kind": "lead", "free": True, "refresh": "hourly",
     "credit": "named researcher (per receipt)", "accepts_support": False,
     "alone_never_acts": True},
]


def registry_public() -> list[dict[str, Any]]:
    """Settings-page shape: no secrets, includes empty track-record slots."""
    out = []
    for src in SOURCES:
        row = deepcopy(src)
        row.setdefault("last_seen", None)
        row.setdefault("track", {"first": 0, "confirmed": 0, "wrong": 0})
        out.append(row)
    return out


def source_by_id(source_id: str) -> dict[str, Any] | None:
    for src in SOURCES:
        if src["id"] == source_id:
            return deepcopy(src)
    return None


def credit_for(source_ids: list[str]) -> list[dict[str, str]]:
    credits = []
    for sid in source_ids:
        src = source_by_id(sid)
        if src:
            credits.append({"id": src["id"], "credit": src["credit"], "url": src.get("url") or ""})
    return credits


def may_act_on_sources(
    source_ids: list[str],
    *,
    act_on_single_source: bool,
) -> tuple[bool, str]:
    """Cross-check: one source alone never triggers a shield unless the client set it."""
    cleaned = [s for s in source_ids if source_by_id(s)]
    if not cleaned:
        return False, "no known source"
    # Researcher leads never act alone.
    if len(cleaned) == 1 and source_by_id(cleaned[0]).get("alone_never_acts"):
        return False, "lead sources never act alone"
    if len(cleaned) == 1 and not act_on_single_source:
        return False, "single source; client requires cross-check"
    return True, "ok"


def record_track(store, tenant_id: str, source_id: str, outcome: str) -> dict[str, Any]:
    """outcome in {first, confirmed, wrong}. Visible weights on the registry page."""
    if outcome not in {"first", "confirmed", "wrong"}:
        raise ValueError("Unknown track outcome.")
    key = "autumbra_source_track"
    tracks = store.get_state(tenant_id, key, {}) or {}
    if not isinstance(tracks, dict):
        tracks = {}
    row = dict(tracks.get(source_id) or {"first": 0, "confirmed": 0, "wrong": 0})
    row[outcome] = int(row.get(outcome, 0)) + 1
    tracks[source_id] = row
    store.set_state(tenant_id, key, tracks)
    return row


def registry_with_weights(store, tenant_id: str) -> list[dict[str, Any]]:
    tracks = store.get_state(tenant_id, "autumbra_source_track", {}) or {}
    out = registry_public()
    for row in out:
        row["track"] = dict(tracks.get(row["id"]) or {"first": 0, "confirmed": 0, "wrong": 0})
    return out


def sources_accepting_support() -> list[dict[str, str]]:
    return [{"id": s["id"], "name": s["name"], "url": s.get("url") or ""} for s in SOURCES if s.get("accepts_support")]
