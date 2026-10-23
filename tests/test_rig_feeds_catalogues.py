"""Expanded RIG-3: real parsers, per-feed provenance and private repricing."""

import base64
import io
import json
import secrets
import zipfile
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from test_rig_feeds_retailer import ROOT, SAMPLES, SITE, TENANT, OTHER, prepared
import access
from command import Actor
from rigbox.feeds import pull
from rigbox.feeds.catalogue import suggest_mapping
from rigbox.retailer import Retailer
from rigbox.service import Service
from rigbox.store import MemoryStore, PgStore
from test_rig_feeds_mapping import mapping_pool, confirm_feed  # noqa: F401

CASES = [
    ("us-distributor.csv", "USD", "US", "cost", "US-LAMP", "534.19", ""),
    ("eu-distributor.xml", "EUR", "DE", "cost", "EU-STAND", "440.00", ""),
    ("nz-distributor.json", "NZD", "NZ", "cost", "NZ-SHADE", "196.63", "catalogue.products"),
    ("distributor.xlsx", "USD", "US", "cost", "XLSX-CHAIR", "788.56", ""),
    ("store-catalogue.csv", "ZAR", "ZA", "selling", "STORE-DESK", "799.95", ""),
]


def sample(case):
    filename, code, country, basis, *_ = case
    kind = filename.rsplit(".", 1)[-1]
    raw = (SAMPLES / filename).read_bytes()
    data = {"provider": "catalogue", "site": SITE, "feed_id": filename.replace(".", "-"), "format": kind,
            "currency": code, "country": country, "price_basis": basis, "records_path": case[-1],
            "encoding": "base64" if kind == "xlsx" else "text",
            "contents": base64.b64encode(raw).decode() if kind == "xlsx" else raw.decode()}
    data["columns"] = suggest_mapping(data, data["contents"])["columns"]
    return data


