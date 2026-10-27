"""Tenant result counts, comparison and expense arithmetic shared by JSON and CSV."""
from __future__ import annotations

from collections import defaultdict
import csv
from decimal import Decimal
import io
import json
import re
from typing import Any
from urllib.parse import urlsplit

from base_evidence import FIELDS, phone

COUNTS = ("attempted", "website", "phone", "email", "email_and_phone", "email_only", "phone_only", "neither", "verified", "failed")
RUNGS = {1: "paid model", 2: "cheaper model", 3: "code", 4: "cache"}


def obj(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One business result per licence, newest attempted version; CSV rows stay separate."""
    chosen: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: (str(r["checked_at"]), str(r["record_id"]))):
        chosen[row.get("licence_key") or str(row["record_id"])] = row
    return list(chosen.values())


def selected(row: dict[str, Any], states: list[str], kinds: list[str], collectors: bool) -> bool:
    return (not states or row["state"] in states) and (not kinds or row["licence_type"] in kinds) and (
        collectors or row["licence_type"] != "03"
    )


def flags(row: dict[str, Any]) -> dict[str, bool]:
    fields = obj(row["fields"])
    found = {name: bool(fields[name].get("verified")) for name in FIELDS}
    return {"attempted": True, **found,
            "email_and_phone": found["email"] and found["phone"],
            "email_only": found["email"] and not found["phone"],
            "phone_only": found["phone"] and not found["email"],
            "neither": not found["email"] and not found["phone"],
            "verified": any(found[name] for name in ("website", "phone", "email")),
            "failed": row.get("status", "done") in {"done", "failed"} and any(not found[name] for name in FIELDS)}


def failure_reasons(row: dict[str, Any]) -> list[str]:
    if row.get("status", "done") not in {"done", "failed"}:
        return []
    return sorted({str(value.get("reason") or "No verified source.") for value in obj(row["fields"]).values() if not value.get("verified")})


def counts(reference: list[dict[str, Any]], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    def group(row: dict[str, Any]) -> dict[str, Any]:
        key = (row["state"], row["licence_type"])
        return groups.setdefault(key, {"state": key[0], "licence_type": key[1], "licensees": 0,
                                       **{metric: 0 for metric in COUNTS}, "failed_by_reason": {}})
    for row in reference:
        group(row)["licensees"] += 1
    for row in latest(results):
        item = group(row)
        for metric, present in flags(row).items():
            if metric in COUNTS:
                item[metric] += int(present)
        for reason in failure_reasons(row):
            item["failed_by_reason"][reason] = item["failed_by_reason"].get(reason, 0) + 1
    return [groups[key] for key in sorted(groups)]


def cost_rows(results: list[dict[str, Any]], ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = {str(row["record_id"]): row for row in results}
    groups: dict[tuple[str, str, int], dict[str, Any]] = {}
    denominator: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in results:
        if flags(row)["verified"]:
            denominator[(row["state"], str(row["checked_at"])[:7])].add(row.get("licence_key") or str(row["record_id"]))
    seen: set[str] = set()
    for entry in ledger:
        identity = str(entry["id"])
        if identity in seen:
            continue
        seen.add(identity)
        record = records.get(str(entry.get("record_id")))
        if record is None:
            continue
        key = (record["state"], str(entry["ts"])[:7], 4 if entry.get("cache_hit") else int(entry["rung"]))
        item = groups.setdefault(key, {"state": key[0], "month": key[1], "rung": key[2], "rung_label": RUNGS.get(key[2], "other"),
                                       "known_cost": Decimal(0), "unpriced": 0, "ledger_ids": [], "vendors": set()})
        item["ledger_ids"].append(identity)
        item["vendors"].add(entry.get("vendor") or "")
        if entry.get("cost_status") == "not_set" or entry["cost_usd"] is None:
            item["unpriced"] += 1
        else:
            item["known_cost"] += Decimal(str(entry["cost_usd"]))
    out = []
    for key, item in sorted(groups.items()):
        n = len(denominator[(key[0], key[1])])
        known = item.pop("known_cost")
        total = None if item["unpriced"] else known
        out.append({**item, "verified_records": n, "known_cost_usd": str(known),
                    "cost_usd": str(total) if total is not None else None,
                    "cost_per_verified_record": str(known / n) if n else None,
                    "vendors": sorted(item["vendors"]),
                    "status": "price not set" if item["unpriced"] else "no verified records" if not n else "priced"})
    return out


def matches(row: dict[str, Any], metric: str, reason: str | None = None) -> bool:
    return (flags(row).get(metric, False) if metric != "all" else True) and (not reason or reason in failure_reasons(row))


def csv_text(rows: list[dict[str, Any]], columns: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column)
            text = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else "" if value is None else str(value)
            if re.match(r"^[\s\ufeff]*[=+@-]|^[\t\r\n]", text) and not re.fullmatch(r"\+?[1-9][0-9]{6,14}", text):
                text = "'" + text
            cells.append(text)
        writer.writerow(cells)
    return "\ufeff" + stream.getvalue()


def csv_reason(reason: str | None, field: str) -> str | None:
    """Readable export copy; stored reasons and count filters keep their codes."""
    if not reason:
        return None
    reasons = {
        "blocked": "The store blocked automated checks.",
        "active_block": "The store requires a human access check; automated checks stopped.",
        "login_required": "The page requires sign-in, so it was not read.",
        "paywall": "The page requires payment, so it was not read.",
        "unavailable": "The website could not be reached.",
        "no_website": "No website found for this business.",
        "no_website_found": "No website found for this business.",
    }
    code = reason.strip().lower()
    if code in reasons:
        return reasons[code]
    if code.startswith("blocked:") or code in {"http_403", "http_429", "http_451"}:
        return reasons["blocked"]
    if code == "not_found":
        detail = {"website": "website", "phone": "phone number", "email": "email address", "socials": "social links"}[field]
        return f"No {detail} found for this business."
    if re.fullmatch(r"[\w.:-]+", reason.strip()):
        return "This detail could not be verified."
    return reason


def export_records(rows: list[dict[str, Any]]) -> str:
    columns = ["record_id", "licence_key", "state", "licence_type", "name"]
    columns += [f"{field}_{part}" for field in FIELDS for part in ("value", "source_url", "checked_at", "reason", "items")]
    exported = []
    for row in rows:
        fields = obj(row["fields"])
        exported.append({**row, **{f"{name}_{part}": csv_reason(fields[name].get(part), name) if part == "reason" else fields[name].get(part) for name in FIELDS
                                  for part in ("value", "source_url", "checked_at", "reason", "items")}})
    return csv_text(exported, columns)


def normal(value: Any, name: str) -> set[str]:
    values = value if isinstance(value, list) else re.split(r"[;,]", str(value or ""))
    result = set()
    for item in values:
        text = str(item).strip().lower()
        if name == "phone":
            text = phone(text)
        elif name == "website" and text:
            try:
                text = (urlsplit(text if "://" in text else "https://" + text).hostname or "").removeprefix("www.")
            except ValueError:
                text = ""
        if text:
            result.add(text)
    return result


def compare(results: list[dict[str, Any]], apollo: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {row["licence_key"]: row for row in latest(results) if row.get("licence_key")}
    groups: dict[str, Any] = {}
    rows = []
    for other in apollo:
        row = obj(other.get("base_snapshot")) or lookup.get(other["licence_key"])
        if row is None:
            continue
        base = obj(row["fields"])
        answer = obj(other["fields"])
        outcomes = {}
        state = groups.setdefault(row["state"], {"state": row["state"], "records": 0,
            **{name: {key: 0 for key in ("matches", "base_only", "apollo_only", "disagreements", "neither")}
               for name in ("website", "phone", "email")}})
        state["records"] += 1
        for name in ("website", "phone", "email"):
            left = normal(base[name]["value"] if base[name]["verified"] else None, name)
            right = normal(answer.get(name), name)
            outcome = "neither" if not left and not right else "base_only" if not right else "apollo_only" if not left else "matches" if left == right else "disagreements"
            state[name][outcome] += 1
            outcomes[name] = outcome
        rows.append({"record_id": str(row["record_id"]), "licence_key": row["licence_key"], "state": row["state"],
                     "base": base, "apollo": answer, "outcomes": outcomes})
    return {"states": [groups[key] for key in sorted(groups)], "rows": rows}
