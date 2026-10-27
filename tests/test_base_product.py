from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

import httpx
import pytest

from base_product_fixtures import AT, TENANT, OTHER, atf_bytes, raw, finished, fixture_app
from base_evidence import observations, observe, row_fields
from base_metrics import compare, cost_rows, export_records
from agents.base.engines.ffl import reference


def test_atf_fixture_refresh_keeps_collectors_and_tracks_identity_across_move():
    before = reference.parse_file(atf_bytes())
    moved = raw(street="20 New Fixture Road")
    moved["LIC_XPRDTE"] = "8A"
    moved["LIC_CNTY"] = "002"
    after = reference.parse_file(atf_bytes([moved, raw(3, "CA", "07"), raw(4, kind="03"), raw(5)]))
    delta = {r["licence_key"]: r["change"] for r in reference.changes(before, after)}
    assert delta == {"5-74-00001": "moved", "5-74-00002": "lapsed", "5-74-00003": "continuing",
                     "5-74-00004": "continuing", "5-74-00005": "new"}
    assert any(row["licence_type"] == "03" for row in after)
    with pytest.raises(ValueError, match="duplicate"):
        reference.parse_file(atf_bytes([raw(), raw()]))


@pytest.mark.asyncio
async def test_reference_reads_only_new_month_never_reloads_september(monkeypatch):
    read = []
    async def get(http, url):
        read.append(url)
        if url == reference.LISTING:
            return b'<a href="/0926-ffl-list-complete.txt">September</a><a href="/1026-ffl-list-complete.txt">October</a>', url
        return atf_bytes(), url
    monkeypatch.setattr(reference, "read_public", get)
    new = await reference.refresh(None, date(2026, 9, 1), date(2026, 10, 26))
    assert new["published_on"] == "2026-10-01"
    assert len(new["rows"]) == 4
    assert all("0926" not in url for url in read)
    read.clear()
    assert (await reference.refresh(None, date(2026, 10, 1), date(2026, 10, 26)))["changed"] is False
    assert read == [reference.LISTING]


def test_each_field_uses_the_page_where_it_was_observed():
    row = finished(reference.project(raw()))
    fields = row_fields(row)
    assert fields["website"]["source_url"].endswith("/")
    for name in ("phone", "email", "socials"):
        assert fields[name]["source_url"].endswith("/contact")
        assert fields[name]["checked_at"] == AT
    row["passes"]["2b"]["access_error"] = {"status": "blocked", "url": "https://public.example/contact"}
    assert all(value["reason"] == "blocked" for value in row_fields(row).values())
    assert "phone_source_url" in export_records([row])


def test_archived_contacts_do_not_become_current_verified_fields():
    row = finished(reference.project(raw()))
    row["passes"]["2b"]["archive_date"] = "2020-01-01"
    assert all(not value["verified"] and "archived" in value["reason"] for value in row_fields(row).values())


def test_known_mail_rejection_and_social_block_are_recorded_as_failures():
    row = finished(reference.project(raw()))
    row["profile"]["contacts"] = {"value": {"domain_accepts_mail": False}}
    row["passes"]["4"] = {"access_error": {"status": "blocked", "url": "https://facebook.com/fixture-business"}}
    fields = row_fields(row)
    assert fields["email"]["verified"] is False and "does not accept" in fields["email"]["reason"]
    assert fields["socials"]["reason"] == "blocked" and fields["socials"]["source_url"] == "https://facebook.com/fixture-business"
    assert fields["website"]["verified"] and fields["phone"]["verified"]


@pytest.mark.asyncio
async def test_atf_public_block_stops_future_requests_without_robots(monkeypatch):
    monkeypatch.setattr(reference, "_blocked", False)
    monkeypatch.setattr(reference, "_last_read", 0)
    seen = []
    def blocked(request):
        seen.append(request)
        assert request.headers["user-agent"] == reference.USER_AGENT
        return httpx.Response(403)
    async with httpx.AsyncClient(transport=httpx.MockTransport(blocked)) as client:
        with pytest.raises(ValueError, match="blocked"):
            await reference.read_public(client, reference.LISTING)
        with pytest.raises(ValueError, match="blocked"):
            await reference.read_public(client, "https://www.atf.gov/another-page")
    assert [str(request.url) for request in seen] == [reference.LISTING]


