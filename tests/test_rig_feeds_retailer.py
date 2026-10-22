"""RIG-3 imports, review boundaries and private prices, using synthetic goods."""

import json
import secrets
import sys
import base64
import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

import access  # noqa: E402
from command import Actor  # noqa: E402
from rigbox.retailer_server import create_retailer_app  # noqa: E402
from rigbox.retailer import Retailer  # noqa: E402
from rigbox.service import RigError, Service  # noqa: E402
from rigbox.store import MemoryStore, PgStore  # noqa: E402

TENANT = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
SAMPLES = ROOT / "agents" / "rig" / "catalogues" / "samples"
SITE = "https://supplier.example"


def envelope(provider="shopify"):
    suffix = "xml" if provider == "google" else "json"
    return {"provider": provider, "site": SITE, "currency": "USD", "contents": (SAMPLES / f"{provider}.{suffix}").read_text()}


async def prepared(store=None):
    service = Service(store or MemoryStore())
    retailer = Retailer(service)
    await retailer.set_rule(TENANT, {"freight": "1", "duty_percent": "10", "margin_percent": "20"})
    await retailer.set_rate(TENANT, {"currency": "USD", "rate": "18.50"}, founder=True)
    return retailer


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,count", [("shopify", 2), ("woocommerce", 1), ("google", 1)])
async def test_sample_imports_receipts_and_repeatability(provider, count):
    retailer = await prepared()
    result = await retailer.import_file(TENANT, envelope(provider))
    assert result["ok"] is True
    assert {key: result["receipt"][key] for key in ("added", "updated", "rejected")} == {"added": count, "updated": 0, "rejected": 0}
    again = await retailer.import_file(TENANT, envelope(provider))
    assert again["receipt"]["updated"] == count
    assert again["receipt"]["added"] == 0
    assert len(await retailer.store.products(TENANT)) == count
    assert len(await retailer.store.receipts(TENANT)) == 2
    assert await retailer.store.products(OTHER) == []
    assert await retailer.store.receipts(OTHER) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", access.DISTRIBUTORS)
async def test_distributor_uses_access_adapter_and_produces_receipt(provider):
    retailer = await prepared()
    body = access.FeedImport(target="rig", distributor=provider, site=SITE, source="ftp_export", format="csv",
        contents=SecretStr((SAMPLES / "distributor.csv").read_text()), columns={"sku": "ItemNumber", "price": "DealerPrice", "quantity": "Quantity", "upc": "UPC"})
    rows = access.rig_feed_rows(body)
    assert rows[0]["sku"] == "SAMPLE-DESK"
    result = await retailer.import_file(TENANT, {"provider": provider, "site": SITE, "currency": "USD", "rows": rows})
    assert result["ok"] is True
    assert result["receipt"]["added"] == 1
    product = (await retailer.store.products(TENANT))[0]
    assert product["price"] == Decimal("1042.94")
    assert product["currency"] == "ZAR"


@pytest.mark.asyncio
async def test_late_bad_row_rolls_back_every_product_and_keeps_rejection_receipt():
    retailer = await prepared()
    await retailer.import_file(TENANT, envelope())
    before = deepcopy(await retailer.store.products(TENANT))
    data = envelope()
    raw = json.loads(data["contents"])
    raw["products"][0]["variants"][0]["price"] = "999"
    raw["products"][1]["variants"][0]["price"] = "NaN"
    data["contents"] = json.dumps(raw)
    rejected = await retailer.import_file(TENANT, data)
    assert rejected["ok"] is False
    assert rejected["receipt"]["added"] == rejected["receipt"]["updated"] == 0
    assert rejected["receipt"]["rejected"] > 0
    assert await retailer.store.products(TENANT) == before


