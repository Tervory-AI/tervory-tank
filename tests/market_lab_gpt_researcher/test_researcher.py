"""Real pinned GPT-Researcher + real Tank route/ledger SQL; offline I/O only.

Run in the isolated researcher environment (see PR.md). The main Tank image
does not install this service's heavy dependencies.
"""
import asyncio
import json
import socket
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

pytest.importorskip("gpt_researcher")
from fastapi import FastAPI
from researcher import app as service
from researcher import sources

TENANT_A = "00000000-0000-0000-0000-0000000000aa"
TENANT_B = "00000000-0000-0000-0000-0000000000bb"
URL_A = "https://www.bls.gov/news.release/empsit.nr0.htm"
URL_B = "https://www.uspto.gov/dashboard/patents/production-unexamined-filing.html"
TEXT_A = "Employment rose by 120,000 in the recorded month."
TEXT_B = "Patent applications increased by 4 percent in the recorded year."
HEADERS = {"X-Tank-Key": "offline-room"}


@pytest.fixture
def stack(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/unused")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "offline-model")
    monkeypatch.setenv("TANK_API_KEY", "offline-workspace")
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", "offline-room")
    monkeypatch.setenv("TANK_KEY", "offline-room")
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    import main as tank
    policy = {"model": "offline-model", "priority": "standard", "rung": 1,
              "system_prompt": "Answer with source evidence", "max_tokens_out": 2048,
              "cache_scope": "none", "candidate_model": None, "shadow_rate": 0}
    conn = SimpleNamespace(execute=AsyncMock(), fetchval=AsyncMock(return_value=False),
                           fetch=AsyncMock(return_value=[]))

    @asynccontextmanager
    async def acquire():
        yield conn

    conn.transaction = acquire
    monkeypatch.setattr(tank, "pool", lambda: SimpleNamespace(acquire=acquire))
    monkeypatch.setattr(tank, "load_policy", AsyncMock(return_value=policy))
    monkeypatch.setattr(tank, "_redis", None)
    monkeypatch.setattr(tank, "_pool", None)
    monkeypatch.setattr(tank, "TANK_API_KEY", "offline-workspace")
    calls, searches, pages, routed = [], [], [], []
    flags = {"wrong_url": False, "bad_quote": False, "model_failure": False, "empty": False}

    def provider(request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        calls.append(body)
        prompt = "\n".join(m["content"] for m in body["messages"])
        assert "<html" not in prompt and "<script" not in prompt
        if flags["model_failure"]:
            return httpx.Response(503, json={"error": "offline provider unavailable"})
        patent = "patent" in prompt.lower()
        url, text = (URL_B, TEXT_B) if patent else (URL_A, TEXT_A)
        if "Return ONLY JSON" in prompt:
            content = json.dumps({"claims": [{"text": text,
                "url": "https://example.org/invented" if flags["wrong_url"] else url,
                "quote": "A fabricated supporting quote" if flags["bad_quote"] else text}]})
        else:
            content = json.dumps(["patent applications" if patent else "employment growth"])
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 40}},
            headers={"x-litellm-response-cost": "0.004", "x-litellm-model-group": "offline-model"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(tank, "httpx", SimpleNamespace(
        AsyncClient=lambda **kw: real_client(transport=httpx.MockTransport(provider), **kw),
        HTTPError=httpx.HTTPError))
    tank_app = tank.app

    class TankTransport(httpx.ASGITransport):
        async def handle_async_request(self, request):
            assert request.url.host == "tank" and request.url.path == "/v1/route"
            routed.append(json.loads(request.content))
            return await super().handle_async_request(request)

    app = service.create_app()
    app.state.tank_transport = TankTransport(app=tank_app)
    app.state.model_transport = httpx.ASGITransport(app=app)

    def public_dns(host, *args, **kwargs):
        if host in {"www.bls.gov", "www.uspto.gov", "example.org"}:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", public_dns)

    def offline_get(url, **kwargs):
        import requests
        response = requests.Response()
        response.status_code = 200
        response.url = url
        if url == sources.SEARX_URL:
            assert kwargs["allow_redirects"] is False
            searches.append(kwargs["params"]["q"])
            url_found = URL_B if "patent" in searches[-1].lower() else URL_A
            data = [] if flags["empty"] else [{"url": url_found, "content": "Search snippet"}]
            response._content = json.dumps({"results": data}).encode()
            response.headers["Content-Type"] = "application/json"
        else:
            assert url in {URL_A, URL_B}, "unapproved outbound request"
            assert kwargs["headers"]["User-Agent"] == sources.USER_AGENT
            assert kwargs["allow_redirects"] is False
            pages.append(url)
            response.headers["Content-Type"] = "text/html"
            text = TEXT_A if url == URL_A else TEXT_B
            response._content = f"<html><head><title>Recorded public source</title></head><body><p>{text}</p></body></html>".encode()
        response._content_consumed = True
        return response

    monkeypatch.setattr(sources.requests, "get", offline_get)
    # Any SDK, embeddings, alternate search or telemetry connection fails the test.
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline test attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    return SimpleNamespace(app=app, tank=tank, tank_app=tank_app, conn=conn, calls=calls,
                           searches=searches, pages=pages, flags=flags, routed=routed, policy=policy)


async def ask(stack, tenant=TENANT_A, question="How is employment changing?"):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=stack.app), base_url="http://research") as client:
        return await client.post("/research", headers=HEADERS,
            json={"tenant_id": tenant, "question": question, "home_region": "us-east"})


