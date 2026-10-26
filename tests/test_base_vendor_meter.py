"""Offline HTTP receipts: real hooks, an explicit fixture ledger, no paid calls."""
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
import uuid

import httpx
import pytest

import controls
import vendor_meter as meter
from base_metrics import cost_rows
from base_product_fixtures import AT, TENANT, raw, finished
from engines.ffl.reference import project


class Ledger:
    def __init__(self):
        self.rows = {}
        self.quotes = {}
        self.links = []

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def fetchrow(self, sql, *args):
        assert "FROM tank.price_book" in sql
        assert args[0] == meter.PLATFORM
        return self.quotes.get(args[1])

    async def execute(self, sql, *args):
        if "INSERT INTO tank.ledger" in sql:
            identity, tenant, region, agent, skill, task, task_id, model, vendor, rate, quote = args
            self.rows[identity] = dict(id=identity, tenant_id=tenant, region=region, agent=agent, skill=skill,
                task_type=task, task_id=task_id, model=model, vendor=vendor, units=1, rung=1,
                cost_usd=Decimal(0), cost_status="not_set", vendor_unit_price=rate, vendor_price_id=quote,
                vendor_cost_status="pending", outcome="unverified", ts=AT)
        elif "INSERT INTO tank.base_ledger_links" in sql:
            tenant, record, identity = args
            assert self.rows[identity]["tenant_id"] == tenant
            self.rows[identity]["record_id"] = record
            self.links.append((tenant, record, identity))
        elif "UPDATE tank.ledger" in sql:
            identity, tenant, outcome, billed = args
            row = self.rows[identity]
            assert row["tenant_id"] == tenant
            if row["vendor_cost_status"] != "pending":
                return
            row.update(outcome=outcome, cost_usd=row["vendor_unit_price"] or Decimal(0) if billed else Decimal(0),
                cost_status="not_set" if billed and row["vendor_unit_price"] is None else "set",
                vendor_cost_status="not_billed" if not billed else "unpriced" if row["vendor_unit_price"] is None else "priced")
        else:
            raise AssertionError(sql)


@pytest.fixture
def book(monkeypatch):
    ledger = Ledger()
    monkeypatch.setattr(meter, "runtime", lambda: SimpleNamespace(pool=lambda: ledger))
    return ledger


@pytest.mark.asyncio
@pytest.mark.parametrize("url,code,vendor", [
    ("https://api.search.brave.com/res/v1/web/search", "brave.search.query", "brave.search"),
    ("https://places.googleapis.com/v1/places:searchText", "google.places.request", "google.places"),
    ("https://maps.googleapis.com/maps/api/place/textsearch/json", "google.places.request", "google.places"),
])
async def test_paid_calls_snapshot_prices_once_without_backfilling_history(book, url, code, vendor):
    row = finished(project(raw()))
    token = meter.current.set(meter.Run(TENANT, "us-east", "base", "base.find_site@1", None, row["id"]))
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"status": "OK"})),
                                     event_hooks={"request": [meter.request_hook], "response": [meter.response_hook]}) as client:
            first_response = await client.get(url)
            await meter.response_hook(first_response)  # duplicate notification never books twice
            first = next(iter(book.rows.values()))
            assert first["vendor"] == vendor and first["cost_usd"] == 0 and first["cost_status"] == "not_set"
            amount = cost_rows([row], list(book.rows.values()))[0]
            assert amount["status"] == "price not set" and amount["cost_usd"] is None
            assert amount["known_cost_usd"] == "0"
            book.quotes[code] = {"id": uuid.uuid4(), "unit_price": Decimal("0.000792"), "price_status": "set", "free_pass": False}
            await client.get(url)
            assert len(book.rows) == 2
            second = list(book.rows.values())[1]
            assert second["cost_usd"] == Decimal("0.000792") and second["cost_status"] == "set"
            assert first["cost_status"] == "not_set" and first["vendor_unit_price"] is None
            assert cost_rows([row], list(book.rows.values()))[0]["known_cost_usd"] == "0.000792"
    finally:
        meter.current.reset(token)


@pytest.mark.asyncio
async def test_pause_books_nothing_and_nonpaid_hosts_are_untouched(book, monkeypatch):
    async def paused():
        return True
    monkeypatch.setattr(controls, "paid_paused", paused)
    monkeypatch.setattr(controls, "db", lambda: book)
    seen = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: seen.append(req) or httpx.Response(200)),
                                 event_hooks={"request": [controls.paid_host_hook], "response": [controls.paid_response_hook]}) as client:
        with pytest.raises(Exception, match="paid work is paused"):
            await client.get("https://api.search.brave.com/res/v1/web/search")
        assert not book.rows and not seen
        await client.get("https://public.example/shop")
        assert len(seen) == 1 and not book.rows


@pytest.mark.asyncio
async def test_transport_failure_preserves_unknown_receipt_and_http_error_not_billed(book):
    token = meter.current.set(meter.Run(TENANT, "us-east", "base", "base.find_site", None, uuid.uuid4()))
    try:
        request = httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search")
        await meter.request_hook(request)
        assert next(iter(book.rows.values()))["cost_status"] == "not_set"
        await meter.response_hook(httpx.Response(429, request=request))
        assert next(iter(book.rows.values()))["cost_status"] == "set"
        assert next(iter(book.rows.values()))["vendor_cost_status"] == "not_billed"
        assert next(iter(book.rows.values()))["outcome"] == "failed"
    finally:
        meter.current.reset(token)


def test_paid_http_log_omits_queries_and_credentials():
    import logging
    row = logging.LogRecord("httpx", logging.INFO, __file__, 1, "HTTP Request: %s %s", (
        "GET", httpx.URL("https://api.search.brave.com/res/v1/web/search?q=fixture-business")), None)
    assert meter.SafeHTTPLog().filter(row)
    assert "fixture-business" not in row.getMessage() and "?" not in row.getMessage()