@pytest.mark.asyncio
async def test_supplier_evidence_is_reviewed_and_refresh_preserves_decisions():
    retailer = await prepared()
    await retailer.import_file(TENANT, envelope())
    service = retailer.service
    pending = await service.suggested_fits(TENANT)
    assert len(pending["fits"]) == 1
    assert "Synthetic supplier" in pending["fits"][0]["note"]
    assert await service._approved_fits(TENANT) == []
    assert await service.approve(OTHER, "SAMPLE-SHADE", "SAMPLE-LAMP", None) is False
    await service.approve(TENANT, "SAMPLE-SHADE", "SAMPLE-LAMP", None)
    assert len(await service._approved_fits(TENANT)) == 1
    await retailer.import_file(TENANT, envelope())
    assert len(await service._approved_fits(TENANT)) == 1
    await service.reject(TENANT, "SAMPLE-SHADE", "SAMPLE-LAMP", None)
    await retailer.import_file(TENANT, envelope())
    assert await service._approved_fits(TENANT) == []
    assert (await service.suggested_fits(TENANT))["fits"] == []


@pytest.mark.asyncio
async def test_private_inputs_never_appear_in_public_or_admin_responses():
    retailer = await prepared()
    await retailer.import_file(TENANT, envelope())
    product = await retailer.service.product(TENANT, "SAMPLE-LAMP")
    assert product["price"] == {"amount": 534.19, "currency": "ZAR", "indicative": True}
    for payload in [product, await retailer.panel(TENANT), await retailer.service.search(TENANT, "Sample Lamp", 12)]:
        encoded = json.dumps(payload, default=str)
        for field in ("supplier_cost", "freight", "duty_percent", "margin_percent", "exchange_rates", "18.50"):
            assert field not in encoded
    assert (await retailer.store.costs(TENANT))[0]["cost"] == "20.00"


@pytest.mark.asyncio
async def test_rule_reprices_and_exchange_rate_requires_founder():
    retailer = await prepared()
    await retailer.import_file(TENANT, envelope())
    await retailer.set_rule(TENANT, {"freight": 0, "duty_percent": 0, "margin_percent": 0})
    assert (await retailer.service.product(TENANT, "SAMPLE-LAMP"))["price"]["amount"] == 370
    with pytest.raises(RigError) as denied:
        await retailer.set_rate(TENANT, {"currency": "USD", "rate": "22"})
    assert denied.value.status == 403
    await retailer.set_rate(TENANT, {"currency": "USD", "rate": "22"}, founder=True)
    assert (await retailer.service.product(TENANT, "SAMPLE-LAMP"))["price"]["amount"] == 440


@pytest.mark.asyncio
async def test_missing_configuration_imports_nothing():
    retailer = Retailer(Service(MemoryStore()))
    result = await retailer.import_file(TENANT, envelope())
    assert result["ok"] is False
    assert await retailer.store.products(TENANT) == []
    await retailer.set_rule(TENANT, {})
    result = await retailer.import_file(TENANT, envelope())
    assert result["ok"] is False
    assert await retailer.store.products(TENANT) == []


@pytest.mark.asyncio
async def test_tiger_only_updates_unfed_products_and_never_fitment():
    retailer = await prepared()
    await retailer.import_file(TENANT, envelope())
    before = deepcopy(await retailer.store.fits(TENANT))
    assert await retailer.service.apply_watch(TENANT, "SAMPLE-LAMP", {"price": "1", "active": False}) is False
    await retailer.store.upsert_product(TENANT, {"sku": "UNFED", "name": "Desk", "brand": "Sample", "category": "furniture", "price": "15", "currency": "ZAR", "active": True})
    assert await retailer.service.apply_watch(TENANT, "UNFED", {"price": "16", "active": False, "fits_sku": "SAMPLE-LAMP", "approved": True}) is True
    assert await retailer.store.fits(TENANT) == before
    assert (await retailer.service.product(TENANT, "SAMPLE-LAMP"))["price"]["amount"] == 534.19