def ledger_rows(stack):
    return [call.args for call in stack.conn.execute.call_args_list if "INSERT INTO tank.ledger" in call.args[0]]


@pytest.mark.asyncio
async def test_real_researcher_cites_fetched_search_page_and_tank_ledgers_every_call(stack, capsys):
    response = await ask(stack)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["facts"]) == 1 and result["facts"][0]["href"] == URL_A
    assert TEXT_A in result["facts"][0]["text"]
    assert result["facts"][0]["fetched_at"] in result["facts"][0]["text"]
    assert datetime.fromisoformat(result["facts"][0]["fetched_at"]).tzinfo is not None
    assert stack.pages == [URL_A] and stack.searches
    rows = ledger_rows(stack)
    assert len(rows) == len(stack.calls) == len(stack.routed) == len(result["receipts"]) == 2
    assert {str(row[1]) for row in rows} == {r["ledger_id"] for r in result["receipts"]}
    assert all(row[2] == UUID(TENANT_A) and row[4] == "market_lab" for row in rows)
    assert all(row[6] == "market.research" and row[12] == .004 for row in rows)
    assert result["cost_usd"] == .008
    assert not stack.app.state.runs
    output = capsys.readouterr()
    assert TEXT_A not in output.out + output.err
    assert "How is employment changing?" not in output.out + output.err


@pytest.mark.asyncio
async def test_concurrent_tenants_never_share_context_results_or_receipts(stack):
    first, second = await asyncio.gather(ask(stack), ask(stack, TENANT_B, "How are patent applications changing?"))
    assert first.status_code == second.status_code == 200
    a, b = first.json(), second.json()
    assert URL_B not in json.dumps(a) and URL_A not in json.dumps(b)
    for result, tenant in ((a, TENANT_A), (b, TENANT_B)):
        ids = {r["ledger_id"] for r in result["receipts"]}
        assert ids == {str(row[1]) for row in ledger_rows(stack) if row[2] == UUID(tenant)}
    assert len(ledger_rows(stack)) == 4 and not stack.app.state.runs


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["wrong_url", "bad_quote"])
async def test_unfetched_urls_and_invented_source_quotes_are_rejected(stack, defect):
    stack.flags[defect] = True
    response = await ask(stack)
    assert response.status_code == 503
    assert "facts" not in response.json() and not stack.app.state.runs


@pytest.mark.asyncio
async def test_empty_search_makes_no_model_call(stack):
    stack.flags["empty"] = True
    response = await ask(stack)
    assert response.status_code == 200 and response.json()["facts"] == []
    assert not stack.calls and not ledger_rows(stack)


