"""Contact quality: invented offline contacts, unchanged legacy evidence/CSV, no models."""
from __future__ import annotations

import csv
import importlib.util
import io
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from base_evidence import row_fields
from base_metrics import export_records
from base_product_fixtures import AT, finished, raw

from agents.base.engines.ffl import reference

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "base"))
from pipeline import enrich_one, merge

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ("phone_e164", "phone_valid", "phone_line_type", "email_syntax_ok", "email_disposable")


def load(relative):
    spec = importlib.util.spec_from_file_location("quality_" + relative.replace("/", "_"), ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTACTS = load("tank/skills/base.contacts/1.2.0/run.py")


@pytest.fixture(autouse=True, params=["1.2.0", "1.3.0"])
def contacts_version(request, monkeypatch):
    monkeypatch.setitem(globals(), "CONTACTS", load(f"tank/skills/base.contacts/{request.param}/run.py"))
    return request.param


VERIFY = load("tank/skills/base.verify/1.2.0/run.py")


@pytest.mark.parametrize("email,valid", [
    ("a" * 64 + "@quality.example", True), ("a" * 65 + "@quality.example", False),
    ('"invented person"@quality.example', True), ('"invented@person"@quality.example', True),
    ("invented..person@quality.example", False), ("invented@-quality.example", False),
    ("invented@" + "a" * 64 + ".example", False), ("invented@quality..example", False),
    ("invented\n@quality.example", False), ("invented@quality.example\n", False),
    ("invented@[192.0.2.1]", True), ("invented@[IPv6:2001:db8::1]", True),
    ("invented@" + ".".join(["a" * 63] * 4), False),
    ("invented@qualité.example", False),
])
def test_rfc_5321_syntax_and_octet_limits(email, valid):
    assert CONTACTS.email_syntax(email) is valid


def test_phone_types_are_library_metadata_and_country_not_guessed():
    import phonenumbers
    for typ in CONTACTS._LINE_TYPES:
        sample = phonenumbers.example_number_for_type("US", typ)
        if sample is None:
            continue
        text = phonenumbers.format_number(sample, phonenumbers.PhoneNumberFormat.E164)
        quality = CONTACTS.phone_quality({"value": text, "source": "input", "confidence": 90}, "US")
        assert quality["phone_line_type"]["value"] == CONTACTS._LINE_TYPES.get(phonenumbers.number_type(sample), "unknown")
        assert quality["phone_valid"]["value"] is phonenumbers.is_valid_number(sample)
    quality = CONTACTS.phone_quality({"value": "+12025550123"}, "")
    assert quality["phone_country_matches"]["value"] is None
    assert CONTACTS.phone_quality({"value": "garbage"}, "US")["phone_e164"]["value"] is None


@pytest.mark.asyncio
async def test_each_email_gets_own_mx_and_disposable_status_without_smtp(contacts_version):
    requests = []

    async def get(url, **kwargs):
        assert url == "https://cloudflare-dns.com/dns-query"
        assert kwargs["params"]["type"] == "MX"
        domain = kwargs["params"]["name"]
        requests.append(domain)
        return SimpleNamespace(status_code=200, json=lambda: {"Answer": [{"type": 15}]} if domain != "no-mail.example" else {})

    ctx = SimpleNamespace(http=SimpleNamespace(get=get))
    output = await CONTACTS.run({"website": "https://quality.example", "emails": [
        "info@quality.example", "invented@no-mail.example", "invented@mailinator.com", "bad-address",
    ]}, ctx)
    quality = {item["email"]: item for item in output["email_quality"]}
    assert len(quality) == 4  # off-domain addresses and invalid syntax are not dropped
    assert quality["info@quality.example"]["email_kind"]["value"] == "role"
    assert quality["invented@no-mail.example"]["email_mx_ok"]["value"] is (False if contacts_version == "1.2.0" else None)
    assert quality["invented@mailinator.com"]["email_disposable"]["value"] is True
    assert quality["bad-address"]["email_syntax_ok"]["value"] is False
    assert quality["bad-address"]["email_mx_ok"]["value"] is None
    assert sorted(requests) == (["mailinator.com", "no-mail.example", "quality.example"]
                                if contacts_version == "1.2.0" else ["mailinator.com"])
    assert CONTACTS.disposable("sub.mailinator.com")
    assert not CONTACTS.disposable("mailinator.com.quality.example")


@pytest.mark.asyncio
async def test_pipeline_passes_site_and_raw_phones_country_and_provenance():
    seen = {}
    page = {"source_url": "https://quality.example/contact", "checked_at": AT,
            "phones": ["+12025550123"], "emails": ["info@quality.example"]}

    async def call(skill, payload):
        seen[skill] = payload
        if skill == "base.normalize":
            return {"fields": {"phone": {"value": "+12025550124", "source": "input", "confidence": 90}}}
        if skill == "base.find_site":
            return {"website": {"value": "https://quality.example", "confidence": 90}}
        if skill == "base.scrape_site":
            return {"phones": page["phones"], "emails": page["emails"], "_base_observations": [page]}
        if skill == "base.contacts":
            return await CONTACTS.run(payload, None)
        if skill == "base.verify":
            return await VERIFY.run(payload, None)
        return {}

    output = await enrich_one({"phone": "2025550124", "country": "US"}, None, [], None, call)
    assert output.status == "done", output.error
    payload = seen["base.contacts"]
    assert payload["country"] == "US"
    assert {item["value"] for item in payload["phones"]} == {"+12025550123", "+12025550124", "2025550124"}
    site = next(item for item in output.profile["phone_quality"]["value"] if item["phone"] == "+12025550123")
    assert site["phone_valid"]["source_url"] == page["source_url"]
    assert site["phone_valid"]["checked_at"] == AT
    assert output.profile["phone_e164"]["value"] == "+12025550124"  # normal merge still selects input at 90
    assert seen["base.verify"]["profile"]["phone_valid"]["value"] is True
    profile = {"phone_valid": {"value": False, "source": "trusted", "confidence": 99}}
    merge(profile, {"phone_valid": {"value": True, "source": "other", "confidence": 50}})
    assert profile["phone_valid"]["value"] is False


async def quality_row():
    row = finished(reference.project(raw()))
    page = row["passes"]["2b"]["field_observations"][1]
    payload = {"phones": [{"value": row["profile"]["phone"]["value"], "source": "site", "confidence": 80,
                           "source_url": page["source_url"], "checked_at": AT}],
               "emails": row["profile"]["emails"]["value"], "country": "US",
               "email_evidence": [{"value": row["profile"]["emails"]["value"][0], "source": "site", "confidence": 80,
                                   "source_url": page["source_url"], "checked_at": AT}]}
    output = await CONTACTS.run(payload, None)
    row["profile"].update(output["fields"])
    return row


@pytest.mark.asyncio
async def test_quality_evidence_never_changes_legacy_values_and_csv_bytes():
    row = await quality_row()
    baseline_row = deepcopy(row)
    for key in ("phone_quality", "email_quality", *QUALITY):
        baseline_row["profile"].pop(key, None)
    before = row_fields(baseline_row)
    after = row_fields(row)
    assert {key: value for key, value in after.items() if key not in QUALITY} == before
    assert set(after) - set(before) == set(QUALITY)
    for name in QUALITY:
        assert after[name]["source_url"].endswith("/contact")
        assert after[name]["checked_at"] == AT
        assert after[name]["confidence"] == 80
    old_csv = legacy_export_records([{**row, "fields": before}])
    new_csv = export_records([{**row, "fields": after}])
    parsed = list(csv.reader(io.StringIO(new_csv.removeprefix("\ufeff"))))
    old_columns = len(next(csv.reader(io.StringIO(old_csv.removeprefix("\ufeff")))) )
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows([line[:old_columns] for line in parsed])
    assert ("\ufeff" + stream.getvalue()).encode() == old_csv.encode()
    cells = dict(zip(*parsed))
    assert cells["phone_e164"] == "+12125550101"
    assert cells["phone_valid"] == "True"
    assert cells["email_syntax_ok"] == "True"
    assert cells["email_disposable"] == "False"
    assert cells["phone_valid_source_url"] == after["phone_valid"]["source_url"]
    assert cells["phone_valid_confidence"] == "80"


@pytest.mark.asyncio
async def test_quality_does_not_borrow_another_contacts_provenance():
    row = await quality_row()
    row["profile"]["phone_quality"]["value"][0]["phone_e164"]["source_url"] = "https://other.example/"
    assert "phone_valid" not in row_fields(row)
    row = await quality_row()
    row["passes"]["2b"]["access_error"] = {"status": "blocked", "url": "https://blocked.example"}
    assert all(name not in row_fields(row) for name in QUALITY)
    row = await quality_row()
    row["passes"]["2b"]["archive_date"] = "2000-01-01"
    assert all(name not in row_fields(row) for name in QUALITY)



@pytest.mark.asyncio
async def test_product_records_csv_and_apollo_snapshot_retain_quality(monkeypatch):
    import httpx
    from base_product_fixtures import TENANT, fixture_app
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    app, store = fixture_app()
    row = await quality_row()
    row["fields"] = row_fields(row)
    store.rows[TENANT].append(row)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture",
                                 headers={"X-Tank-Key": "local-fixture"}) as client:
        params = {"tenant_id": str(TENANT)}
        response = await client.get("/v1/base-product/records", params=params)
        assert response.status_code == 200
        assert response.json()["rows"][0]["fields"]["phone_valid"]["value"] is True
        response = await client.get("/v1/base-product/records.csv", params=params)
        assert response.status_code == 200
        exported = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
        assert exported[0]["phone_line_type"] == "fixed-or-mobile"
        assert exported[0]["email_syntax_ok"] == "True"
        response = await client.post("/v1/base-product/comparison", json={**params,
            "csv": "licence_key,phone,email\n5-74-00001,2125550199,other@quality.example\n"})
        assert response.status_code == 200
        response = await client.get("/v1/base-product/comparison", params=params)
        compared = response.json()["rows"][0]
        assert compared["outcomes"]["phone"] == "disagreements"
        assert compared["base"]["phone_valid"]["value"] is True
        assert compared["base"]["email_disposable"]["value"] is False


