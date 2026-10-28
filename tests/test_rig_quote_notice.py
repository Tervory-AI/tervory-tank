"""Offline store notice isolation, exact receipts and prohibited fields."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from test_custom_nation_rig import store as notice_store  # noqa: F401 -- shared disposable DB fixture
from rigbox.api import LinkIn, QuoteIn
from rigbox.quotes.notice import notice
from rigbox.quotes.service import QuoteService
from rigbox.quotes.store import MemoryQuotes, PgQuotes
from rigbox.retailer import Retailer
from rigbox.service import RecordingHandoff, RigError, Service
from rigbox.store import PgStore


@pytest.mark.asyncio
async def test_notice_settings_receipts_and_tenant_isolation(notice_store):  # noqa: F811 -- pytest fixture
    store = notice_store
    a, b = str(uuid4()), str(uuid4())
    settings = Retailer(Service(store))
    original = {"text": "Offline notice <&> exactly.  ", "url": "https://shop.example.test/privacy"}
    await settings.set_settings(a, {"name": "Offline A", "email": "a@example.test", "quote_notice": original})
    await settings.set_settings(b, {"name": "Offline B", "email": "b@example.test"})
    # Legacy forms/imports omit notice fields and must preserve them.
    await settings.set_settings(a, {"name": "Offline A", "email": "a@example.test"})
    await store.put_retailer(a, "offline-a", "a@example.test", None, "Offline A")
    assert (await store.retailer(a))["quote_notice"] == original
    for invalid in (None, {}, {"text": "text", "url": "javascript:alert(1)"}):
        with pytest.raises(ValueError):
            await settings.set_settings(a, {"name": "Offline A", "email": "a@example.test", "quote_notice": invalid})
        assert (await store.retailer(a))["quote_notice"] == original
    if isinstance(store, PgStore):
        await store.apply_schema()
        store = PgStore(store.pool)
    sender = RecordingHandoff()
    quotes = PgQuotes(store.pool) if isinstance(store, PgStore) else MemoryQuotes(store)
    rig = QuoteService(store, None, sender, quotes)
    shown = await rig.privacy_notice(a)
    assert shown == notice(original)
    assert await rig.privacy_notice(b) is None
    for version in (None, "old-version"):
        with pytest.raises(RigError) as error:
            await rig.link_quote(a, "https://product.example.test/item", "", notice_version=version)
        assert error.value.status == 409
        assert await store.quotes_for(a) == []
    before = datetime.now(timezone.utc)
    ack = await rig.link_quote(a, "https://product.example.test/item", "", notice_version=shown["version"])
    rows = await store.quotes_for(a)
    evidence = rows[0]["payload"]["notice_receipt"]
    assert evidence.items() >= shown.items()
    assert before <= datetime.fromisoformat(evidence["submitted_at"]) <= datetime.now(timezone.utc)
    assert rows[0]["id"] == ack["request_id"]
    changed = {**original, "text": "Changed offline notice"}
    await Retailer(Service(store)).set_settings(a, {"name": "Offline A", "email": "a@example.test", "quote_notice": changed})
    assert (await rig.privacy_notice(a))["version"] != shown["version"]
    assert (await store.quotes_for(a))[0]["payload"]["notice_receipt"] == evidence
    with pytest.raises(RigError):
        await rig.link_quote(b, "https://product.example.test/item", "", notice_version=shown["version"])
    assert await store.quotes_for(b) == []


@pytest.mark.parametrize("field", ["card", "card_number", "bank_account", "id_number", "financial_details"])
@pytest.mark.asyncio
async def test_financial_fields_never_enter_quote_payload(notice_store, field):  # noqa: F811 -- pytest fixture
    store = notice_store
    tenant = str(uuid4())
    quotes = PgQuotes(store.pool) if isinstance(store, PgStore) else MemoryQuotes(store)
    rig = QuoteService(store, None, RecordingHandoff(), quotes)
    with pytest.raises(RigError):
        await rig.link_quote(tenant, "https://product.example.test/item", "", contact={field: "offline-rejected"})
    assert await store.quotes_for(tenant) == []
    for model in (LinkIn, QuoteIn):
        with pytest.raises(ValidationError):
            model.model_validate({field: "offline-rejected"})