@pytest.mark.asyncio
async def test_upstream_model_endpoint_override_cannot_send_the_key_or_prompt_elsewhere(stack, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.org/unapproved")
    response = await asyncio.wait_for(ask(stack), timeout=10)
    assert response.status_code == 503 and not stack.routed and not stack.calls
    assert not stack.app.state.runs


@pytest.mark.asyncio
async def test_provider_failure_is_ledgered_once_and_cancels_upstream_retries(stack):
    stack.flags["model_failure"] = True
    response = await asyncio.wait_for(ask(stack), timeout=10)
    assert response.status_code == 503
    assert len(stack.calls) == len(ledger_rows(stack)) == 1
    assert not stack.app.state.runs


@pytest.mark.asyncio
async def test_paid_pause_stops_before_provider(stack, monkeypatch):
    from fastapi import HTTPException
    import controls
    async def paused(**kwargs):
        raise HTTPException(503, "paid work is paused")
    monkeypatch.setattr(controls, "refuse_paid", paused)
    assert (await asyncio.wait_for(ask(stack), 10)).status_code == 503
    assert not stack.calls


@pytest.mark.asyncio
async def test_real_tank_ask_corridor_reaches_room_researcher_and_model_route(stack, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agents/market_lab"))
    from core.http import build_router
    from core.ledger import MemoryLedger
    from core import research_adapter
    active = []
    @asynccontextmanager
    async def ledger_context():
        active.append(True)
        try:
            yield MemoryLedger()
        finally:
            active.pop()

    room = FastAPI()
    room.include_router(build_router(key_ok=lambda key: key == "offline-room", ledger_context=ledger_context))
    destinations = {"tank": stack.tank_app, "agent-market-lab": room, "market-research": stack.app}
    hops = []
    async def dispatch(request):
        assert not active, "Database connection held during web research"
        hops.append((request.url.host, request.url.path))
        return await httpx.ASGITransport(app=destinations[request.url.host]).handle_async_request(request)

    client_type = httpx.AsyncClient
    monkeypatch.setattr(research_adapter, "httpx", SimpleNamespace(
        AsyncClient=lambda **kwargs: client_type(transport=httpx.MockTransport(dispatch), **kwargs)))
    async with client_type(transport=httpx.MockTransport(dispatch)) as corridor:
        monkeypatch.setattr(stack.tank, "_http", corridor)
        async with client_type(transport=httpx.ASGITransport(app=stack.tank_app), base_url="http://tank:8000") as client:
            response = await client.post("/v1/market-lab/ask", headers={"X-Tank-Key": "offline-workspace"},
                json={"tenant_id": TENANT_A, "question": "How is employment changing?"})
            assert response.status_code == 200, response.text
            assert response.json()["facts"][0]["href"] == URL_A
            assert response.headers["cache-control"] == "private, no-store"
            for key in ("", "offline-workspace", "another-room"):
                denied = await client.post("/v1/market-lab/internal/research", headers={"X-Tank-Key": key},
                    json={"tenant_id": TENANT_A, "question": "q", "home_region": "us-east"})
                assert denied.status_code == 401
            denied = await client.post("/v1/market-lab/internal/research", headers=HEADERS,
                json={"tenant_id": TENANT_A, "question": "q", "home_region": "eu"})
            assert denied.status_code == 403
    assert hops == [("agent-market-lab", "/market/ask"), ("tank", "/v1/market-lab/internal/research"),
                    ("market-research", "/research")]
    assert len(ledger_rows(stack)) == 2
    print(json.dumps({"path": hops, "answer": response.json(),
                      "ledger_rows": len(ledger_rows(stack)), "live_model_calls": 0}))


@pytest.mark.asyncio
async def test_tank_cache_is_used_and_each_cached_call_has_its_own_tenant_ledger(stack, monkeypatch):
    stack.policy["cache_scope"] = "tenant"
    transcripts, cached = {}, {}
    record = stack.conn.execute
    async def execute(sql, *args):
        await record(sql, *args)
        if "INSERT INTO tank.transcripts" in sql:
            transcripts[args[0]] = args[-1]
        if "INSERT INTO tank.route_cache" in sql:
            cached[tuple(args[:5])] = {"input_hash": args[4], "content": transcripts[args[7]]}
    async def fetch(sql, *args):
        if "FROM tank.route_cache" in sql:
            hit = cached.get(tuple(args[:5]))
            return [hit] if hit else []
        return []
    monkeypatch.setattr(stack.conn, "execute", execute)
    monkeypatch.setattr(stack.conn, "fetch", fetch)
    first, second = await ask(stack), await ask(stack)
    assert first.status_code == second.status_code == 200
    assert len(stack.calls) == 2 and second.json()["cost_usd"] == 0
    assert len([c for c in record.call_args_list if "INSERT INTO tank.ledger" in c.args[0]]) == 4
    assert {r["ledger_id"] for r in first.json()["receipts"]}.isdisjoint(
        {r["ledger_id"] for r in second.json()["receipts"]})
    third = await ask(stack, TENANT_B)
    assert third.status_code == 200 and len(stack.calls) == 4
    assert third.json()["cost_usd"] == .008


@pytest.mark.asyncio
async def test_service_and_completion_require_room_key_and_active_run(stack):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=stack.app), base_url="http://research") as client:
        assert (await client.post("/research", json={"tenant_id": TENANT_A, "question": "q", "home_region": "us-east"})).status_code == 401
        assert (await client.post("/model/v1/chat/completions", headers={"Authorization": "Bearer offline-room", "X-Research-Run": TENANT_A}, json={})).status_code == 401
        assert (await client.get("/research")).status_code == 405
        assert (await client.get("/research/" + TENANT_B)).status_code == 404
    assert not stack.calls