def test_html_observation_preserves_sources_and_no_url_query():
    token = observations.set([])
    try:
        observe("https://public.example/contact?tracking=value", '<p>212-555-0101</p><a href="mailto:hello@public.example">Email</a>')
        entry = observations.get()[0]
        assert entry["source_url"] == "https://public.example/contact"
        assert entry["emails"] == ["hello@public.example"]
        assert entry["phones"] == ["2125550101"]
        assert entry["checked_at"]
    finally:
        observations.reset(token)


@pytest.mark.asyncio
async def test_texas_type01_without_upload_numbers_download_and_tenant_isolation(monkeypatch):
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    app, store = fixture_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
        response = await client.post("/v1/base-product/reference/batches", json={"tenant_id": str(TENANT), "request_id": str(uuid.uuid4()),
            "created_by": "fixture", "states": ["TX"], "types": ["01"]})
        assert response.status_code == 200, response.text
        assert response.json()["records"] == 2
        values = (await client.get("/v1/base-product/numbers", params={"tenant_id": str(TENANT)})).json()
        texas = next(row for row in values["groups"] if row["state"] == "TX")
        assert texas["licensees"] == texas["attempted"] == texas["website"] == texas["phone"] == texas["email"] == 2
        assert texas["email_and_phone"] == 2 and texas["neither"] == 0
        csv = await client.get("/v1/base-product/records.csv", params={"tenant_id": str(TENANT), "metric": "email_and_phone"})
        assert csv.status_code == 200 and "contact" in csv.text and AT in csv.text
        other = (await client.get("/v1/base-product/numbers", params={"tenant_id": str(OTHER)})).json()
        assert sum(group["attempted"] for group in other["groups"]) == 0
        assert other["states"] == [] and other["costs"] == []
        public = (await client.get("/v1/base-product/reference", params={"tenant_id": str(OTHER)})).json()
        assert public["total_all"] == 4 and public["selected"] == 3 and public["collectors"] == 1
        assert (await client.put("/v1/base-product/reference", json={})).status_code == 405
        assert (await client.post("/v1/base-product/comparison", json={"tenant_id": str(OTHER), "csv": "licence_key,email\n5-74-00001,other@example.com\n"})).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("reason,sentence", [
    ("blocked", "The store blocked automated checks."),
    ("no_website", "No website found for this business."),
    ("not_found", "No website found for this business."),
    ("http_403", "The store blocked automated checks."),
    ("unknown_check_code", "This detail could not be verified."),
    ("Only an archived page was available.", "Only an archived page was available."),
])
async def test_csv_reason_is_a_sentence_and_dates_remain_iso(monkeypatch, reason, sentence):
    import csv
    import io
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    app, store = fixture_app()
    row = finished(reference.project(raw()))
    row["fields"]["website"].update(value=None, verified=False, reason=reason)
    row["fields"]["phone"]["value"] = "+15125550101"
    store.rows[TENANT].append(row)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
        response = await client.get("/v1/base-product/records.csv", params={"tenant_id": str(TENANT), "metric": "failed", "reason": reason})
    assert response.status_code == 200
    records = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert len(records) == 1
    assert records[0]["website_reason"] == sentence
    assert records[0]["website_source_url"] == row["fields"]["website"]["source_url"]
    assert records[0]["website_checked_at"] == records[0]["phone_checked_at"] == AT
    assert records[0]["phone"] == "+15125550101"
    assert row["fields"]["website"]["reason"] == reason


