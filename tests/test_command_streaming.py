"""Real Tank command/router/SQL over local HTTP; only LiteLLM is stubbed.

The actual SDK consumes chunked SSE. No model, GitHub or other remote API calls.
"""
import asyncio
import json
import socket
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
import uvicorn
import yaml
from pathlib import Path

import command
import command_stream
import test_command as command_tests
from test_command import TENANT, OTHER

command_pool = command_tests.command_pool
TEXT = "Hello world.\nA 😀 answer."


class ModelStream(httpx.AsyncByteStream):
    def __init__(self, gateway):
        self.gateway = gateway

    async def __aiter__(self):
        g = self.gateway
        if g.mode == "early_usage":
            yield g.frame({"choices": [], "usage": {"prompt_tokens": 8, "completion_tokens": 0, "total_tokens": 8, "cost": 0}})
        for index, part in enumerate(g.parts):
            yield g.frame({"choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}]})
            if index == 0:
                g.paused.set()
                if g.gated:
                    await g.release.wait()
                if g.mode == "eof":
                    return
                if g.mode == "transport":
                    raise httpx.RemoteProtocolError("private upstream detail")
                if g.mode == "error":
                    yield b'data: {"error":{"message":"private upstream detail"}}\n\n'
                    return
        if g.mode != "no_finish":
            yield g.frame({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        if g.mode not in {"no_usage", "early_usage"}:
            usage = dict(g.usage)
            if g.mode == "no_cost":
                del usage["cost"]
            yield g.frame({"choices": [], "usage": usage})
        yield b'data: [DONE]\n\n'
        g.finished = True

    async def aclose(self):
        self.gateway.closed.set()


class Gateway:
    def __init__(self):
        self.parts = ['{"text":"Hello', ' world.\\nA ', '\\uD83D', '\\uDE00', ' answer.","actions":[]}']
        self.usage = {"prompt_tokens": 8, "completion_tokens": 13, "total_tokens": 21, "cost": 0.0024}
        self.mode = "ok"
        self.status = 200
        self.gated = False
        self.finished = False
        self.paused, self.release, self.closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        self.calls = []

    @staticmethod
    def frame(value):
        body = {"id": "offline-completion", "object": "chat.completion.chunk", "created": 1,
                "model": "fixture-provider", **value}
        return ("data: " + json.dumps(body) + "\n\n").encode()

    def request(self, request):
        assert str(request.url) == "http://litellm.internal/v1/chat/completions"
        assert request.method == "POST"
        body = json.loads(request.content)
        self.calls.append(body)
        headers = {"x-litellm-model-group": "fixture-answered"}
        if self.status != 200:
            return httpx.Response(self.status, headers={"location": "https://other.invalid/"}, json={"error": {"message": "private upstream detail"}})
        if body.get("stream"):
            assert body["stream_options"] == {"include_usage": True}
            return httpx.Response(200, headers={**headers, "content-type": "text/event-stream"}, stream=ModelStream(self))
        return httpx.Response(200, headers={**headers, "x-litellm-response-cost": str(self.usage["cost"])}, json={
            "choices": [{"message": {"content": "".join(self.parts)}, "finish_reason": "stop"}], "usage": self.usage})


@pytest_asyncio.fixture
async def streaming(monkeypatch, command_pool):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/unused")
    monkeypatch.setenv("TANK_API_KEY", "dummy-workspace-key")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "dummy-gateway-key")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder")
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    import main as tank
    monkeypatch.setattr(tank, "TANK_API_KEY", "dummy-workspace-key")
    monkeypatch.setattr(tank, "LITELLM_URL", "http://litellm.internal")
    monkeypatch.setattr(tank, "pool", lambda: command_pool)
    monkeypatch.setattr(tank, "_redis", None)
    policy = {"model": "fixture-auto", "priority": "standard", "rung": 1, "system_prompt": "",
              "max_tokens_out": 512, "cache_scope": "tenant", "semantic_cache": False,
              "candidate_model": None, "shadow_rate": 0, "acceptance_window_s": 86400}
    monkeypatch.setattr(tank, "load_policy", AsyncMock(return_value=policy))
    monkeypatch.setattr(tank, "list_models", AsyncMock(return_value=[{"name": "fixture-pin"}]))
    gateway = Gateway()
    original_client = httpx.AsyncClient

    def client(**kwargs):
        assert not kwargs.get("follow_redirects", False)
        return original_client(**kwargs, transport=httpx.MockTransport(gateway.request))

    # Keep the SDK's actual stream decoder and completion types. Only its HTTP
    # transport is replaced; all calls outside the local Tank server fail closed.
    transport = SimpleNamespace(AsyncClient=client, HTTPError=httpx.HTTPError, Response=httpx.Response)
    monkeypatch.setattr(command_stream, "httpx", transport)
    monkeypatch.setattr(tank, "httpx", transport)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(tank.app, log_level="error", lifespan="off"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started
    try:
        async with original_client(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False,
            headers={"X-Tank-Key": "dummy-workspace-key", "X-Tervory-User": "founder", "X-Tervory-Tenant": str(TENANT)}) as api:
            yield SimpleNamespace(api=api, tank=tank, pool=command_pool, gateway=gateway, policy=policy)
    finally:
        gateway.release.set()
        if command._background:
            await asyncio.gather(*command._background)
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        listener.close()


async def events(response):
    kind = None
    async for line in response.aiter_lines():
        if line.startswith("event: "):
            kind = line[7:]
        elif line.startswith("data: "):
            yield kind, json.loads(line[6:])


def answer(events):
    text = ""
    for kind, data in events:
        if kind == "token":
            text = ("" if data.get("replace") else text) + data["text"]
    return text


async def thread(b, **headers):
    response = await b.api.post("/v1/command/threads", json={}, headers=headers)
    assert response.status_code == 200
    return response.json()["thread_id"]


async def turn(b, thread_id, text="Hello", **kwargs):
    async with b.api.stream("POST", f"/v1/command/threads/{thread_id}/turn", json={"text": text, **kwargs}) as response:
        assert response.status_code == 200
        return [item async for item in events(response)]


@pytest.mark.asyncio
async def test_tokens_arrive_before_finish_then_exact_message_and_receipt(streaming):
    b = streaming
    b.gateway.gated = True
    tid = await thread(b)
    updates = []
    async with b.api.stream("POST", f"/v1/command/threads/{tid}/turn", json={"text": "Hello"}) as response:
        async with asyncio.timeout(5):
            async for item in events(response):
                updates.append(item)
                if item[0] == "token" and not b.gateway.release.is_set():
                    assert answer(updates) == "Hello" and not b.gateway.finished
                    state = (await b.api.get(f"/v1/command/threads/{tid}")).json()
                    assert [m["role"] for m in state["messages"]] == ["user"]
                    assert state["receipts"] == [] and state["cards"] == []
                    async with b.pool.acquire() as conn:
                        assert await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1", TENANT) == 0
                    b.gateway.release.set()
    assert answer(updates) == TEXT
    assert [d["seq"] for _, d in updates] == sorted({d["seq"] for _, d in updates})
    assert sum(kind == "token" for kind, _ in updates) >= 3
    assert updates[-1][0] == "done"
    assert "actions" not in answer(updates)
    state = (await b.api.get(f"/v1/command/threads/{tid}")).json()
    assert state["messages"][-1]["content"] == TEXT
    assert state["steps"][-1]["status"] == "done"
    receipt = next(data for kind, data in updates if kind == "receipt")["rows"][0]
    async with b.pool.acquire() as conn:
        ledger = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", uuid.UUID(receipt["ledger_id"]), TENANT)
        assert ledger["outcome"] == "delivered"
        assert (receipt["tokens_in"], receipt["tokens_out"], receipt["cost_usd"], receipt["model"]) == (8, 13, float(ledger["cost_usd"]), ledger["model"])
    assert receipt["cost_usd"] == 0.0024 and receipt["model"] == "fixture-answered"


@pytest.mark.asyncio
async def test_streamed_and_buffered_turn_accounting_match(streaming, monkeypatch):
    b = streaming
    b.policy["cache_scope"] = "none"
    streamed = await turn(b, await thread(b), model="fixture-pin")
    original = command.route_turn

    async def buffered(actor, messages, model=None, *, task_id=None, on_token=None):
        return await original(actor, messages, model=model, task_id=task_id)

    monkeypatch.setattr(command, "route_turn", buffered)
    buffered_events = await turn(b, await thread(b), model="fixture-pin")
    assert answer(streamed) == answer(buffered_events) == TEXT
    receipts = [next(data for kind, data in result if kind == "receipt")["rows"][0] for result in (streamed, buffered_events)]
    ignored = {"step_id", "ledger_id"}
    assert {k: v for k, v in receipts[0].items() if k not in ignored} == {k: v for k, v in receipts[1].items() if k not in ignored}
    async with b.pool.acquire() as conn:
        rows = await conn.fetch("SELECT model,rung,tokens_in,tokens_out,cost_usd,cache_hit,outcome,route_seat,escalation FROM tank.ledger WHERE tenant_id=$1 ORDER BY ts", TENANT)
        assert len(rows) == 2 and dict(rows[0]) == dict(rows[1])
        assert rows[0]["route_seat"] == "pinned"
    assert len(b.gateway.calls) == 2
    assert b.gateway.calls[0]["disable_fallbacks"] and b.gateway.calls[1]["disable_fallbacks"]


@pytest.mark.asyncio
async def test_cache_hit_whole_and_other_tenant_must_call_model(streaming):
    b = streaming
    tid = await thread(b)
    first = await turn(b, tid)
    second = await turn(b, tid)
    assert len(b.gateway.calls) == 1
    assert sum(kind == "token" for kind, _ in second) == 1
    assert answer(first) == answer(second) == TEXT
    receipt = next(data for kind, data in second if kind == "receipt")["rows"][0]
    assert receipt["cost_usd"] == 0
    headers = {"X-Tervory-Tenant": str(OTHER)}
    other = await thread(b, **headers)
    response = await b.api.post(f"/v1/command/threads/{other}/turn", json={"text": "Hello"}, headers=headers)
    assert "event: done" in response.text and len(b.gateway.calls) == 2
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.route_cache WHERE tenant_id=$1", OTHER) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["eof", "transport", "error", "no_finish", "no_usage", "no_cost", "early_usage"])
async def test_broken_stream_never_saved_complete_or_cached(streaming, mode):
    b = streaming
    b.gateway.mode = mode
    tid = await thread(b)
    updates = await turn(b, tid)
    assert any(kind == "token" for kind, _ in updates)
    assert updates[-1][0] == "error" and all(kind != "done" for kind, _ in updates)
    assert "private upstream" not in json.dumps(updates)
    state = (await b.api.get(f"/v1/command/threads/{tid}")).json()
    assert [m["role"] for m in state["messages"]] == ["user"]
    assert state["steps"][-1]["status"] == "failed" and state["cards"] == []
    async with b.pool.acquire() as conn:
        rows = await conn.fetch("SELECT outcome,cost_status FROM tank.ledger WHERE tenant_id=$1", TENANT)
        assert len(rows) == 1 and rows[0]["outcome"] == "failed"
        assert await conn.fetchval("SELECT count(*) FROM tank.route_cache") == 0
        assert await conn.fetchval("SELECT count(*) FROM tank.transcripts") == 0
        assert await conn.fetchval("SELECT status FROM tank.tasks WHERE tenant_id=$1", TENANT) == "failed"
    assert len(b.gateway.calls) == 1  # SDK cannot retry a partially charged answer.
    if mode != "no_finish":
        assert state["receipts"][0]["cost_usd"] is None
        assert state["thread"]["spent_usd"] is None


@pytest.mark.asyncio
async def test_disconnect_closes_upstream_and_fails_pending_turn(streaming):
    b = streaming
    b.gateway.gated = True
    tid = await thread(b)
    async with b.api.stream("POST", f"/v1/command/threads/{tid}/turn", json={"text": "Hello"}) as response:
        async for kind, data in events(response):
            if kind == "token":
                assert data["text"] == "Hello"
                break
    await asyncio.wait_for(b.gateway.closed.wait(), 3)
    async with asyncio.timeout(3):
        while True:
            state = (await b.api.get(f"/v1/command/threads/{tid}")).json()
            if state["steps"][-1]["status"] == "failed":
                break
            await asyncio.sleep(0.01)
    assert len(state["messages"]) == 1 and state["receipts"][0]["cost_usd"] is None
    assert not b.gateway.finished and len(b.gateway.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 429, 500])
async def test_gateway_errors_and_redirects_are_not_retried(streaming, status):
    b = streaming
    b.gateway.status = status
    tid = await thread(b)
    updates = await turn(b, tid)
    assert updates[-1][0] == "error" and all(kind not in {"token", "done"} for kind, _ in updates)
    assert "private upstream detail" not in json.dumps(updates)
    assert len(b.gateway.calls) == 1
    state = (await b.api.get(f"/v1/command/threads/{tid}")).json()
    assert len(state["messages"]) == 1 and state["receipts"][0]["cost_usd"] is None


@pytest.mark.asyncio
async def test_other_tenant_and_user_cannot_receive_live_or_replayed_events(streaming):
    b = streaming
    b.gateway.gated = True
    tid = await thread(b)
    async with b.api.stream("POST", f"/v1/command/threads/{tid}/turn", json={"text": "Hello"}) as response:
        async for kind, data in events(response):
            if kind == "token" and not b.gateway.release.is_set():
                for headers in ({"X-Tervory-Tenant": str(OTHER)}, {"X-Tervory-User": "client"}):
                    for suffix in ("", "/events"):
                        denied = await b.api.get(f"/v1/command/threads/{tid}{suffix}", headers=headers)
                        assert denied.status_code == 404 and "Hello" not in denied.text
                    denied = await b.api.post(f"/v1/command/threads/{tid}/turn", json={"text": "steal"}, headers=headers)
                    assert denied.status_code == 404
                b.gateway.release.set()
    assert len(b.gateway.calls) == 1
    assert (await b.api.get(f"/v1/command/threads/{tid}/events", headers={"X-Tervory-Tenant": str(OTHER)})).status_code == 404


@pytest.mark.asyncio
async def test_tools_remain_unexecuted_cards_after_complete_plan(streaming, monkeypatch):
    b = streaming
    monkeypatch.setenv("TANK_GITHUB_READ_TOKEN", "dummy-offline-setting")
    dispatch = AsyncMock(return_value=(200, {"count": 0}))
    monkeypatch.setattr(command, "dispatch_action", dispatch)
    b.gateway.parts = ['{"text":"Read', ' the brief.","actions":[{"tool":"repo.file","arguments":{"path":"AGENTS.md"}}]}']
    tid = await thread(b)
    updates = await turn(b, tid)
    assert answer(updates) == "Read the brief." and "AGENTS.md" not in answer(updates)
    card = next(data for kind, data in updates if kind == "card")
    assert card["status"] == "pending" and card["tool"] == "repo.file"
    dispatch.assert_not_awaited()
    assert any(kind == "step" and data["status"] == "planned" for kind, data in updates)
    assert (await b.api.post(f"/v1/command/cards/{card['card_id']}", json={"action": "cancel"})).status_code == 200
    dispatch.assert_not_awaited()


@pytest.mark.parametrize("text", [TEXT, "Plain text with {braces}", " leading whitespace", "A quote: \"x\" and \\ path"])
def test_text_preview_handles_every_split_without_json_or_escape_leaks(text):
    raw = json.dumps({"text": text, "actions": []}, ensure_ascii=True)
    for width in range(1, len(raw) + 1):
        preview = command_stream.AnswerText()
        shown = "".join(preview.feed(raw[index:index + width]) for index in range(0, len(raw), width))
        assert shown == text


def test_gateway_configs_enable_actual_streaming_cost():
    for file in ("litellm/config.yaml", "litellm/config.za.yaml"):
        assert yaml.safe_load(Path(file).read_text())["litellm_settings"]["include_cost_in_streaming_usage"] is True
