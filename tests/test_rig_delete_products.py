"""Offline deletion contract, also exercised on a disposable local Postgres."""
import json
from copy import deepcopy
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from test_rig_feeds_retailer import OTHER, TENANT, envelope, prepared
from rigbox.service import RigError
from rigbox.store import MemoryStore, PgStore
import access
from command import Actor


@pytest_asyncio.fixture(params=["memory", "postgres"])
async def retailer(request):
    if request.param == "memory":
        yield await prepared()
        return
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    admin = _admin_url()
    name = "rig_delete_" + uuid4().hex
    await _create_database(admin, name)
    pool = await asyncpg.create_pool(_database_url(admin, name))
    try:
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()
        yield await prepared(store)
    finally:
        await pool.close()
        await _drop_database(admin, name)


async def seed(retailer):
    assert (await retailer.import_file(TENANT, envelope()))["ok"]
    for row in await retailer.store.products(TENANT):
        await retailer.store.upsert_product(OTHER, row)
    await retailer.store.set_family(TENANT, "lighting", ["SAMPLE-LAMP", "SAMPLE-SHADE"])
    await retailer.store.set_family(OTHER, "lighting", ["SAMPLE-LAMP", "SAMPLE-SHADE"])
    for part, target in [("SAMPLE-LAMP", "SAMPLE-SHADE"), ("SAMPLE-SHADE", "SAMPLE-LAMP")]:
        for tenant in (TENANT, OTHER):
            await retailer.store.upsert_fit(tenant, {"part_sku": part, "fits_sku": target, "source": "import", "approved": True, "note": "Stored source"})
    await retailer.store.add_quote(TENANT, "historical", {"sku": "SAMPLE-LAMP", "price": 534.19}, {})
    await retailer.store.put_answer(TENANT, "graph", "SAMPLE-SHADE", "version", {"sku": "SAMPLE-LAMP"})
    await retailer.store.put_answer(OTHER, "graph", "SAMPLE-SHADE", "version", {"sku": "SAMPLE-LAMP"})
    await retailer.service.search(TENANT, "Sample Lamp", 12)


@pytest.mark.asyncio
@pytest.mark.parametrize("skus", [["SAMPLE-LAMP"], ["SAMPLE-LAMP", "SAMPLE-SHADE", "SAMPLE-LAMP"]])
async def test_delete_atomic_scoped_history_search_and_receipt(retailer, skus):
    await seed(retailer)
    store = retailer.store
    history = deepcopy(await store.quotes_for(TENANT))
    other = deepcopy(await store.products(OTHER))
    result = await retailer.delete_products(TENANT, {"skus": skus, "tenant_id": OTHER})
    assert result["deleted"] == len(set(skus))
    assert result["receipt"]["updated"] == len(set(skus))
    assert set(result["receipt"]) == {"id", "provider", "site", "feed_id", "added", "updated", "rejected"}
    assert "SAMPLE" not in json.dumps(result["receipt"])
    assert await store.deleted_skus(TENANT) == set(skus)
    assert not (set(skus) & {row["sku"] for row in await store.products(TENANT)})
    assert not (set(skus) & {row["sku"] for row in await store.costs(TENANT)})
    assert await store.fits(TENANT) == []
    assert len(await store.fits(OTHER)) == 2
    assert await store.products(OTHER) == other
    assert await store.deleted_skus(OTHER) == set()
    assert await store.quotes_for(TENANT) == history
    assert await store.get_answer(TENANT, "graph", "SAMPLE-SHADE", "version") is None
    assert await store.get_answer(OTHER, "graph", "SAMPLE-SHADE", "version") == {"sku": "SAMPLE-LAMP"}
    result = await retailer.service.search(TENANT, "Sample Lamp", 12)
    assert "SAMPLE-LAMP" not in json.dumps(result)
    with pytest.raises(RigError):
        await retailer.service.product(TENANT, "SAMPLE-LAMP")
    if isinstance(store, MemoryStore):
        assert not set(skus) & set(store.families[(TENANT, "lighting")])
        assert store.families[(OTHER, "lighting")] == ["SAMPLE-LAMP", "SAMPLE-SHADE"]
    else:
        async with store.pool.acquire() as conn:
            members = await conn.fetchval("SELECT member_skus FROM agent_rig.families WHERE tenant_id=$1 AND family='lighting'", UUID(TENANT))
            assert not set(skus) & set(members)