@pytest.mark.asyncio
@pytest.mark.parametrize("email_count", [2, 3])
async def test_download_has_plain_contacts_and_each_values_own_evidence(monkeypatch, email_count):
    import csv
    import io
    from base_evidence import field
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    app, store = fixture_app()
    row = finished(reference.project(raw()))
    row["name"] = "=1+1"
    row["fields"]["phone"]["value"] = "+15125550101"
    emails = [field(address, f"https://shop.example/{i}", f"2026-10-{25+i}T10:00:00+00:00")
              for i, address in enumerate(["info@shop.example", "sales@shop.example", "support@shop.example"][:email_count])]
    row["fields"]["email"] = {**field([item["value"] for item in emails], "https://shop.example/", AT),
                               "items": [field("unverified@shop.example"), *emails, emails[0]]}
    links = {"facebook": "https://www.facebook.com/shop", "instagram": "https://instagram.com/shop",
             "x": "https://twitter.com/shop", "linkedin": "https://www.linkedin.com/company/shop",
             "youtube": "https://youtu.be/fixture"}
    socials = [field(url, f"https://shop.example/{network}", f"2026-10-{20+i}T11:00:00+00:00")
               for i, (network, url) in enumerate(links.items())]
    row["fields"]["socials"] = {**field(list(links.values()), "https://shop.example/", AT), "items": socials}
    store.rows[TENANT].extend([row, finished(reference.project(raw(2)))])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
        response = await client.get("/v1/base-product/records.csv", params={"tenant_id": str(TENANT), "metric": "email_and_phone"})
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    # Inspect the actual downloaded text, then the cells an importer receives.
    assert not any(mark in response.text for mark in ('[', ']', '{', '}'))
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    result = next(item for item in rows if item["record_id"] == str(row["record_id"]))
    assert result["email"] == "info@shop.example"
    assert result["other_emails"] == "; ".join(item["value"] for item in emails[1:])
    assert result["email_source_url"] == emails[0]["source_url"]
    assert result["email_checked_at"] == emails[0]["checked_at"]
    for part in ("source_url", "checked_at"):
        assert result[f"other_emails_{part}"] == "; ".join(item[part] for item in emails[1:])
    for (network, url), evidence in zip(links.items(), socials):
        assert result[network] == url
        assert result[f"{network}_source_url"] == evidence["source_url"]
        assert result[f"{network}_checked_at"] == evidence["checked_at"]
    assert result["website"] == row["fields"]["website"]["value"]
    assert result["phone"] == "+15125550101" and result["phone_checked_at"] == AT
    assert result["name"] == "'=1+1"
    assert not any(key.endswith(("_items", "_value")) or key.startswith("socials") for key in result)
    for item in rows:
        assert all(not any(mark in item[key] for mark in ('[', ']', '"')) for key in ("email", "other_emails", *links))
    single = next(item for item in rows if item["record_id"] != str(row["record_id"]))
    assert single["other_emails"] == single["other_emails_source_url"] == ""
    for network in ("instagram", "x", "linkedin", "youtube"):
        assert single[network] == single[f"{network}_source_url"] == single[f"{network}_checked_at"] == ""


def test_social_export_does_not_mislabel_lookalike_hosts():
    from base_evidence import field
    from base_metrics import social_network
    assert social_network("https://facebook.com.evil.example/shop") is None
    assert social_network("https://m.facebook.com/shop") == "facebook"
    row = finished(reference.project(raw()))
    row["fields"]["email"] = field(reason="blocked", source="https://shop.example/")
    text = export_records([row])
    assert "The store blocked automated checks." in text and "[" not in text


def test_unpriced_cost_is_excluded_and_comparison_uses_same_record():
    row = finished(reference.project(raw()))
    ledger = [{"id": uuid.uuid4(), "record_id": row["id"], "ts": AT, "rung": 1, "cost_usd": Decimal("99"), "cost_status": "not_set"},
              {"id": uuid.uuid4(), "record_id": row["id"], "ts": AT, "rung": 1, "cost_usd": Decimal("0.000792"), "cost_status": "set"}]
    amount = cost_rows([row], ledger)[0]
    assert amount["known_cost_usd"] == "0.000792"
    assert amount["cost_usd"] is None and Decimal(amount["cost_per_verified_record"]) == Decimal("0.000792")
    assert amount["status"] == "price not set"
    comparison = compare([row], [{"licence_key": row["licence_key"], "fields": {"website": row["profile"]["website"]["value"], "phone": "2125550199"}}])
    assert comparison["states"][0]["website"]["matches"] == 1
    assert comparison["states"][0]["phone"]["disagreements"] == 1
    assert comparison["states"][0]["email"]["base_only"] == 1


@pytest.mark.asyncio
async def test_apollo_import_retains_the_base_snapshot(monkeypatch):
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    app, store = fixture_app()
    row = finished(reference.project(raw()))
    store.rows[TENANT].append(row)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
        imported = await client.post("/v1/base-product/comparison", json={"tenant_id": str(TENANT), "csv": "licence_key,phone\n5-74-00001,2125550101\n"})
        assert imported.status_code == 200, imported.text
        row["fields"]["phone"]["value"] = "2125550199"
        compared = (await client.get("/v1/base-product/comparison", params={"tenant_id": str(TENANT)})).json()
        assert compared["states"][0]["phone"]["matches"] == 1
        assert compared["rows"][0]["base"]["phone"]["value"] == "212-555-0101"


