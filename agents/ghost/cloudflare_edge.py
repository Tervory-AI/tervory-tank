"""Enforce-only Rulesets control. Live transport remains sealed pending egress approval.

Only fixed rules from shields.rule_for cross this adapter. No raw logs, models,
provider response bodies, or credentials belong in its durable shield table.
"""
from __future__ import annotations

import ipaddress
import re
from typing import Callable

import httpx

from .fixture_edge import FixtureEdgeControl, _now
from .shields import ALLOWED_ZONES, PHASES, ShieldRequest, rule_for, zone_of

# A code hold, deliberately not an environment switch. A separately reviewed
# egress change must replace this hold and provide an approved health probe.
CLOUDFLARE_EGRESS_APPROVED = False
API_ROOT = "https://api.cloudflare.com/client/v4"
TOKEN_ENV = "CLOUDFLARE_API_TOKEN_ENFORCE"


class CloudflareEdgeError(RuntimeError):
    """Fixed error only: never expose HTTP headers, URLs with credentials or bodies."""


def _id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise CloudflareEdgeError("Invalid Cloudflare resource identifier.")
    return value


class CloudflareEdgeControl(FixtureEdgeControl):
    """Same durable apply/undo/health interface as the fixture, scoped to one site.

    While egress is held, only httpx.MockTransport is accepted. This prevents
    direct construction from bypassing the runtime selector's sealed default.
    Site health is supplied by an approved probe; absent/failed probes fail closed.
    API reachability alone is never reported as site health.
    """

    control_name = "cloudflare"

    def __init__(self, *, tenant_id: str, site: str, transport: httpx.BaseTransport,
                 token: str = "", health_probe: Callable[[], bool] | None = None):
        self._zone(site)
        if not CLOUDFLARE_EGRESS_APPROVED and not isinstance(transport, httpx.MockTransport):
            raise CloudflareEdgeError("Cloudflare egress is not approved.")
        super().__init__(tenant_id=tenant_id, site=site)
        self._client = httpx.Client(
            base_url=API_ROOT + "/", transport=transport, timeout=2.0,
            follow_redirects=False, trust_env=False,
            headers={"Authorization": "Bearer " + token} if token else {},
        )
        self._health_probe = health_probe

    @staticmethod
    def _zone(site: str) -> str:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", site):
            raise ValueError("Site is not an allowed Cloudflare host.")
        zone = zone_of(site)
        if zone not in ALLOWED_ZONES or any(not label for label in site.split(".")):
            raise ValueError("Site is not an allowed Cloudflare zone.")
        return zone

    def _request(self, method: str, path: str, *, body=None, missing_ok=False):
        # Paths are constructed locally from validated hex identifiers only.
        try:
            response = self._client.request(method, path, json=body)
            if missing_ok and response.status_code == 404:
                return None
            if not response.is_success:
                raise CloudflareEdgeError("Cloudflare request failed.")
            data = response.json()
            if not isinstance(data, dict) or data.get("success") is not True:
                raise CloudflareEdgeError("Cloudflare request failed.")
            return data["result"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise CloudflareEdgeError("Cloudflare request failed.") from None

    def _apply(self, *, kind: str, site: str, ref: str, address=None, path=None) -> dict:
        zone = self._zone(site)
        if site != self.site:
            raise ValueError("Control is bound to another site.")
        if kind not in {"block_ip", "rate_limit"}:
            raise ValueError("Unsupported Cloudflare shield.")
        request = ShieldRequest(site=site, kind=kind, address=address, path=path)
        if kind == "block_ip":
            address = str(ipaddress.ip_address(request.address or ""))
        if not re.fullmatch(r"(?:enforce|approve)-[a-f0-9]{16}", ref):
            raise ValueError("Invalid Autumbra rule reference.")
        rule = rule_for(kind, site, request.path, ref, address=address)
        with self._lock:
            zones = self._request("GET", "zones?name=" + zone)
            if not isinstance(zones, list) or len(zones) != 1 or zones[0].get("name") != zone:
                raise CloudflareEdgeError("Allowed Cloudflare zone was not found.")
            zone_id = _id(zones[0].get("id"))
            entry = f"zones/{zone_id}/rulesets/phases/{PHASES[kind]}/entrypoint"
            ruleset = self._request("GET", entry, missing_ok=True)
            if ruleset is None:
                # Create only a missing phase entrypoint, never PUT an existing
                # ruleset (which would replace somebody else's protections).
                result = self._request("POST", f"zones/{zone_id}/rulesets", body={
                    "name": "Autumbra " + PHASES[kind], "kind": "zone",
                    "phase": PHASES[kind], "rules": [rule],
                })
            else:
                ruleset_id = _id(ruleset.get("id"))
                result = self._request("POST", f"zones/{zone_id}/rulesets/{ruleset_id}/rules", body=rule)
            ruleset_id = _id(result.get("id"))
            matches = [r for r in result.get("rules", []) if r.get("ref") == ref]
            if len(matches) != 1 or matches[0].get("expression") != rule["expression"]:
                raise CloudflareEdgeError("Cloudflare did not confirm the added rule.")
            rule_id = _id(matches[0].get("id"))
            row = {
                "control": self.control_name, "rule_id": rule_id, "zone_id": zone_id,
                "ruleset_id": ruleset_id, "site": site, "ref": ref, "kind": kind,
                "address": address, "path": request.path, "up_at": _now(),
                "expression": rule["expression"],
            }
            self.blocked[rule_id] = row
            return dict(row)

    def apply_block_ip(self, *, site: str, address: str, ref: str) -> dict:
        return self._apply(kind="block_ip", site=site, address=address, ref=ref)

    def apply_rate_limit(self, *, site: str, path: str, ref: str) -> dict:
        return self._apply(kind="rate_limit", site=site, path=path, ref=ref)

    def undo(self, rule_id: str) -> dict:
        with self._lock:
            row = self.blocked.get(rule_id)
            if not row or row.get("control") != self.control_name or row.get("site") != self.site:
                raise LookupError("No owned Cloudflare shield found.")
            self._zone(row["site"])
            root = f"zones/{_id(row['zone_id'])}/rulesets/{_id(row['ruleset_id'])}"
            ruleset = self._request("GET", root)
            owned = [r for r in ruleset.get("rules", []) if r.get("id") == _id(rule_id)]
            if len(owned) != 1 or any(owned[0].get(k) != row[k] for k in ("ref", "expression")):
                raise CloudflareEdgeError("Cloudflare shield ownership could not be verified.")
            self._request("DELETE", root + "/rules/" + _id(rule_id))
            del self.blocked[rule_id]
            return {**row, "ended_at": _now(), "state": "undone"}

    def health_check(self) -> bool:
        try:
            return self._health_probe is not None and self._health_probe() is True
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()