def test_page_rendering_is_byte_identical_with_and_without_quality():
    result = subprocess.run(["node", "tests/base_contact_quality_pages.cjs"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


# Frozen pre-B1 export function from main 23cb9f31: byte-for-byte regression oracle.
from typing import Any

from base_metrics import (
    SOCIAL_NAMES,
    SOCIAL_NETWORKS,
    csv_reason,
    csv_text,
    obj,
    social_network,
    verified_contacts,
)


def legacy_export_records(rows: list[dict[str, Any]]) -> str:
    identity = ["record_id", "licence_key", "state", "licence_type", "name"]
    contacts = ["email", "other_emails", "phone", "other_phones", "website", "other_websites"]
    contacts += [name for network in SOCIAL_NETWORKS for name in (network, f"other_{network}")]
    columns = identity + contacts
    columns += [f"{name}_{part}" for name in contacts for part in ("source_url", "checked_at", "reason")]
    exported = []
    for row in rows:
        fields = obj(row["fields"])
        record = {name: row.get(name) for name in identity}

        def write(name: str, values: list[dict[str, str]], reason: str | None = None,
                  missing: dict[str, Any] | None = None) -> None:
            record[name] = "; ".join(item["value"] for item in values)  # noqa: B023 - frozen legacy oracle
            for part in ("source_url", "checked_at"):
                record[f"{name}_{part}"] = "; ".join(item[part] for item in values) if values else (missing or {}).get(part)  # noqa: B023
            record[f"{name}_reason"] = reason if not values else None  # noqa: B023

        emails = verified_contacts(fields["email"])
        write("email", emails[:1], csv_reason(fields["email"].get("reason"), "email"),
              fields["email"] if not fields["email"].get("verified") else None)
        write("other_emails", emails[1:])
        for name in ("phone", "website"):
            values = verified_contacts(fields[name])
            write(name, values[:1], csv_reason(fields[name].get("reason"), name),
                  fields[name] if not fields[name].get("verified") else None)
            write(f"other_{name}s", values[1:])
        socials = verified_contacts(fields["socials"])
        for network in SOCIAL_NETWORKS:
            values = [item for item in socials if social_network(item["value"]) == network]
            reason = csv_reason(fields["socials"].get("reason"), "socials") or f"No verified {SOCIAL_NAMES[network]} link found for this business."
            write(network, values[:1], reason, fields["socials"] if not fields["socials"].get("verified") else None)
            write(f"other_{network}", values[1:])
        exported.append(record)
    return csv_text(exported, columns)



@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["placeholder.example", "placeholder.invalid", "placeholder.localhost",
                                    "placeholder.test", "TEST", "Sub.Placeholder.Example."])
async def test_reserved_mx_never_requests_and_discovery_agrees(domain):
    contacts = load("tank/skills/base.contacts/1.3.0/run.py")
    requests = []

    async def get(url, **kwargs):
        requests.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"Answer": [{"type": 15}]})

    ctx = SimpleNamespace(http=SimpleNamespace(get=get))
    assert await contacts.mx_ok(ctx, domain) is None
    result = await contacts.run({"website": "https://" + domain,
                                 "emails": ["info@" + domain.lower().rstrip(".")]}, ctx)
    assert result["email_quality"][0]["email_mx_ok"]["value"] is None
    discovered = await contacts._discover({"website": "https://" + domain}, ctx)
    assert discovered["domain_accepts_mail"] is None
    assert requests == []
    result = await contacts.run({"emails": ["info@placeholder.test"]}, None)
    assert result["email_quality"][0]["email_mx_ok"]["value"] is None