@pytest.mark.asyncio
async def test_delete_keeps_unrelated_searches_and_missed_search_counts(retailer):
    assert (await retailer.import_file(TENANT, envelope()))["ok"]
    store = retailer.store
    searches = [
        {"id": "returned-deleted", "query": "desk lamp", "ids": ["SAMPLE-SHADE", "SAMPLE-LAMP"], "exact_match": True},
        {"id": "other-hit", "query": "SAMPLE-LAMP shade", "ids": ["SAMPLE-SHADE"], "exact_match": True},
        {"id": "closest-hit", "query": "blue shade", "ids": ["SAMPLE-SHADE"], "exact_match": False},
        {"id": "miss-one", "query": "missing desk", "ids": [], "exact_match": False},
        {"id": "miss-two", "query": "missing desk", "ids": [], "exact_match": False},
    ]
    for tenant in (TENANT, OTHER):
        for row in searches:
            await store.add_search(tenant, "saved-version", row)
    before = await store.searches_for(TENANT, "saved-version")
    other_before = await store.searches_for(OTHER, "saved-version")
    missed_before = await store.missed_searches(TENANT)
    assert len(before) == len(other_before) == 5
    assert {row["query"]: row["count"] for row in missed_before} == {"missing desk": 2, "blue shade": 1}

    assert (await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP"]}))["deleted"] == 1

    remaining = await store.searches_for(TENANT, "saved-version")
    assert len(remaining) == 4
    assert remaining == [row for row in before if row["query"] != "desk lamp"]
    assert await store.missed_searches(TENANT) == missed_before
    assert await store.searches_for(OTHER, "saved-version") == other_before
    assert await store.missed_searches(OTHER) == missed_before


@pytest.mark.asyncio
async def test_refresh_keeps_removed_sku_and_manual_import_restores(retailer):
    await seed(retailer)
    await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP"]})
    data = envelope()
    for _ in range(2):
        result = await retailer.import_file(TENANT, {**data, "refresh": True})
        assert result["ok"]
        assert result["receipt"]["added"] == 0
        assert not await retailer.store.product_exists(TENANT, "SAMPLE-LAMP")
        assert await retailer.store.fits(TENANT) == []
    # Legacy scheduled feeds cannot bypass the removal either.
    await retailer.store.put_feed(TENANT, "shopify", "https://supplier.example/feed", "USD")
    async def fetch(_url):
        return json.loads(data["contents"])
    await retailer.service.pull_feeds(TENANT, fetch)
    assert not await retailer.store.product_exists(TENANT, "SAMPLE-LAMP")
    assert (await retailer.import_file(TENANT, data))["receipt"]["added"] == 1
    assert await retailer.store.deleted_skus(TENANT) == set()
    assert await retailer.store.product_exists(TENANT, "SAMPLE-LAMP")


@pytest.mark.asyncio
async def test_all_deleted_refresh_succeeds_without_restoring_families(retailer):
    await seed(retailer)
    await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP", "SAMPLE-SHADE"]})
    result = await retailer.import_file(TENANT, {**envelope(), "refresh": True})
    assert result["ok"]
    assert result["receipt"]["added"] == result["receipt"]["updated"] == 0
    assert await retailer.store.products(TENANT) == []
    assert await retailer.store.fits(TENANT) == []


@pytest.mark.asyncio
async def test_receipt_failure_rolls_back_entire_delete(retailer, monkeypatch):
    await seed(retailer)
    store = retailer.store
    before = [deepcopy(await getattr(store, name)(TENANT)) for name in ("products", "costs", "fits", "receipts")]
    async def fail(*_):
        raise RuntimeError("Offline receipt failure")
    monkeypatch.setattr(type(store), "save_feed_receipt", fail)
    with pytest.raises(RuntimeError):
        await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP"]})
    assert await store.deleted_skus(TENANT) == set()
    assert [await getattr(store, name)(TENANT) for name in ("products", "costs", "fits", "receipts")] == before
    assert await store.get_answer(TENANT, "graph", "SAMPLE-SHADE", "version") is not None


@pytest.mark.asyncio
async def test_unknown_sku_and_validation_do_not_touch_other_tenant():
    retailer = await prepared()
    await seed(retailer)
    for skus in (None, [], "SAMPLE-LAMP", [None], [True], [" "], ["x"] * 5001):
        with pytest.raises(ValueError):
            await retailer.delete_products(TENANT, {"skus": skus})
    await retailer.store.upsert_product(OTHER, {**(await retailer.store.products(OTHER))[0], "sku": "OTHER-ONLY"})
    assert (await retailer.delete_products(TENANT, {"skus": ["OTHER-ONLY"]}))["deleted"] == 0
    assert await retailer.store.product_exists(OTHER, "OTHER-ONLY")
    assert await retailer.store.deleted_skus(TENANT) == set()
    assert (await retailer.delete_products(TENANT, {"skus": [str(n) for n in range(5000)]}))["deleted"] == 0


@pytest.mark.asyncio
async def test_tank_delete_route_founder_and_tenant_boundary(monkeypatch):
    retailer = await prepared()
    await seed(retailer)
    app = FastAPI()
    app.include_router(access.router)
    actor = Actor(UUID(TENANT), "founder", True, frozenset())
    app.dependency_overrides[access.identity] = lambda: actor
    async def request(who, operation, data=None):
        assert operation == "delete-products"
        return await retailer.delete_products(str(who.tenant_id), data)
    monkeypatch.setattr(access, "rig_request", request)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/access/rig/admin/delete-products", json={"data": {"skus": ["SAMPLE-LAMP"], "tenant_id": OTHER}})
        assert response.status_code == 200
        assert response.json()["deleted"] == 1
        assert await retailer.store.product_exists(OTHER, "SAMPLE-LAMP")
        actor = Actor(UUID(TENANT), "member", False, frozenset())
        assert (await client.post("/v1/access/rig/admin/delete-products", json={"data": {"skus": ["SAMPLE-SHADE"]}})).status_code == 403
        actor = Actor(UUID(TENANT), "admin", False, frozenset({"rig"}))
        assert (await client.post("/v1/access/rig/admin/delete-products", json={"data": {"skus": [str(n).zfill(20) for n in range(5000)]}})).status_code == 200


@pytest.mark.asyncio
async def test_last_family_target_removed_and_refresh_accepts_other_rows(retailer):
    data = envelope()
    body = json.loads(data["contents"])
    body["rig"]["fits"] = [{"part_sku": "SAMPLE-SHADE", "fits_family": "sample-lighting", "note": "Source family"}]
    data["contents"] = json.dumps(body)
    assert (await retailer.import_file(TENANT, data))["ok"]
    await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP"]})
    assert await retailer.store.fits(TENANT) == []
    result = await retailer.import_file(TENANT, {**data, "refresh": True})
    assert result["ok"]
    assert result["receipt"]["updated"] == 1
    assert await retailer.store.fits(TENANT) == []


@pytest.mark.asyncio
async def test_failed_manual_restore_preserves_removal(retailer, monkeypatch):
    await seed(retailer)
    await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP"]})
    async def fail(*_):
        raise ValueError("Offline private-cost failure")
    monkeypatch.setattr(type(retailer.store), "save_cost", fail)
    assert not (await retailer.import_file(TENANT, envelope()))["ok"]
    assert await retailer.store.deleted_skus(TENANT) == {"SAMPLE-LAMP"}
    assert not await retailer.store.product_exists(TENANT, "SAMPLE-LAMP")


@pytest.mark.asyncio
@pytest.mark.parametrize("retailer", ["postgres"], indirect=True)
async def test_dependent_three_d_jobs_removed_only_for_deleted_product(retailer):
    await seed(retailer)
    async with retailer.store.pool.acquire() as conn:
        for tenant, sku in [(TENANT, "SAMPLE-LAMP"), (TENANT, "SAMPLE-SHADE"), (OTHER, "SAMPLE-LAMP")]:
            await conn.execute("INSERT INTO agent_rig.rig_3d_jobs(tenant_id,id,product_id,request) VALUES($1,$2,$3,'{}')", UUID(tenant), uuid4(), sku)
    await retailer.delete_products(TENANT, {"skus": ["SAMPLE-LAMP"]})
    async with retailer.store.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM agent_rig.rig_3d_jobs WHERE tenant_id=$1 AND product_id='SAMPLE-LAMP'", UUID(TENANT)) == 0
        assert await conn.fetchval("SELECT count(*) FROM agent_rig.rig_3d_jobs WHERE tenant_id=$1", UUID(TENANT)) == 1
        assert await conn.fetchval("SELECT count(*) FROM agent_rig.rig_3d_jobs WHERE tenant_id=$1", UUID(OTHER)) == 1
