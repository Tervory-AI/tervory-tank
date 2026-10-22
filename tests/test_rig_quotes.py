"""RIG-4: real HTTP contracts with an Odoo stub, no external requests."""

import asyncio
from datetime import date
import json
from pathlib import Path
import sys
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))

from rigbox.api import mount  # noqa: E402
from rigbox.quotes.api import mount as mount_quotes  # noqa: E402
from rigbox.quotes.sample import KEY, TENANT, seed  # noqa: E402
from rigbox.quotes.senders import DeliveryError, OdooHandoff, RetailerHandoff  # noqa: E402
from rigbox.quotes.service import QuoteService  # noqa: E402
from rigbox.quotes.store import MemoryQuotes  # noqa: E402
from rigbox.service import RecordingHandoff, RigError, hash_key  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

OTHER = "55555555-5555-4555-8555-555555555555"
CONTACT = {"name": "Sample Shopper", "email": "shopper@example.com"}


async def service(handoff=None):
    store = MemoryStore()
    await seed(store)
    return QuoteService(store, None, handoff or RecordingHandoff(), MemoryQuotes(store))


class OdooStub:
    def __init__(self):
        self.calls = []
        self.orders = []
        self.fail_after_create = False
        self.missing_product = False
        self.version = 17

    def __call__(self, request):
        assert request.url.path == "/jsonrpc"
        body = json.loads(request.content)
        assert body["jsonrpc"] == "2.0" and body["method"] == "call"
        params = body["params"]
        if params["service"] == "common":
            if params["method"] == "version":
                return httpx.Response(200, json={"result": {"server_version_info": [self.version, 0, 0]}})
            assert params["method"] == "authenticate"
            return httpx.Response(200, json={"result": 7})
        assert params["method"] == "execute_kw"
        _, uid, _, model, method, args, kwargs = params["args"]
        assert uid == 7
        self.calls.append((model, method, args, kwargs))
        if model == "sale.order" and method == "search":
            result = [index + 1 for index, order in enumerate(self.orders)
                      if order["client_order_ref"] == args[0][0][2]]
        elif model == "sale.order" and method == "create":
            self.orders.append(args[0])
            if self.fail_after_create:
                self.fail_after_create = False
                raise httpx.ReadTimeout("stub", request=request)
            result = len(self.orders)
        elif model == "product.product" and self.missing_product:
            result = []
        elif method == "search":
            result = [42]
        elif method == "create":
            result = 42
        else:
            raise AssertionError((model, method))
        return httpx.Response(200, json={"result": result})


def adapter(http):
    key_var = "RIG_ODOO_API_KEY"
    return OdooHandoff(http, url="https://odoo.example", database="sample", user="RIG_ODOO_USER",
                       api_key=key_var)


@pytest.mark.asyncio
async def test_quote_reprices_and_only_sends_approved_parts():
    rig = await service()
    built = (await rig.setups(TENANT, "CORE-1"))["setups"][0]
    built["total"]["amount"] = 1
    built["parts"][0]["product"]["price"]["amount"] = 1
    ack = await rig.quote(TENANT, {"setup": built, "contact": CONTACT})
    assert ack["delivery"] == "sent"
    stored = (await rig.store.quotes_for(TENANT))[0]
    assert stored["payload"]["setup"]["total"]["amount"] == 120
    built["parts"][1]["product"]["id"] = "PART-DRAFT"
    with pytest.raises(RigError, match="approved fit"):
        await rig.quote(TENANT, {"setup": built, "contact": CONTACT})
    with pytest.raises(RigError, match="approved fit"):
        await rig.swap(TENANT, built, "Part")
    assert len(await rig.store.quotes_for(TENANT)) == 1


@pytest.mark.asyncio
async def test_missing_configuration_is_stored_pending_and_can_be_retried(monkeypatch):
    monkeypatch.setenv("RIG_QUOTE_FLOWS", "")
    rig = await service(RetailerHandoff(None))
    ack = await rig.quote(TENANT, {"product_id": "CORE-1", "contact": CONTACT})
    assert ack["delivery"] == "pending"
    assert "pending" in ack["message"]
    assert (await rig.store.quotes_for(TENANT))[0]["sent_at"] is None
    assert (await rig.quote_store.status(TENANT, ack["request_id"]))["error"] == "not_configured"
    rig.handoff = RecordingHandoff()
    assert not await rig.quote_store.pending(TENANT)
    await rig.quote_store.retry_now(TENANT, ack["request_id"])
    await asyncio.gather(rig.deliver(TENANT, ack["request_id"]), rig.deliver(TENANT, ack["request_id"]))
    assert len(rig.handoff.sent) == 1
    assert (await rig.quote_store.status(TENANT, ack["request_id"]))["status"] == "sent"
    assert (await rig.quote_store.analytics(TENANT, date.min))["quotes"] == 1


