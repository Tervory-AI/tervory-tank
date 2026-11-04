"""RIG-4: store delivery HTTP contracts, no external requests."""

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
from fixtures.rig_quote_sample import KEY, TENANT, seed  # noqa: E402
from rigbox.quotes.senders import DeliveryError, RetailerHandoff  # noqa: E402
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
async def test_attention_pages_past_100_and_only_resumed_holds_count():
    rig = await service()
    rig.quote_store.clock = lambda: 120  # Equal timestamps exercise the ID tie-breaker.
    await rig.store.put_key(TENANT, hash_key("RIG_ADMIN_KEY"), "admin", [])
    await rig.store.put_key(OTHER, hash_key("OTHER_RIG_ADMIN_KEY"), "admin", [])
    await rig.quote(TENANT, {"product_id": "CORE-1", "contact": CONTACT})
    for index in range(205):
        await rig.quote_store.create(TENANT, {"id": f"held_{index:03}", "payload": {}, "contact": {}}, hold=True)
    await rig.quote_store.create(OTHER, {"id": "other_held", "payload": {}, "contact": {}}, hold=True)
    assert (await rig.quote_store.analytics(TENANT, date.min))["quotes"] == 1
    app = FastAPI()
    app.state.rig = rig
    mount(app)
    mount_quotes(app)
    headers = {"X-Rig-Key": "RIG_ADMIN_KEY"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.get("/v1/rig/admin/quotes/attention", headers=headers)).json()
        assert len(first["requests"]) == 100 and first["next_cursor"]
        ids = [row["request_id"] for row in first["requests"]]
        # Removing an earlier entry while paging must not skip later entries.
        for _ in range(2):
            assert (await client.post("/v1/rig/admin/quotes/held_000/resume", headers=headers)).status_code == 200
        assert (await rig.quote_store.analytics(TENANT, date.min))["quotes"] == 2
        cursor = first["next_cursor"]
        while cursor:
            response = await client.get("/v1/rig/admin/quotes/attention", params={"cursor": cursor}, headers=headers)
            assert response.status_code == 200
            page = response.json()
            ids.extend(row["request_id"] for row in page["requests"])
            cursor = page["next_cursor"]
        assert ids == [f"held_{index:03}" for index in range(205)]
        other = (await client.get("/v1/rig/admin/quotes/attention", headers={"X-Rig-Key": "OTHER_RIG_ADMIN_KEY"})).json()
        assert [row["request_id"] for row in other["requests"]] == ["other_held"]
        for params in ({"limit": 0}, {"limit": 101}, {"cursor": "not-a-cursor"}, {"cursor": "W10"}):
            assert (await client.get("/v1/rig/admin/quotes/attention", params=params, headers=headers)).status_code == 422
        assert (await client.get("/v1/rig/admin/quotes/attention", headers={"X-Rig-Key": KEY})).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("field,limit", [("name", 120), ("email", 254), ("phone", 40)])
async def test_contact_length_caps_prevent_storage_and_delivery(field, limit):
    rig = await service()
    with pytest.raises(RigError) as error:
        await rig.quote(TENANT, {"product_id": "CORE-1", "contact": {**CONTACT, field: "a" * (limit + 1)}})
    assert error.value.status == 422
    assert not await rig.store.quotes_for(TENANT) and not rig.handoff.sent


@pytest.mark.asyncio
async def test_controls_are_removed_before_storage_and_handoff():
    rig = await service()
    contact = {"name": "Sam\x00ple\u202e", "email": "shopper\r\n@example.com", "phone": "12\x003"}
    await rig.link_quote(TENANT, "https://example.com/item", "Please\x00 source\r\n this\u202e", contact)
    stored = (await rig.store.quotes_for(TENANT))[0]
    assert stored["contact"] == {"name": "Sample", "email": "shopper@example.com", "phone": "123"}
    assert stored["payload"]["note"] == "Please source this"
    assert rig.handoff.sent[0]["quote"]["contact"] == stored["contact"]
    with pytest.raises(RigError):
        await rig.link_quote(TENANT, "https://example.com/item", "a" * 4001, CONTACT)


@pytest.mark.asyncio
async def test_flow_is_exact_tenant_and_webhook_checks_http_status(monkeypatch):
    monkeypatch.setenv("RIG_QUOTE_FLOWS", json.dumps({TENANT: {"sender": "email"}}))
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
async def test_sample_has_three_distinct_approved_tiers():
    rig = await service()
    setups = (await rig.setups(TENANT, "CORE-1"))["setups"]
    assert [s["total"]["amount"] for s in setups] == [120, 130, 160]
    assert setups[1]["badge"] == "Most chosen"
    assert all("PART-DRAFT" not in [part["product"]["id"] for part in s["parts"]] for s in setups)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['product', 'setup', 'link'])
async def test_store_email_delivery_keeps_pending_retry_and_reference(monkeypatch, kind):
    """Email remains the store's quote handoff, including recovery after SMTP failure."""
    from rigbox.reserve import SmtpMailer

    letters = []
    class Mail:
        async def send(self, letter):
            letters.append(letter)
            if len(letters) == 1:
                raise RuntimeError('private SMTP diagnostic')
    monkeypatch.setenv('RIG_QUOTE_FLOWS', '')
    monkeypatch.setattr(SmtpMailer, 'from_env', lambda: Mail())
    rig = await service(RetailerHandoff(None))
    await rig.store.put_retailer(TENANT, 'email-store', 'store@example.com', None)
    if kind == 'link':
        ack = await rig.link_quote(TENANT, 'https://example.com/item', 'Please source this', CONTACT)
    elif kind == 'setup':
        built = (await rig.setups(TENANT, 'CORE-1'))['setups'][0]
        ack = await rig.quote(TENANT, {'setup': built, 'contact': CONTACT})
    else:
        ack = await rig.quote(TENANT, {'product_id': 'CORE-1', 'contact': CONTACT})
    qid = ack['request_id']
    assert ack['delivery'] == 'pending'
    state = await rig.quote_store.status(TENANT, qid)
    assert state['error'] == 'email_unavailable'
    assert (await rig.store.quotes_for(TENANT))[0]['sent_at'] is None
    await rig.quote_store.retry_now(TENANT, qid)
    await rig.retry_pending(TENANT)
    assert (await rig.quote_store.status(TENANT, qid))['status'] == 'sent'
    assert len(letters) == 2
    assert all(letter['to'] == 'store@example.com' for letter in letters)
    assert all(letter['reply_to'] == CONTACT['email'] for letter in letters)
    assert letters[0]['message_id'] == letters[1]['message_id'] == f'<{qid}@rig.tervory.com>'
    assert all(qid in letter['subject'] for letter in letters)
    if kind == 'link':
        assert all('https://example.com/item' in letter['text'] for letter in letters)
    assert len(await rig.store.quotes_for(TENANT)) == 1