def test_csv_spreadsheet_import_keeps_phones_and_neutralises_formulas():
    import csv
    import io
    from base_metrics import csv_text
    phones = ["+15125550101", "+442079460018", "15125550101"]
    formulas = ['=HYPERLINK("https://evil.example/","click")', "+SUM(1,2)", "-1+2", "@SUM(1,2)", "  =1+1"]
    output = csv_text([{"phone": phone} for phone in phones + formulas], ["phone"])
    values = [row["phone"] for row in csv.DictReader(io.StringIO(output.lstrip("\ufeff")))]
    # These are the actual cell contents a CSV importer receives: no apostrophe
    # added to phone values; dangerous expressions import as literal text.
    assert values[:len(phones)] == phones
    assert values[len(phones):] == ["'" + formula for formula in formulas]


def test_partial_cost_metrics_keep_priced_margin_and_cost_per_outcome():
    from admin import pack_metrics
    value = pack_metrics(3, 0, 0, 0.000792, 2, 1, unpriced=1)
    assert value["spend_usd"] == 0.000792
    assert value["cost_per_outcome"] == 0.000396
    assert value["margin_pct"] == pytest.approx(99.92)
    assert value["unpriced_calls"] == 1


@pytest.mark.parametrize("status", ["set", "price not set"])
def test_price_status_receipt_remains_searchable_in_founder_pdf(status):
    from io import BytesIO
    from pypdf import PdfReader
    from proof import pdf_export
    receipt = "ff9ef974-6eca-43ea-bb93-da93b3d3c30f"
    data = {"tenant_id": str(TENANT), "region": "us-east",
            **{section: [] for section in ("tasks", "ledger", "shadows", "runs", "cases", "promotions", "policies", "state")}}
    data["ledger"] = [{"baseline_status": "backfilled", "cost_status": status, "cost_usd": None, "id": receipt}]
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(pdf_export(data))).pages)
    assert status in text and receipt in text


@pytest.mark.asyncio
async def test_uploaded_records_without_licence_type_can_download_their_count(monkeypatch):
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    app, store = fixture_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
        uploaded = await client.post("/v1/base-product/uploads", json={"tenant_id": str(TENANT), "request_id": str(uuid.uuid4()),
            "created_by": "fixture", "records": [{"name": "Uploaded business", "state": "CA"}]})
        assert uploaded.status_code == 200, uploaded.text
        params = {"tenant_id": str(TENANT), "states": "CA", "types": "unspecified", "metric": "attempted"}
        downloaded = await client.get("/v1/base-product/records.csv", params=params)
        assert downloaded.status_code == 200 and "Uploaded business" in downloaded.text
        other = await client.get("/v1/base-product/records.csv", params={**params, "tenant_id": str(OTHER)})
        assert other.status_code == 200 and "Uploaded business" not in other.text


@pytest.mark.asyncio
async def test_base_collector_stops_before_tank_closes_shared_resources():
    import asyncio
    from types import SimpleNamespace
    from fastapi import FastAPI
    from base_product import build_router
    entered, active = asyncio.Event(), set()
    class Collecting:
        async def adopt(self):
            task = asyncio.current_task()
            active.add(task)
            entered.set()
            try:
                await asyncio.Future()
            finally:
                active.remove(task)
    app = FastAPI()
    # Tank registers its shared-pool shutdown callback before the Base router.
    async def close_shared_pool():
        assert not active, "Base must return every connection before Tank closes the pool"
    app.add_event_handler("shutdown", close_shared_pool)
    app.include_router(build_router(SimpleNamespace(box_region=lambda: "us-east"), Collecting()))
    try:
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(entered.wait(), timeout=1)
            await asyncio.sleep(0)
            assert len(active) == 1, "Only one reference/result collector may run"
        assert not active
    finally:
        # Clean up a leaked task even when this regression is run against old code.
        remaining = list(active)
        for task in remaining:
            task.cancel()
        await asyncio.gather(*remaining, return_exceptions=True)