@pytest.mark.asyncio
async def test_odoo_draft_uses_server_price_and_reconciles_timeout():
    stub = OdooStub()
    stub.fail_after_create = True
    async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
        rig = await service(adapter(http))
        ack = await rig.quote(TENANT, {"product_id": "CORE-1", "contact": CONTACT})
        assert ack["delivery"] == "pending"
        await rig.quote_store.retry_now(TENANT, ack["request_id"])
        await rig.retry_pending(TENANT)
        assert (await rig.quote_store.status(TENANT, ack["request_id"]))["status"] == "sent"
    assert len(stub.orders) == 1
    order = stub.orders[0]
    assert order["order_line"][0][2]["price_unit"] == 100
    assert order["order_line"][0][2]["tax_id"] == [[6, 0, []]]
    assert order["pricelist_id"] == 42
    assert order["client_order_ref"] == f"rig:{TENANT}:{ack['request_id']}"
    assert all(call[1] in {"search", "create"} for call in stub.calls)
    assert "state" not in order  # Odoo's create default is a draft quotation.


@pytest.mark.asyncio
async def test_link_request_is_stored_and_sent_as_unpriced_odoo_note():
    stub = OdooStub()
    async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
        rig = await service(adapter(http))
        ack = await rig.link_quote(TENANT, "https://example.com/item", "Please source this", CONTACT)
    assert ack["delivery"] == "sent"
    line = stub.orders[0]["order_line"][0][2]
    assert line["display_type"] == "line_note"
    assert "https://example.com/item" in line["name"]
    assert "price_unit" not in line and "product_id" not in line
    assert (await rig.store.quotes_for(TENANT))[0]["contact"] == CONTACT


@pytest.mark.asyncio
async def test_odoo_refuses_unmapped_sku_and_remote_error_is_not_exposed():
    stub = OdooStub()
    stub.missing_product = True
    async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
        rig = await service(adapter(http))
        ack = await rig.quote(TENANT, {"product_id": "CORE-1", "contact": CONTACT})
        assert ack["delivery"] == "pending"
        assert not stub.orders
        assert (await rig.quote_store.status(TENANT, ack["request_id"]))["error"] == "odoo_product_mapping"
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"error": {"data": "PRIVATE_REMOTE_DIAGNOSTIC"}}))) as http:
        with pytest.raises(DeliveryError, match="^odoo_rejected$"):
            await adapter(http).send(tenant_id=TENANT, email=None, webhook=None,
                                    quote={"id": "request", "payload": {}, "contact": CONTACT})


@pytest.mark.asyncio
async def test_flow_is_exact_tenant_and_webhook_checks_http_status(monkeypatch):
    monkeypatch.setenv("RIG_QUOTE_FLOWS", json.dumps({TENANT: {"sender": "odoo"}}))
    for name in ("RIG_ODOO_URL", "RIG_ODOO_DATABASE", "RIG_ODOO_USER", "RIG_ODOO_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    calls = []

    def reject(request):
        calls.append(request)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(reject)) as http:
        sender = RetailerHandoff(http)
        quote = {"id": "request", "payload": {}, "contact": CONTACT}
        with pytest.raises(DeliveryError, match="not_configured"):
            await sender.send(tenant_id=TENANT, email=None, webhook="https://portal.example", quote=quote)
        assert not calls
        with pytest.raises(DeliveryError, match="retailer_unavailable"):
            await sender.send(tenant_id=OTHER, email=None, webhook="https://portal.example", quote=quote)
        assert calls[0].headers["Idempotency-Key"] == f"rig:{OTHER}:request"