async def rates(retailer):
    await retailer.set_rate(TENANT, {"currency": "EUR", "rate": "20"}, founder=True)
    await retailer.set_rate(TENANT, {"currency": "NZD", "rate": "11"}, founder=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
async def test_every_required_sample_is_mapped_receipted_and_priced(case):
    retailer = await prepared()
    await rates(retailer)
    data = sample(case)
    preview = suggest_mapping(data, data["contents"])
    assert all(key in preview["columns"] for key in preview["required"])
    assert case[4] not in json.dumps(preview)  # Field names only, never values.
    result = await retailer.import_file(TENANT, data)
    assert result["ok"] is True
    assert result["receipt"]["added"] == 1
    assert result["receipt"]["rejected"] == 0
    product = (await retailer.store.products(TENANT))[0]
    assert product["price"] == Decimal(case[5])
    assert product["currency"] == "ZAR"
    assert (await retailer.import_file(TENANT, data))["receipt"]["updated"] == 1
    assert not await retailer.store.products(OTHER)


@pytest.mark.asyncio
@pytest.mark.parametrize("amount,expected", [("19.9949999999999999999999", "19.99"), ("19.9950000000000000000001", "20.00"), ("999999999.99", "999999999.99")])
async def test_xlsx_numeric_prices_do_not_pass_through_float(amount, expected):
    from rigbox.feeds.catalogue import xlsx_rows
    buffer = io.BytesIO()
    with zipfile.ZipFile(SAMPLES / "distributor.xlsx") as original, zipfile.ZipFile(buffer, "w") as archive:
        for name in original.namelist():
            contents = original.read(name)
            if name.endswith("sheet1.xml"):
                import re
                contents, replaced = re.subn(rb'<c r="E2"[^>]*>.*?</c>', f'<c r="E2"><v>{amount}</v></c>'.encode(), contents)
                assert replaced == 1
            archive.writestr(name, contents)
    raw = buffer.getvalue()
    assert xlsx_rows(raw)[0]["cost"] == amount
    data = sample(CASES[3])
    data.update(contents=base64.b64encode(raw).decode(), currency="ZAR", price_basis="selling")
    retailer = await prepared()
    assert (await retailer.import_file(TENANT, data))["ok"]
    assert (await retailer.store.products(TENANT))[0]["price"] == Decimal(expected)
    assert Decimal((await retailer.store.costs(TENANT))[0]["cost"]) == Decimal(expected)


@pytest.mark.asyncio
async def test_regional_and_supplier_overrides_and_selling_price_survive_repricing():
    retailer = await prepared()
    await rates(retailer)
    for case in CASES:
        assert (await retailer.import_file(TENANT, sample(case)))["ok"]
    await retailer.set_rule(TENANT, {"scope": "region", "scope_id": "EU", "freight": "2", "duty_percent": "5", "margin_percent": "0"})
    assert (await retailer.service.product(TENANT, "EU-STAND"))["price"]["amount"] == 357
    await retailer.set_rule(TENANT, {"scope": "region", "scope_id": "DE", "freight": "4", "duty_percent": "0", "margin_percent": "0"})
    assert (await retailer.service.product(TENANT, "EU-STAND"))["price"]["amount"] == 380
    data = sample(CASES[1])
    await retailer.set_rule(TENANT, {"scope": "supplier", "scope_id": f"catalogue:{SITE}:{data['feed_id']}", "freight": "3", "duty_percent": "0", "margin_percent": "0"})
    assert (await retailer.service.product(TENANT, "EU-STAND"))["price"]["amount"] == 360
    await retailer.set_rule(TENANT, {"freight": "5", "duty_percent": "20", "margin_percent": "50"})
    assert (await retailer.service.product(TENANT, "STORE-DESK"))["price"]["amount"] == 799.95
    assert (await retailer.service.product(TENANT, "EU-STAND"))["price"]["amount"] == 360
    assert (await retailer.service.product(TENANT, "US-LAMP"))["price"]["amount"] == 1110
    for source, rate in [("USD", "1"), ("EUR", "1.1"), ("NZD", ".6"), ("ZAR", ".05")]:
        await retailer.set_rate(TENANT, {"currency": source, "target_currency": "USD", "rate": rate}, founder=True)
    await retailer.set_rule(TENANT, {"shop_currency": "USD", "freight": "0", "duty_percent": "0", "margin_percent": "0"})
    assert (await retailer.service.product(TENANT, "US-LAMP"))["price"] == {"amount": 20.0, "currency": "USD", "indicative": True}
    assert (await retailer.service.product(TENANT, "STORE-DESK"))["price"]["amount"] == 40.0
    for payload in [await retailer.panel(TENANT), await retailer.service.product(TENANT, "US-LAMP")]:
        assert not any(key in json.dumps(payload) for key in ("duty_percent", "margin_percent", "freight", "price_basis", "scopes"))


@pytest.mark.asyncio
async def test_selling_price_needs_no_cost_rule_and_bad_rates_rollback_all_products():
    retailer = Retailer(Service(MemoryStore()))
    assert (await retailer.import_file(TENANT, sample(CASES[-1])))["ok"]
    await retailer.set_rule(TENANT, {"freight": "1"})
    with pytest.raises(ValueError):
        await retailer.set_rule(TENANT, {"shop_currency": "EUR", "freight": "9"})
    assert (await retailer.panel(TENANT))["currency"] == "ZAR"
    assert (await retailer.service.product(TENANT, "STORE-DESK"))["price"]["amount"] == 799.95


@pytest.mark.parametrize("kind,raw", [("xml", '<!DOCTYPE x [<!ENTITY y "boom">]><catalogue/>'), ("xml", '<!ENTITY x "boom"><catalogue/>'), ("xml", '\x00<catalogue/>'), ("csv", "sku,sku\na,b"), ("xlsx", "not-a-workbook")])
def test_unsafe_or_invalid_documents_reject_without_partial_rows(kind, raw):
    result = pull({"format": kind, "currency": "USD"}, raw)
    assert result["rows"] == [] and result["rejected"]


def test_xlsx_zip_bomb_and_formula_are_refused():
    data = sample(CASES[3])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("huge.xml", b"x" * 32_000_001)
    data["contents"] = base64.b64encode(buffer.getvalue()).decode()
    assert pull(data, data["contents"])["rejected"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(SAMPLES / "distributor.xlsx") as original, zipfile.ZipFile(buffer, "w") as archive:
        for name in original.namelist():
            body = original.read(name)
            if name.endswith("sheet1.xml"):
                body = body.replace(b'<is><t>30.00</t></is>', b'<f>1+1</f><v>2</v>')
            archive.writestr(name, body)
    data["contents"] = base64.b64encode(buffer.getvalue()).decode()
    assert pull(data, data["contents"])["rejected"]


def test_feed_bounds_and_explicit_declarations_do_not_expand_tiger_formats():
    data = {"target": "rig", "distributor": "catalogue", "format": "csv", "site": SITE,
            "source": "ftp_export", "contents": "x", "mapping_confirmed": True}
    with pytest.raises(ValidationError):
        access.FeedImport(**data)
    data.pop("mapping_confirmed")
    data.update(currency="ZAR", country="ZA", price_basis="selling")
    assert access.FeedImport(**data).price_basis == "selling"
    with pytest.raises(ValidationError):
        access.FeedImport(**{**data, "contents": "é" * 4_000_001})
    with pytest.raises(ValidationError):
        access.FeedImport(**{**data, "format": "xlsx", "encoding": "base64", "contents": "not base64"})
    for kind in ("xml", "xlsx"):
        with pytest.raises(ValidationError):
            access.FeedImport(**{**data, "target": "tiger", "distributor": "zanders", "format": kind})


@pytest.mark.asyncio
@pytest.mark.usefixtures("mapping_pool")
async def test_mapping_preview_is_read_only_and_refuses_private_fetches(monkeypatch):
    from rigbox.retailer_server import create_retailer_app
    app = FastAPI()
    app.include_router(access.router)
    actor = Actor(UUID(TENANT), "admin", False, frozenset({"rig"}))
    app.dependency_overrides[access.identity] = lambda: actor
    retailer = await prepared()
    control = secrets.token_hex(32)
    monkeypatch.setenv("RIG_RETAILER_KEY", control)
    room = create_retailer_app(retailer.service)
    async def dispatch(who, operation, data=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room), base_url="http://private") as client:
            response = await client.post("/internal/retailer/" + operation, headers={"x-rig-retailer-key": control}, json={"tenant_id": str(who.tenant_id), "data": data})
            response.raise_for_status()
            return response.json()
    monkeypatch.setattr(access, "rig_request", dispatch)
    data = sample(CASES[0])
    data.update(distributor=data.pop("provider"), source="ftp_export")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/access/rig/admin/mapping", json={"data": data})
        assert response.status_code == 200
        assert response.json()["columns"]["price"] == "DealerPrice"
        assert "20.00" not in response.text and "US-LAMP" not in response.text
        assert not await retailer.store.products(TENANT)
        assert not await retailer.store.receipts(TENANT)
        # Use the real pinned public_get with a deterministic private DNS answer.
        import asyncio
        loop = asyncio.get_running_loop()
        async def private_dns(*args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1", 443))]
        remote = {k: v for k, v in data.items() if k not in {"contents", "encoding", "source"}}
        remote.update(endpoint=SITE + "/catalogue.csv", auth_mode="none", official_read_only=True)
        # Undo the DNS patch before fixtures tear down, so dropping the test
        # database still resolves the real Postgres host.
        with monkeypatch.context() as dns:
            dns.setattr(loop, "getaddrinfo", private_dns)
            denied = await client.post("/v1/access/rig/admin/mapping", json={"data": remote})
        assert denied.status_code == 422


@pytest.mark.parametrize("provider", ["shopify", "woocommerce", "google"])
@pytest.mark.asyncio
async def test_existing_importers_accept_confirmed_maps(provider):
    from test_rig_feeds_retailer import envelope
    retailer = await prepared()
    data = envelope(provider)
    data["format"] = "xml" if provider == "google" else "json"
    record = {**data, "format": "xml" if provider == "google" else provider}
    data["columns"] = suggest_mapping(record, data["contents"])["columns"]
    assert (await retailer.import_file(TENANT, data))["ok"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["shopify", "woocommerce"])
async def test_merchant_mapping_preserves_stock_and_original_price_fallback(provider):
    from test_rig_feeds_retailer import envelope
    retailer = await prepared()
    data = envelope(provider)
    raw = json.loads(data["contents"])
    products = raw["products"] if isinstance(raw, dict) else raw
    product = products[0]
    if provider == "shopify":
        product["status"] = "draft"
        product["variants"][0]["inventory_quantity"] = 12
    else:
        product["stock_status"] = "outofstock"
        product["regular_price"] = product["price"]
        product["price"] = ""
    data.update(format="json", contents=json.dumps(raw))
    data["columns"] = suggest_mapping({**data, "format": provider}, data["contents"])["columns"]
    assert (await retailer.import_file(TENANT, data))["ok"]
    assert (await retailer.store.products(TENANT))[0]["active"] is False


@pytest.mark.asyncio
async def test_saved_maps_refresh_metadata_scopes_and_schema_reapply_on_postgres(monkeypatch):
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    name = "rig_formats_" + secrets.token_hex(6)
    admin = _admin_url()
    await _create_database(admin, name)
    pool = await asyncpg.create_pool(_database_url(admin, name))
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / "tank/schema.sql").read_text())
            await conn.execute((ROOT / "tank/schema.sql").read_text())
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()
        retailer = await prepared(store)
        await rates(retailer)
        monkeypatch.setattr(access, "db", lambda: pool)
        monkeypatch.setenv("TANK_VAULT_KEY", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        actor = Actor(UUID(TENANT), "sample-admin", False, frozenset({"rig"}))
        async def dispatch(who, operation, data=None):
            if operation == "panel":
                return await retailer.panel(str(who.tenant_id))
            if operation == "mapping":
                return suggest_mapping(data, data["contents"])
            return await retailer.import_file(str(who.tenant_id), data)
        monkeypatch.setattr(access, "rig_request", dispatch)
        for case in CASES:
            data = sample(case)
            data = await confirm_feed(actor, {**{k: v for k, v in data.items() if k != "provider"}, "distributor": "catalogue", "target": "rig", "source": "ftp_export"})
            body = access.FeedImport(**data)
            assert (await access.import_feed_body(actor, body))["ok"]
            # An upload without a new confirmation reuses exactly the saved mapping and declarations.
            again = body.model_copy(update={"columns": {}})
            assert (await access.import_feed_body(actor, again))["receipt"]["updated"] == 1
            with pytest.raises(HTTPException, match="settings changed"):
                await access.import_feed_body(actor, body.model_copy(update={"currency": "AUD", "country": "AU", "price_basis": "selling"}))
        panel = await access.rig_admin_panel(actor)
        assert len(panel["feeds"]) == 5
        assert {f["currency"] for f in panel["feeds"]} == {"USD", "EUR", "NZD", "ZAR"}
        assert (await access.rig_admin_panel(Actor(UUID(OTHER), "other", False, frozenset({"rig"}))))["feeds"] == []
        # Two feeds at the same website retain different declarations and schedules.
        data = sample(CASES[3])
        connection = access.FeedConnection(**{k: v for k, v in data.items() if k not in {"provider", "contents", "encoding"}}, distributor="catalogue", target="rig",
            endpoint=SITE + "/catalogue.xlsx", auth_mode="none", official_read_only=True)
        async def fetch(url, **kwargs):
            return (SAMPLES / "distributor.xlsx").read_bytes(), {}
        monkeypatch.setattr(access, "public_get", fetch)
        data_connection = connection.model_dump(mode="json", exclude={"token", "username", "password"})
        connection = access.FeedConnection(**await confirm_feed(actor, data_connection))
        await access.connect_feed_body(actor, connection)
        with pytest.raises(HTTPException, match="settings changed"):
            await access.connect_feed_body(actor, connection.model_copy(update={"endpoint": SITE + "/changed.xlsx"}))
        refreshed = await access.refresh_connected_feed(actor, access.FeedRefresh(distributor="catalogue", target="rig", site=SITE, feed_id=data["feed_id"]))
        assert refreshed["receipt"]["updated"] == 1
        restored = Retailer(Service(PgStore(pool)))
        await restored.set_rule(TENANT, {"scope": "region", "scope_id": "EU", "freight": "0", "duty_percent": "0", "margin_percent": "0"})
        assert (await restored.service.product(TENANT, "EU-STAND"))["price"]["amount"] == 300
        assert (await restored.service.product(TENANT, "STORE-DESK"))["price"]["amount"] == 799.95
        old = (await restored.service.product(TENANT, "EU-STAND"))["price"]
        invalid = sample(CASES[1]); invalid["contents"] = invalid["contents"].replace("15.00", "NaN")
        assert not (await restored.import_file(TENANT, invalid))["ok"]
        assert (await restored.service.product(TENANT, "EU-STAND"))["price"] == old
        costs = await restored.store.costs(TENANT)
        assert {row["country"] for row in costs} == {"US", "DE", "NZ", "ZA"}
    finally:
        await pool.close()
        await _drop_database(admin, name)
