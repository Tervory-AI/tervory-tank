"""Real agent handler, Tank/Rig ASGI routes and tenant-scoped local SQL."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from test_tiger import ROOT, _load, _watch
from test_tg2_tiger_watchlist import _request
from rig_tiger_prices.test_prices import corridor, product  # noqa: F401
from test_alerts import A, B, KINDS, URL, PEER, listing, watched, checked
from tiger_works.fixture import extract, no_paid_call, saved_page
from test_tiger_alert_email import catcher  # noqa: F401
from alert_email import deliver_pending
from rigbox.store import PgStore as RigStore
from rig_watch import TankRig
from watch import DomainLimiter, PgStore
import access
import main as tank

agent = _load("g5_tiger_agent", ROOT / "agents/tiger/app.py")


@pytest_asyncio.fixture
async def system(database, corridor, monkeypatch):  # noqa: F811
    _, service, http = corridor
    rig = RigStore(database)
    service.store = rig
    for tenant in (A, B):
        await product(rig, tenant, sku="own-item", url="https://own.example/item")
        await rig.save_cost(tenant, {"sku": "own-item", "cost": "125" if tenant == A else "100",
                                   "currency": "USD", "provider": "fixture", "site": "https://supplier.example"})
        async with database.acquire() as conn:
            await conn.executemany("INSERT INTO tank.access_feed_links(tenant_id,url,sku) VALUES($1,$2,$3)",
                                   [(UUID(tenant), url, "own-item") for url in (URL, PEER, "https://own.example/item")])
    monkeypatch.setattr(access, "db", lambda: database)
    monkeypatch.setenv("TANK_URL", "http://tank")
    monkeypatch.setenv("TANK_KEY", "offline-tiger")
    monkeypatch.setattr(agent.app.state, "pool", database, raising=False)
    monkeypatch.setattr(agent.app.state, "http", http, raising=False)
    monkeypatch.setattr(agent, "_limiter", DomainLimiter(0))
    async def no_feed(*args):
        return {"found": False}
    monkeypatch.setattr(agent, "official_feed", no_feed)
    return rig, PgStore(database), http


@pytest.mark.asyncio
async def test_private_cost_read_uses_same_tenant_sku_and_never_retail_price(system, database):
    rig, store, http = system
    relay = TankRig(http)
    a = await relay.alert_context(A, URL)
    b = await relay.alert_context(B, URL)
    assert a["product"]["cost"] == "125" and b["product"]["cost"] == "100"
    for tenant, ctx in ((A, a), (B, b)):
        watch = await watched(store, tenant, alert_market_gap=False)
        result = await checked(store, watch, ctx=ctx)
        assert [r["kind"] for r in result["alerts"]] == (["below_cost"] if tenant == A else [])
    absent = await relay.alert_context(str(uuid4()), URL)
    assert absent["product"] is None and absent["urls"] == []
    assert (await relay.alert_context(A, "https://unmatched.example/item"))["product"] is None
    async with database.acquire() as conn:
        await conn.execute("DELETE FROM agent_rig.supplier_costs WHERE tenant_id=$1", UUID(A))
    assert (await relay.alert_context(A, URL))["product"]["cost"] is None
    assert (await relay.alert_context(B, URL))["product"]["cost"] == "100"
    await rig.delete_products(B, ["own-item"])
    assert (await relay.alert_context(B, URL))["product"] is None
    denied = await http.get("/v1/access/rig/tiger/alert-context", params={"tenant_id": A, "url": URL},
                            headers={"x-tank-key": "wrong"})
    assert denied.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_agent_job_to_existing_email_path(system, catcher, monkeypatch, kind):
    _, store, _ = system
    watches = [await watched(store, tenant, **{"alert_" + k: k == kind for k in KINDS}) for tenant in (A, B)]
    state = {"added": False, "reads": []}
    async def render(url, session, name, tenant, task):
        state["reads"].append((tenant, url))
        return {"ok": True, "html": listing(state["added"]) if kind == "new_product" else
                saved_page("120", "OutOfStock" if kind == "market_gap" else "InStock"),
                "png_base64": "offline-image-must-not-be-used"}
    async def skill(tenant, name, data):
        assert name == "tiger.price_extract", "No model/OCR needed for these pages"
        return await extract(data["html"], data["url"])
    monkeypatch.setattr(agent, "_render", render)
    for watch in watches:
        state["added"] = False
        ctx = SimpleNamespace(tenant_id=watch["tenant_id"], agent="tiger", job_id=uuid4(),
                              input={"url": URL}, files=None, tank=SimpleNamespace(run_skill=skill))
        first = await agent.check(ctx)
        if kind == "new_product":
            assert first["alerts"] == []
            state["added"] = True
            first = await agent.check(ctx)
        expected = [] if kind == "below_cost" and watch["tenant_id"] == B else [kind]
        assert [r["kind"] for r in first["alerts"]] == expected
        assert (await agent.check(ctx))["alerts"] == []
        sent = await deliver_pending(store, watch["tenant_id"], transport=catcher.transport,
            recipient=("a" if watch["tenant_id"] == A else "b") + "@example.test",
            clock=lambda: datetime(2030, 1, 1, tzinfo=timezone.utc))
        assert sent["sent"] == len(expected)
    assert len(state["reads"]) == (6 if kind == "new_product" else 4)
    assert len(catcher.messages) == (1 if kind == "below_cost" else 2)


@pytest.mark.asyncio
async def test_switches_create_patch_read_and_cross_tenant_refusal(database, monkeypatch):
    store = PgStore(database)
    monkeypatch.setattr(agent, "_store", lambda: store)
    # Direct ASGI transport through the real Tank relay to the real agent route.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app)) as room:
        async def call(method, path, params, body):
            return await room.request(method, "http://agent-tiger" + path, params=params,
                                      content=body, headers={"content-type": "application/json"})
        monkeypatch.setattr(tank, "_tiger_call", call)
        # Public literal IP prevents DNS/network in watch URL validation.
        import json
        ids = {}
        for tenant in (A, B):
            response = await tank.tiger_create_watch(_request("POST", "/v1/tiger/watchlist", body=json.dumps({
                **_watch(tenant), "url": "https://8.8.8.8/item", "alert_new_product": False,
                "alert_below_cost": False, "alert_market_gap": False}).encode()))
            assert response.status_code == 201
            row = json.loads(response.body)
            ids[tenant] = row["id"]
            assert not any(row["alert_" + kind] for kind in KINDS)
        body = json.dumps({"tenant_id": A, **{"alert_" + kind: True for kind in KINDS}}).encode()
        changed = await tank.tiger_update_watch(UUID(ids[A]), _request("PATCH", "/v1/tiger/watchlist/" + ids[A], body=body))
        assert changed.status_code == 200 and all(json.loads(changed.body)["alert_" + kind] for kind in KINDS)
        denied = await tank.tiger_update_watch(UUID(ids[B]), _request("PATCH", "/v1/tiger/watchlist/" + ids[B], body=body))
        assert denied.status_code == 404
        other = await store.get_watch_by_id(B, ids[B])
        assert not any(other["alert_" + kind] for kind in KINDS)