@pytest.mark.asyncio
async def test_template_defaults_and_no_result_counts_are_tenant_scoped():
    retailer = await prepared()
    await retailer.set_templates(TENANT, {"lighting": {"stand": "stand"}})
    await retailer.import_file(TENANT, envelope())
    assert (await retailer.store.templates_for(TENANT))["lighting"] == {"stand": "stand"}
    await retailer.service.search(TENANT, "no-such-product-xyz", 12)
    assert (await retailer.panel(TENANT))["missed_searches"]
    assert (await retailer.panel(OTHER))["missed_searches"] == []
    assert (await retailer.panel(OTHER))["templates"] == {}


@pytest.mark.asyncio
async def test_private_api_needs_control_key_and_ignores_body_tenant_in_data(monkeypatch):
    retailer = await prepared()
    app = create_retailer_app(retailer.service)
    key = secrets.token_hex(32)
    monkeypatch.setenv("RIG_RETAILER_KEY", key)
    with TestClient(app) as client:
        assert client.post("/internal/retailer/panel", json={"tenant_id": TENANT}).status_code == 401
        response = client.post("/internal/retailer/panel", headers={"x-rig-retailer-key": key}, json={"tenant_id": OTHER, "data": {"tenant_id": TENANT}})
        assert response.status_code == 200
        assert response.json()["price_configured"] is False
        response = client.post("/internal/retailer/exchange-rate", headers={"x-rig-retailer-key": key}, json={"tenant_id": TENANT, "data": {"currency": "USD", "rate": "20"}})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_access_authorization_and_server_identity_win(monkeypatch):
    app = FastAPI()
    app.include_router(access.router)
    actor = Actor(UUID(TENANT), "retailer-user", False, frozenset({"rig"}))
    app.dependency_overrides[access.identity] = lambda: actor
    seen = []
    async def request(who, operation, data=None):
        seen.append((who, operation, data))
        return {"saved": True}
    monkeypatch.setattr(access, "rig_request", request)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post("/v1/access/rig/admin/exchange-rate", json={"data": {"currency": "USD", "rate": "20"}})
        assert result.status_code == 403
        result = await client.post("/v1/access/rig/admin/templates", json={"data": {"tenant_id": OTHER}})
        assert result.status_code == 200
        assert str(seen[-1][0].tenant_id) == TENANT
        actor = Actor(UUID(TENANT), "retailer-user", False, frozenset())
        result = await client.post("/v1/access/rig/admin/templates", json={"data": {}})
        assert result.status_code == 403


