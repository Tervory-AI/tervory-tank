"""Public business gold candidates from independent, local evidence snapshots."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
MAX_CANDIDATES = 200
MAX_SNAPSHOT_BYTES = 20_000_000
ROOT = Path(__file__).resolve().parent.parent


def _text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"+1{digits}" if len(digits) == 10 else ""


def _host(value: Any) -> str:
    parsed = urlsplit(str(value or ""))
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.port not in (None, 443) or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,63}", host):
        return ""
    if host.endswith((".localhost", ".internal", ".local", ".invalid", ".test")):
        return ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    return ""


def _name_key(name: str) -> str:
    words = re.sub(r"[^a-z0-9& ]+", " ", name.lower()).split()
    suffixes = {
        "the", "inc", "incorporated", "llc", "ltd", "limited", "co", "corp",
        "corporation", "company", "lp", "llp", "pllc", "pc", "dba",
    }
    return " ".join(word for word in words if word not in suffixes).replace("&", "and")


def source_catalogue() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "engines").glob("*/gold_lists.json")):
        for source in json.loads(path.read_text(encoding="utf-8")):
            sources[source["id"]] = source
    return sources


def candidates(
    snapshots: Iterable[dict[str, Any]], *, region: str, limit: int = 200,
    today: date | None = None, catalogue: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if region not in ("us-east", "za"):
        raise ValueError("unsupported region")
    limit = max(0, min(limit, MAX_CANDIDATES))
    if not limit:
        return []
    today = today or date.today()
    catalogue = source_catalogue() if catalogue is None else catalogue
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        try:
            examples = _examples(snapshot, region, today, catalogue)
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        for example in examples:
            identity = hashlib.sha256(json.dumps(example, sort_keys=True).encode()).hexdigest()
            if identity in seen:
                continue
            seen.add(identity)
            output.append(example)
            if len(output) == limit:
                return output
    return output


def _examples(
    snapshot: dict[str, Any], region: str, today: date, catalogue: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if (
        snapshot.get("tenant_id") != PLATFORM_TENANT or snapshot.get("public") is not True
        or snapshot.get("region") != region or snapshot.get("record_kind") != "business"
        or snapshot.get("entity_type") not in ("corporation", "llc", "registered_company")
    ):
        return []
    source = catalogue[snapshot["source_id"]]
    if source["region"] != region:
        return []
    official, site = snapshot["official"], snapshot["site"]
    source_url = urlsplit(official["source_url"])
    if (
        _host(official["source_url"]) not in source["hosts"]
        or not any(source_url.path.startswith(prefix) for prefix in source["path_prefixes"])
        or official.get("active") is not True
        or not date.fromisoformat(official["observed_on"]) <= today <= date.fromisoformat(official["valid_until"])
        or (today - date.fromisoformat(official["observed_on"])).days > 90
        or not 0 <= (today - date.fromisoformat(site["observed_on"])).days <= 30
        or site.get("blocked") is not False or site.get("status") != 200
    ):
        return []
    website = site["website"]
    if not _host(website) or _host(website) != _host(site["source_url"]):
        return []
    if official.get("website") and _host(official["website"]) != _host(website):
        return []
    fields = ("name", "address", "city", "state", "zip")
    if any(not _text(official.get(key)) or _text(official[key]) != _text(site.get(key)) for key in fields):
        return []
    phone = _phone(official["phone"])
    if not phone or phone != _phone(site["phone"]) or not official.get("id"):
        return []
    name_key = _name_key(official["name"])
    if not name_key or not re.fullmatch(r"[A-Z]{2}", official["state"]) or not re.fullmatch(r"\d{5}", official["zip"]):
        return []
    raw = {key: " ".join(str(official[key]).split()) for key in fields}
    raw["phone"] = phone
    normal = {
        "fields": {
            key: {"value": value}
            for key, value in {"name_key": name_key, "city": raw["city"], "state": raw["state"]}.items()
        }
    }
    registry = {
        "id": official["id"], "name_key": name_key,
        "city": raw["city"].lower(), "state": raw["state"].lower(),
    }
    profile = {
        "name": {"value": official["name"]},
        "city": {"value": official["city"]},
        "state": {"value": official["state"]},
        "registry_match": {"value": official["id"]},
        "website": {"value": website},
        "phones": {"value": [phone]},
    }
    cases = [
        ("base.find_site", {**raw, "website": website}, {
            "website": {
                "value": website.rstrip("/") if urlsplit(website).path in ("", "/") else website,
                "source": "input:verified", "confidence": 85,
            },
        }),
        ("base.verify", {"raw": raw, "profile": profile}, {"checks": {"phone_matches_site": True}}),
        ("base.normalize", raw, {
            "match_key": f"{name_key}|{raw['city'].lower()}|{raw['state'].lower()}",
        }),
        ("base.resolve", {"record": normal, "registry": [registry]}, {
            "verdict": "matched", "match": registry, "score": 100.0,
        }),
    ]
    return [
        {
            "skill_id": skill, "input": value, "expected": expected,
            "label_source": f"{source['label']} · {official['source_url']} · {official['observed_on']}",
            "region": region, "public": True,
        }
        for skill, value, expected in cases
    ]


def read_candidates(*, limit: int, region: str) -> list[dict[str, Any]]:
    if region not in ("us-east", "za"):
        raise ValueError("unsupported region")
    path = Path(os.environ.get("DATA_DIR", "/data")) / "gold" / region / "official-matches.jsonl"
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("invalid evidence snapshot")

    def rows() -> Iterable[dict[str, Any]]:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    yield value

    return candidates(rows(), region=region, limit=limit)
