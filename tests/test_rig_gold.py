"""Gold candidates use uploaded database products and approved fits per tenant."""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/rig"))
sys.path.insert(0, str(ROOT / "agents/_chassis"))
from rigbox.store import MemoryStore, PgStore
from rigbox.logic import search
from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database

KEY = "room-key-for-gold"


def _load_gold():
    spec = importlib.util.spec_from_file_location("rig_room_gold_test", ROOT / "agents/rig/gold_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


candidates = _load_gold().candidates


async def uploaded(store, tenant):
    await store.put_retailer(tenant, "owned-store", None, None)
    for sku in ("PART-1", "BASE-1", "UNAPPROVED", "NOT-UPLOADED", "INACTIVE", "DEMO"):
        await store.upsert_product(tenant, dict(sku=sku, name=sku, brand="LumaWorks", category="part", price=12,
            currency="USD", image_url="", active=sku != "INACTIVE", attributes={"sample": sku == "DEMO"}))
        if sku != "NOT-UPLOADED":
            await store.index_feed_products(tenant, "https://store.example/upload.csv", [sku])
    for sku in ("PART-1", "UNAPPROVED", "NOT-UPLOADED", "INACTIVE", "DEMO"):
        await store.upsert_fit(tenant, dict(part_sku=sku, fits_sku="BASE-1", fits_family=None,
            rule={}, source="suggested", approved=sku != "UNAPPROVED", confidence=1))


@pytest.mark.asyncio
async def test_gold_uses_only_uploaded_active_products_and_approved_fits_per_tenant():
    store = MemoryStore()
    first, other = str(uuid4()), str(uuid4())
    await uploaded(store, first)
    await uploaded(store, other)
    rows = await candidates(store, first, region="za")
    assert [r['skill_id'] for r in rows] == ['rig.search', 'rig.fit_suggest']
    assert all(r['tenant_id'] == first and r['region'] == 'za' and r['public'] is False for r in rows)
    assert all(r['input']['tenant_id'] == first for r in rows)
    assert all(r['label_source'] == first + ':PART-1' for r in rows)
    assert search(rows[0]['input'])['ids'] == ['PART-1']
    assert all(p['tenant_id'] == first for p in rows[0]['input']['products'])
    assert not {'NOT-UPLOADED', 'INACTIVE', 'DEMO'} & {p['sku'] for p in rows[0]['input']['products']}
    assert rows[1]['expected']['fits'] == [dict(part_sku='PART-1', fits_sku='BASE-1', fits_family=None, rule={})]
    assert len(await candidates(store, first, limit=1)) == 1
    assert await candidates(store, None) == []
    assert await candidates(store, str(uuid4())) == []
    assert await candidates(store, first, region='eu-west') == []
    assert await candidates(store, first, limit=0) == []
    assert await candidates(MemoryStore(), first) == []
    # A revision of an approved fit is a new label family.
    original = rows[0]['label_family']
    await store.upsert_fit(first, dict(part_sku='PART-1', fits_sku='BASE-1', rule={'mount': 'changed'}, approved=True))
    assert (await candidates(store, first, region='za'))[0]['label_family'] != original


@pytest.mark.asyncio
async def test_gold_reads_real_postgres_and_keeps_tenants_apart():
    admin, name = _admin_url(), 'rig_gold_' + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            first, other = str(uuid4()), str(uuid4())
            await uploaded(store, first)
            await uploaded(store, other)
            for tenant in (first, other):
                rows = await candidates(store, tenant, region='us-east')
                assert len(rows) == 2
                assert all(r['tenant_id'] == tenant for r in rows)
                assert all(p['tenant_id'] == tenant for p in rows[0]['input']['products'])
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


def _app():
    path = ROOT / "agents" / "rig" / "app.py"
    spec = importlib.util.spec_from_file_location("rig_gold_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rig_gold_app"] = module
    spec.loader.exec_module(module)
    return module


def _call(module, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
    sent: list[dict] = []
    route, _, query = path.partition("?")

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": route,
        "raw_path": route.encode(),
        "query_string": query.encode(),
        "headers": [[name.lower().encode(), value.encode()] for name, value in headers.items()],
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
    }

    import asyncio

    asyncio.run(module.app(scope, receive, send))
    body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    return int(sent[0]["status"]), body


def test_gold_route_requires_room_key_and_explicit_tenant(monkeypatch):
    from types import SimpleNamespace
    from rigbox.service import Service
    from fastapi.testclient import TestClient
    import asyncio
    monkeypatch.setenv('TANK_KEY', KEY)
    monkeypatch.setenv('TANK_REGION', 'za')
    module = _app()
    store = MemoryStore()
    tenant = str(uuid4())
    asyncio.run(uploaded(store, tenant))
    module.app.state.rig = Service(store)
    # Do not start the real application lifespan for this route test.
    client = TestClient(module.app)
    for headers in ({}, {'X-Rig-Key': KEY}, {'X-Tank-Key': 'other'}, {'X-Tank-Key': 'clé-🔐'}):
        status, _ = _call(module, '/gold/candidates', headers)
        assert status == 401
    assert client.get('/gold/candidates', headers={'X-Tank-Key': KEY}).json() == []
    rows = client.get('/gold/candidates', params={'tenant_id': tenant, 'limit': 2}, headers={'X-Tank-Key': KEY}).json()
    assert len(rows) == 2
    assert all(r['tenant_id'] == tenant and r['region'] == 'za' and r['public'] is False for r in rows)
    assert client.get('/gold/candidates', params={'tenant_id': str(uuid4())}, headers={'X-Tank-Key': KEY}).json() == []
    assert client.get('/gold/candidates', params={'tenant_id': 'invalid'}, headers={'X-Tank-Key': KEY}).status_code == 422
