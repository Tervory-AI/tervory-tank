"""Synthetic provider protocol samples; these are not captured real responses."""

import asyncio
import importlib.util
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("context_adapter", ROOT / "agents/base/sources/context_dev.py")
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)
TENANT = "00000000-0000-0000-0000-000000000001"
RUN = "00000000-0000-0000-0000-000000000002"


@pytest.mark.parametrize("value", [
    "http://localhost", "http://127.0.0.1", "http://[::1]", "https://user:pass@example.com",
    "https://example.com?token=private", "https://example.com#private", "http://service.internal",
])
def test_rejects_private_or_sensitive_urls(value):
    with pytest.raises(ValueError):
        adapter.lookup_body(url=value)


def test_only_identity_is_sent():
    assert adapter.lookup_body(url="https://www.example.com/customer/private") == {
        "type": "by_domain", "domain": "example.com",
    }
    with pytest.raises(TypeError):
        adapter.lookup_body(email="someone@example.com")


def test_budget_and_ledger(monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "synthetic-test-value")
    monkeypatch.setenv("CONTEXT_DEV_MAX_CREDITS", "20")
    ledger = AsyncMock()
    ledger.reserve.return_value = "reservation"
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"X-Credits-Used": "10"}, json={
            "status": "ok", "brand": {"title": "Example", "domain": "example.com", "people": ["excluded"]},
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = adapter.ContextDev(http, ledger, tenant_id=TENANT, run_id=RUN)
            results = await asyncio.gather(*(client.lookup(name="Example") for _ in range(4)))
            assert [row["status"] for row in results] == ["candidate", "candidate", "credit_limit", "credit_limit"]
            assert results[0]["fields"] == {"name": "Example", "website": "https://example.com"}
    asyncio.run(run())
    assert len(requests) == 2
    assert ledger.reserve.await_count == ledger.settle.await_count == 2
    assert ledger.settle.call_args.args[1]["task_type"] == "base.context_dev"
    assert ledger.settle.call_args.args[1]["credits"] == 10


@pytest.mark.parametrize("failure", ["missing_credits", "timeout", "redirect", "malformed"])
def test_unknown_cost_stops_and_is_settled(monkeypatch, failure):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "synthetic-test-value")
    ledger = AsyncMock()

    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("not logged", request=request)
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://elsewhere.example"})
        if failure == "malformed":
            return httpx.Response(200, content="not JSON")
        return httpx.Response(200, json={"status": "ok", "brand": {}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = adapter.ContextDev(http, ledger, tenant_id=TENANT, run_id=RUN)
            assert (await client.lookup(name="Example"))["credits"] is None
            assert (await client.lookup(name="Example"))["status"] == "credit_limit"
    asyncio.run(run())
    assert ledger.settle.await_count == 1


def test_no_ledger_means_no_network(monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "synthetic-test-value")
    http = AsyncMock()
    client = adapter.ContextDev(http, None, tenant_id=TENANT, run_id=RUN)
    assert asyncio.run(client.lookup(name="Example"))["status"] == "ledger_unavailable"
    http.post.assert_not_called()


def test_reservation_failure_means_no_network(monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "synthetic-test-value")
    http, ledger = AsyncMock(), AsyncMock()
    ledger.reserve.side_effect = RuntimeError("ledger offline")
    client = adapter.ContextDev(http, ledger, tenant_id=TENANT, run_id=RUN)
    with pytest.raises(RuntimeError):
        asyncio.run(client.lookup(name="Example"))
    http.post.assert_not_called()


def test_candidate_storage_scopes_and_preserves_serving_profile():
    sys.path.insert(0, str(ROOT / "agents/base"))
    from sources.trial import store_trial_candidate

    @asynccontextmanager
    async def transaction():
        yield

    client = AsyncMock()
    client.tenant_id, client.run_id = TENANT, RUN
    client.lookup.return_value = {"status": "candidate", "fields": {"name": "Example"}, "credits": 10}
    conn = AsyncMock()
    conn.transaction = transaction
    conn.fetchrow.return_value = {"passes": {}}
    asyncio.run(store_trial_candidate(conn, client, RUN, {"name": "Example", "email": "excluded"}))
    client.lookup.assert_awaited_once_with(name="Example")
    sql, *params = conn.execute.call_args.args
    assert "tenant_id=$1 AND task_id=$2 AND id=$3" in sql
    assert "profile=" not in sql
    assert str(params[0]) == TENANT
    conn.fetchrow.return_value = None
    with pytest.raises(ValueError):
        asyncio.run(store_trial_candidate(conn, client, RUN, {"name": "Example"}))
    assert client.lookup.await_count == 1
