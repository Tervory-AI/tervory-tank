"""Offline reference and public-page fixtures; never imported by production."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import uuid

from agents.base.engines.ffl.reference import parse_file
from base_evidence import row_fields

AT = "2026-10-26T10:00:00+00:00"
TENANT = uuid.UUID("ba5e0000-0000-4000-8000-000000000111")
OTHER = uuid.UUID("ba5e0000-0000-4000-8000-000000000222")


def raw(number=1, state="TX", kind="01", street="1 Fixture Road"):
    return dict(LIC_REGN="5", LIC_DIST="74", LIC_CNTY="001", LIC_TYPE=kind, LIC_XPRDTE="7A",
                LIC_SEQN=f"{number:05}", LICENSE_NAME=f"Fixture Business {number}", BUSINESS_NAME="",
                PREMISE_STREET=street, PREMISE_CITY="Fixture City", PREMISE_STATE=state, PREMISE_ZIP_CODE="75001")


def atf_bytes(rows=None):
    import csv
    import io
    rows = rows or [raw(), raw(2), raw(3, "CA", "07"), raw(4, kind="03")]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def finished(entry, tenant=TENANT):
    identity = uuid.uuid4()
    host = f"business-{entry['licence_key']}.example"
    site = f"https://{host}/"
    profile = {"name": {"value": entry["name"]}, "website": {"value": site},
               "phone": {"value": "212-555-0101"}, "emails": {"value": [f"info@{host}"]},
               "socials": {"value": {"facebook": "https://facebook.com/fixture-business"}}}
    passes = {"2b": {"field_observations": [
        {"source_url": site, "checked_at": AT, "emails": [], "phones": [], "links": []},
        {"source_url": site + "contact", "checked_at": AT, "emails": [f"info@{host}"],
         "phones": ["2125550101"], "links": ["https://facebook.com/fixture-business"]},
    ]}, "7": {"checks": {"phone_matches_site": True, "email_domain_matches_site": True}}}
    return {"tenant_id": tenant, "record_id": identity, "id": identity, "task_id": uuid.uuid4(), "batch": "Fixture list",
            "licence_key": entry["licence_key"], "state": entry["state"], "licence_type": entry["licence_type"],
            "name": entry["name"], "status": "done", "raw": {**entry["raw"], "_base_reference": entry},
            "profile": profile, "passes": passes, "fields": row_fields({"profile": profile, "passes": passes, "status": "done"}),
            "attempted_at": AT, "created_at": AT, "checked_at": AT, "updated_at": AT}


def multiple_contacts():
    """Independently verified values with distinct pages and dates for CSV/UI parity."""
    from base_evidence import field
    values = {
        "email": ["info@shop.example", "sales@shop.example"],
        "phone": ["+15125550101", "+15125550102"],
        "website": ["https://shop.example/", "https://shop.example/store"],
        "socials": ["https://facebook.com/shop", "https://facebook.com/shop-store",
                    "https://www.tiktok.com/@shop", "https://instagram.com/shop", "https://instagram.com/shop-store",
                    "https://x.com/shop", "https://twitter.com/shop-store", "https://linkedin.com/company/shop",
                    "https://linkedin.com/company/shop-store", "https://youtube.com/@shop", "https://youtu.be/shop-store",
                    "https://www.tiktok.com/@shop-store"],
    }
    fields = {}
    for name, contacts in values.items():
        items = [field(value, f"https://shop.example/{name}/{i}", f"2026-10-{i+1:02}T10:00:00+00:00")
                 for i, value in enumerate(contacts)]
        fields[name] = {**field(contacts, items[0]["source_url"], items[0]["checked_at"]), "items": items}
    return fields


class FixtureStore:
    def __init__(self):
        self.entries = parse_file(atf_bytes())
        self.file = {"id": uuid.uuid4(), "owner_id": "00000000-0000-0000-0000-000000000001",
                     "published_on": "2026-09-01", "source_url": "https://www.atf.gov/fixture-reference",
                     "checked_at": AT, "row_count": len(self.entries), "sha256": hashlib.sha256(atf_bytes()).hexdigest()}
        self.rows, self.receipts, self.plans, self.comparisons = (defaultdict(list) for _ in range(4))
        self.requests = {}

    async def latest_file(self):
        return deepcopy(self.file)

    async def reference(self, file_id=None, **kwargs):
        return [{**deepcopy(entry), **{k: self.file[k] for k in ("source_url", "checked_at", "published_on")}} for entry in self.entries]

    async def reference_history(self):
        return [await self.latest_file()]

    async def results(self, tenant):
        return deepcopy(self.rows[tenant])

    async def ledger(self, tenant):
        return deepcopy(self.receipts[tenant])

    async def campaigns(self, tenant):
        return deepcopy(self.plans[tenant])

    async def create_campaign(self, tenant, request_id, name, created_by, file_id, selection, groups):
        if (tenant, request_id) in self.requests:
            return self.requests[tenant, request_id]
        identity = uuid.uuid4()
        self.requests[tenant, request_id] = identity
        for state, entries in sorted(groups.items()):
            self.plans[tenant].append({"id": identity, "state": state, "batch": f"{name} · {state}", "name": name,
                                      "records_count": len(entries), "status": "waiting", "entries": entries})
        return identity

    async def dispatch(self, tenant):
        for plan in self.plans[tenant]:
            if plan["status"] != "waiting":
                continue
            for entry in plan["entries"]:
                if "licence_key" not in entry:
                    entry = {"licence_key": None, "name": entry["name"], "state": entry.get("state", "TX"),
                             "licence_type": "unspecified", "raw": entry}
                row = finished(entry, tenant)
                row["batch"] = plan["batch"]
                self.rows[tenant].append(row)
                self.receipts[tenant].append({"id": uuid.uuid4(), "record_id": row["record_id"], "ts": AT,
                    "rung": 3, "cost_usd": 0, "cost_status": "set", "vendor": None, "outcome": "delivered"})
            plan["status"] = "done"

    async def apollo(self, tenant):
        return deepcopy(self.comparisons[tenant])

    async def save_apollo(self, tenant, digest, rows):
        self.comparisons[tenant] = deepcopy(rows)
        return uuid.uuid4()


def fixture_app():
    from fastapi import FastAPI
    from types import SimpleNamespace
    from base_product import build_router
    app = FastAPI()
    store = FixtureStore()
    app.include_router(build_router(SimpleNamespace(box_region=lambda: "us-east"), store, background=False))
    return app, store