@pytest.mark.asyncio
async def test_normal_domain_still_makes_exactly_one_mx_request():
    contacts = load("tank/skills/base.contacts/1.3.0/run.py")
    requests = []

    async def get(url, **kwargs):
        requests.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"Answer": [{"type": 15}]})

    assert await contacts.mx_ok(SimpleNamespace(http=SimpleNamespace(get=get)), "placeholder.org") is True
    assert len(requests) == 1
    assert requests[0] == ("https://cloudflare-dns.com/dns-query", {
        "params": {"name": "placeholder.org", "type": "MX"},
        "headers": {"accept": "application/dns-json"}, "timeout": 6})


@pytest.mark.asyncio
@pytest.mark.parametrize("skill,version,total", [("base.contacts", "1.3.0", 20),
                                                 ("base.site_signals", "1.0.1", 8)])
async def test_b6_offline_evals_are_eligible(skill, version, total):
    import httpx
    import skala

    packages = skala.load_packages()
    pkg = packages[(skill, version)]
    requested = []

    def no_network(request):
        requested.append(request)
        raise AssertionError("Offline eval: no network")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as http:
        result = await skala.run_evals(pkg, lambda: SimpleNamespace(http=http, cost_usd=0, calls=0))
    assert result["passed"] == result["total"] == total, [
        (d["name"], d["why"]) for d in result["details"] if not d["passed"]]
    assert result["eligible"] is True
    assert result["cost_usd"] == 0
    assert not any(r.url.params.get("name", "").endswith(".test") for r in requested)
    if skill == "base.contacts":
        baseline = (ROOT / "tank/skills/base.contacts/1.2.0/evals/cases.jsonl").read_bytes()
        assert (pkg.path / "evals/cases.jsonl").read_bytes().startswith(baseline)
    else:
        from skala_patch import changed_code
        assert changed_code(pkg.path.parent / "1.0.0", pkg.path) == set()
        previous = packages[(skill, "1.0.0")].cases
        for old, new in zip(previous, pkg.cases, strict=True):
            assert new == (dict(old, must_refuse=True) if old["name"] in {"future", "archived"} else old)


@pytest.mark.asyncio
async def test_mx_guards_missing_domain_and_context_before_normalizing():
    contacts = load("tank/skills/base.contacts/1.3.0/run.py")

    async def forbidden(*args, **kwargs):
        pytest.fail("No request for missing domain or context")

    ctx = SimpleNamespace(http=SimpleNamespace(get=forbidden))
    assert await contacts.mx_ok(ctx, None) is None
    assert await contacts.mx_ok(ctx, "") is None
    assert await contacts.mx_ok(None, None) is None
    assert await contacts.mx_ok(None, "placeholder.org") is None