def test_http_flow_counts_and_admin_isolation():
    async def ready():
        rig = await service()
        rig.store._products[(TENANT, "CORE-1")]["attributes"].update({
            "supplier_cost": 1, "pricing_rule": {"duty": 2, "margin": 3}, "vat": 4,
        })
        await rig.store.put_key(TENANT, hash_key("RIG_ADMIN_KEY"), "admin", [])
        await rig.store.put_key(OTHER, hash_key("OTHER_ADMIN_KEY"), "admin", [])
        return rig

    rig = asyncio.run(ready())
    app = FastAPI()
    app.state.rig = rig
    mount(app)
    mount_quotes(app)
    headers = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
    admin = {"X-Rig-Key": "RIG_ADMIN_KEY"}
    other = {"X-Rig-Key": "OTHER_ADMIN_KEY"}
    with TestClient(app) as client:
        found = client.get("/v1/rig/search?q=Core", headers=headers)
        assert found.status_code == 200
        assert all(word not in found.text for word in ("supplier_cost", "pricing_rule", '"duty"', '"margin"', '"vat"'))
        empty = client.get("/v1/rig/search?q=zzzzzzzzzzzzzz", headers=headers)
        assert empty.json()["results"] == []
        assert client.get("/v1/rig/admin/analytics", headers=admin).json()["counts"]["searches"] == 0
        for no_results in (False, True):
            body = {"event_id": str(uuid4()), "no_results": no_results}
            assert client.post("/v1/rig/search-events", headers=headers, json=body).json() == {"counted": True}
            assert client.post("/v1/rig/search-events", headers=headers, json=body).json() == {"counted": False}
        setup = client.post("/v1/rig/setups", headers=headers, json={"product_id": "CORE-1"}).json()["setups"][0]
        swap = client.post("/v1/rig/swap", headers=headers, json={"setup": setup, "role": "Part"}).json()
        assert [p["id"] for p in swap["options"]] == ["PART-B"]
        setup["parts"][1]["product"] = swap["options"][0]
        assert client.post("/v1/rig/swap", headers=headers,
            json={"setup": setup, "role": "Part", "commit": True}).status_code == 200
        quote = client.post("/v1/rig/quote", headers=headers, json={"setup": setup, "contact": CONTACT})
        assert quote.status_code == 200 and quote.json()["delivery"] == "sent"
        qid = quote.json()["request_id"]
        assert client.get(f"/v1/rig/admin/quotes/{qid}/delivery", headers=other).status_code == 404
        assert client.post(f"/v1/rig/admin/quotes/{qid}/retry", headers=other).status_code == 404
        assert client.get("/v1/rig/admin/analytics", headers=headers).status_code == 403
        counts = client.get("/v1/rig/admin/analytics", headers=admin).json()["counts"]
        assert counts == {"searches": 2, "setups_opened": 1, "swaps": 1, "quotes": 1, "no_results": 1}
        assert set(client.get("/v1/rig/admin/analytics", headers=other).json()["counts"].values()) == {0}
        issued = client.post("/v1/rig/admin/embed-keys", headers=admin,
            json={"origins": ["https://customnation.co.za", "https://rig.tervory.com"]})
        assert issued.status_code == 200
        key = issued.json()["publishable_key"]
        assert client.get("/v1/rig/search?q=Core", headers={"X-Rig-Key": key,
            "Origin": "https://unrelated.example"}).status_code == 403
        allowed = client.get("/v1/rig/search?q=Core", headers={"X-Rig-Key": key,
            "Origin": "https://customnation.co.za"})
        assert allowed.status_code == 200
        assert allowed.headers["Access-Control-Allow-Origin"] == "https://customnation.co.za"
        assert client.post("/v1/rig/admin/embed-keys", headers=admin,
            json={"origins": ["https://*.example.com"]}).status_code == 422
        assert client.post("/v1/rig/admin/embed-keys", headers=admin,
            json={"origins": ["https://["]}).status_code == 422
        assert client.post("/v1/rig/link-quote", headers=headers,
            json={"url": "https://[", "contact": CONTACT}).status_code == 422


@pytest.mark.asyncio
async def test_delivery_backoff_stops_and_only_explicit_resume_reopens_budget():
    now = [1000.0]
    rig = await service(RetailerHandoff(None))
    rig.quote_store.clock = lambda: now[0]
    ack = await rig.quote(TENANT, {"product_id": "CORE-1", "contact": CONTACT})
    qid = ack["request_id"]
    for attempt in range(1, 6):
        state = await rig.quote_store.status(TENANT, qid)
        assert state["attempts"] == attempt
        assert not await rig.quote_store.pending(TENANT)
        now[0] += 300 * 2 ** (attempt - 1)
        assert await rig.quote_store.pending(TENANT) == [qid]
        await rig.retry_pending(TENANT)
    state = await rig.quote_store.status(TENANT, qid)
    assert state == {"status": "needs_person", "error": "not_configured", "attempts": 6, "next_attempt_at": None}
    await rig.quote_store.retry_now(TENANT, qid)
    now[0] += 86400
    await rig.retry_pending(TENANT)
    assert (await rig.quote_store.status(TENANT, qid))["attempts"] == 6
    await rig.quote_store.retry_now(OTHER, qid, resume=True)
    assert not await rig.quote_store.pending(TENANT)
    await rig.quote_store.retry_now(TENANT, qid, resume=True)
    rig.handoff = RecordingHandoff()
    await rig.retry_pending(TENANT)
    assert (await rig.quote_store.status(TENANT, qid))["status"] == "sent"
    assert len(rig.handoff.sent) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [16, 17, 18, 19])
async def test_odoo_version_guard_precedes_all_mutations(version):
    stub = OdooStub()
    stub.version = version
    async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
        rig = await service(adapter(http))
        ack = await rig.quote(TENANT, {"product_id": "CORE-1", "contact": CONTACT})
    if version == 19:
        assert not stub.calls and not stub.orders
        assert (await rig.quote_store.status(TENANT, ack["request_id"]))["error"] == "odoo_version_unsupported"
    else:
        assert ack["delivery"] == "sent" and len(stub.orders) == 1


@pytest.mark.asyncio
async def test_sample_has_three_distinct_approved_tiers():
    rig = await service()
    setups = (await rig.setups(TENANT, "CORE-1"))["setups"]
    assert [s["total"]["amount"] for s in setups] == [120, 130, 160]
    assert setups[1]["badge"] == "Most chosen"
    assert all("PART-DRAFT" not in [part["product"]["id"] for part in s["parts"]] for s in setups)