@pytest.mark.asyncio
async def test_model_payload_cannot_change_tenant_policy_or_endpoint(stack):
    run = service.Run(service.ResearchRequest(tenant_id=TENANT_A, question="employment", home_region="us-east"))
    stack.app.state.runs["active-offline-run"] = run
    stack.policy["max_tokens_out"] = 32
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=stack.app), base_url="http://research") as client:
        response = await client.post("/model/v1/chat/completions",
            headers={"Authorization": "Bearer offline-room", "X-Research-Run": "active-offline-run"},
            json={"model": "unapproved", "tenant_id": TENANT_B, "max_tokens": 999999,
                  "base_url": "https://example.org/model", "messages": [{"role": "user", "content": "employment"}]})
    assert response.status_code == 200
    assert stack.routed[0]["tenant_id"] == TENANT_A
    assert stack.routed[0]["task_type"] == "market.research"
    assert stack.calls[0]["model"] == "offline-model" and stack.calls[0]["max_tokens"] == 32
    assert ledger_rows(stack)[0][2] == UUID(TENANT_A)


@pytest.mark.parametrize("status,body", [(403, b"denied"), (429, b"limited"),
    (200, b"<html>Verify you are human</html>")])
def test_blocked_pages_stop_the_host_without_retry_or_evidence(stack, monkeypatch, status, body):
    import requests
    calls = []
    def blocked(url, **kwargs):
        calls.append(url)
        response = requests.Response()
        response.status_code = status
        response._content = body
        response._content_consumed = True
        response.headers["Content-Type"] = "text/html"
        return response
    monkeypatch.setattr(sources.requests, "get", blocked)
    registry = sources.Sources()
    sibling = "https://www.bls.gov/another"
    registry.allowed.update((URL_A, sibling))
    assert registry._page(URL_A) is None
    assert registry._page(URL_A) is None
    assert registry._page(sibling) is None
    assert calls == [URL_A] and not registry.pages


def test_search_and_page_redirects_never_follow_another_destination(stack, monkeypatch):
    import requests
    calls = []
    def redirect(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        calls.append(url)
        response = requests.Response()
        response.status_code = 302
        response.headers["Location"] = "http://tank:8000/health"
        response._content = b""
        response._content_consumed = True
        return response
    monkeypatch.setattr(sources.requests, "get", redirect)
    with pytest.raises(requests.RequestException):
        sources.search_get(sources.SEARX_URL)
    registry = sources.Sources()
    registry.allowed.add(URL_A)
    assert registry._page(URL_A) is None and not registry.pages
    assert calls == [sources.SEARX_URL, URL_A]


def test_private_sources_never_reach_page_transport(stack):
    for url in ("http://127.0.0.1/secrets", "http://tank:8000/health", "file:///etc/passwd",
                "https://user:password@www.bls.gov/", "https://www.bls.gov:9000/"):
        with pytest.raises(ValueError):
            sources.public_url(url)
    assert not stack.pages