@pytest.mark.asyncio
async def test_postgres_import_rollback_and_schema_reapply(monkeypatch):
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    admin = _admin_url()
    name = "rig_feed_" + secrets.token_hex(6)
    await _create_database(admin, name)
    pool = await asyncpg.create_pool(_database_url(admin, name))
    try:
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()
        retailer = await prepared(store)
        result = await retailer.import_file(TENANT, envelope())
        assert result["receipt"]["added"] == 2
        before = await store.products(TENANT)
        async def fail_cost(self, tenant, row):
            raise RuntimeError("Synthetic storage failure")
        monkeypatch.setattr(PgStore, "save_cost", fail_cost)
        data = envelope()
        data["contents"] = data["contents"].replace('"20.00"', '"999.00"')
        with pytest.raises(RuntimeError, match="Synthetic storage"):
            await retailer.import_file(TENANT, data)
        assert await store.products(TENANT) == before
        assert len(await store.receipts(TENANT)) == 1
        assert await store.products(OTHER) == []
        assert (await retailer.panel(OTHER))["fits"] == []
    finally:
        await pool.close()
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_access_connect_manual_refresh_nightly_and_receipts_on_postgres(monkeypatch):
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    name = "rig_access_" + secrets.token_hex(6)
    admin = _admin_url()
    await _create_database(admin, name)
    pool = await asyncpg.create_pool(_database_url(admin, name))
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / "tank" / "schema.sql").read_text())
            await conn.execute((ROOT / "tank" / "schema.sql").read_text())
        store = PgStore(pool)
        await store.apply_schema()
        retailer = await prepared(store)
        actor = Actor(UUID(TENANT), "retailer-user", False, frozenset({"rig"}))
        monkeypatch.setattr(access, "db", lambda: pool)
        monkeypatch.setenv("TANK_VAULT_KEY", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        async def dispatch(who, operation, data=None):
            assert operation == "import"
            return await retailer.import_file(str(who.tenant_id), data)
        monkeypatch.setattr(access, "rig_request", dispatch)
        calls = []
        async def fetch(url, *, headers, limit):
            calls.append(url)
            assert headers == {}
            assert limit == 8_000_000
            return (SAMPLES / "shopify.json").read_bytes(), {"content-type": "application/json"}
        monkeypatch.setattr(access, "public_get", fetch)
        app = FastAPI()
        app.include_router(access.router)
        app.dependency_overrides[access.identity] = lambda: actor
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            connection = {"target": "rig", "distributor": "shopify", "site": SITE, "endpoint": SITE + "/products.json",
                          "format": "json", "currency": "USD", "official_read_only": True, "auth_mode": "none"}
            response = await client.post("/v1/access/rig/admin/connect", json={"data": connection})
            assert response.status_code == 200
            request = {"target": "rig", "distributor": "shopify", "site": SITE}
            response = await client.post("/v1/access/rig/admin/refresh", json={"data": request})
            assert response.status_code == 200
            assert response.json()["receipt"]["added"] == 2
            actor = Actor(UUID(OTHER), "other-retailer", False, frozenset({"rig"}))
            assert (await client.post("/v1/access/rig/admin/refresh", json={"data": request})).status_code == 409
            actor = Actor(UUID(TENANT), "retailer-user", False, frozenset({"rig"}))
            invalid = {"target": "rig", "distributor": "zanders", "site": "https://SUPPLIER.example/", "format": "csv", "source": "ftp_export", "contents": "not,a,valid,feed"}
            response = await client.post("/v1/access/rig/admin/import", json={"data": invalid})
            assert response.status_code == 200
            assert response.json()["receipt"]["rejected"] == 1
        async with pool.acquire() as conn:
            await conn.execute("UPDATE tank.access_feed_connections SET rig_refresh_at=now()-interval '1 minute' WHERE tenant_id=$1", UUID(TENANT))
        await access.refresh_due_rig_feeds()
        assert len(calls) == 2
        await access.refresh_due_rig_feeds()
        assert len(calls) == 2
        async with pool.acquire() as conn:
            receipts = await conn.fetch("SELECT action,row_count FROM tank.access_receipts WHERE tenant_id=$1 AND room='rig' ORDER BY created_at", UUID(TENANT))
            assert [row["action"] for row in receipts] == ["feed_connected", "feed_imported", "feed_rejected", "feed_imported"]
            summaries = await conn.fetch("SELECT rig_summary FROM tank.access_feed_batches WHERE tenant_id=$1 ORDER BY fetched_at", UUID(TENANT))
            assert json.loads(summaries[-1]["rig_summary"])["updated"] == 2
            assert await conn.fetchval("SELECT count(*) FROM tank.access_feed_batches WHERE tenant_id=$1 AND site<>$2", UUID(TENANT), SITE) == 0
            assert await conn.fetchval("SELECT count(*) FROM tank.access_receipts WHERE tenant_id=$1 AND site<>$2", UUID(TENANT), SITE) == 0
            await conn.execute("""INSERT INTO tank.access_feed_batches(tenant_id,id,distributor,site,source,row_count)
                VALUES($1,gen_random_uuid(),'zanders',$2,'ftp_export',1)""", UUID(TENANT), SITE)
        panel = await access.connections(actor)
        assert len(panel["feeds"]) == 1
        assert panel["feeds"][0]["distributor"] == "zanders"
    finally:
        await pool.close()
        await _drop_database(admin, name)


def test_authentication_headers_are_explicit_and_do_not_use_url_credentials():
    token = secrets.token_hex(24)
    assert access.feed_auth_headers({"auth_mode": "none", "token": token}) == {}
    assert "X-Shopify-Access-Token" in access.feed_auth_headers({"auth_mode": "shopify", "token": token})
    headers = access.feed_auth_headers({"auth_mode": "basic", "username": secrets.token_hex(8), "password": token})
    assert headers["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["shopify", "woocommerce"])
async def test_supplier_stock_status_controls_availability(provider):
    retailer = await prepared()
    data = envelope(provider)
    raw = json.loads(data["contents"])
    if provider == "shopify":
        raw["products"][0]["variants"][0]["available"] = False
    else:
        raw[0]["stock_status"] = "outofstock"
    data["contents"] = json.dumps(raw)
    assert (await retailer.import_file(TENANT, data))["ok"]
    assert (await retailer.store.products(TENANT))[0]["active"] is False


@pytest.mark.asyncio
async def test_late_model_suggestion_cannot_undo_a_review():
    retailer = await prepared()
    await retailer.import_file(TENANT, envelope())
    started, release = asyncio.Event(), asyncio.Event()
    class DelayedModels:
        async def complete(self, tenant, task_type, messages):
            assert task_type == "rig.fit_suggest"
            started.set()
            await release.wait()
            return json.dumps({"fits": [{"part_sku": "SAMPLE-SHADE", "fits_sku": "SAMPLE-LAMP", "rule": {}, "confidence": 0.6, "note": "Synthetic suggestion"}]})
    retailer.service.models = DelayedModels()
    running = asyncio.create_task(retailer.service.suggest(TENANT))
    await started.wait()
    await retailer.service.reject(TENANT, "SAMPLE-SHADE", "SAMPLE-LAMP", None)
    release.set()
    await running
    assert (await retailer.store.fits(TENANT))[0]["source"] == "rejected"
    assert (await retailer.service.suggested_fits(TENANT))["fits"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["shopify", "woocommerce"])
async def test_catalogue_pagination_uses_existing_fetcher_and_keeps_credentials_same_site(monkeypatch, provider):
    endpoint = SITE + "/products.json"
    seen = []
    first = {"products": [{"id": 1}]} if provider == "shopify" else [{"id": 1}]
    second = {"products": [{"id": 2}]} if provider == "shopify" else [{"id": 2}]
    async def fetch(url, *, headers, limit):
        seen.append(url)
        assert 0 < limit <= 8_000_000
        if len(seen) == 1:
            pagination = {"Link": f'<{endpoint}?page=2>; rel="next"'} if provider == "shopify" else {"X-WP-TotalPages": "2"}
            return json.dumps(first).encode(), pagination
        return json.dumps(second).encode(), {}
    monkeypatch.setattr(access, "public_get", fetch)
    raw = await access.read_rig_feed({"endpoint": endpoint, "distributor": provider}, {})
    loaded = json.loads(raw)
    assert len(loaded["products"] if isinstance(loaded, dict) else loaded) == 2
    assert seen == [endpoint, endpoint + "?page=2"]


@pytest.mark.asyncio
async def test_catalogue_pagination_refuses_other_hosts_and_secret_query_fields(monkeypatch):
    endpoint = SITE + "/products.json"
    for next_url in ["https://other.example/products.json?page=2", SITE + "/admin/delete?page=2", endpoint + "?token=not-a-credential", endpoint]:
        calls = []
        async def fetch(url, *, headers, limit):
            calls.append(url)
            return b'{"products":[]}', {"link": f'<{next_url}>; rel="next"'}
        monkeypatch.setattr(access, "public_get", fetch)
        with pytest.raises(ValueError):
            await access.read_rig_feed({"endpoint": endpoint, "distributor": "shopify"}, {})
        assert calls == [endpoint]
