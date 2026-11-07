"""Offline signed-actor and durable replay tests; never use body identity."""
import asyncio
import time
import uuid
from types import SimpleNamespace

from fastapi import FastAPI, Request
import httpx
import pytest

from chassis.user_assertion import PostgresNonces, signed_user, verify_assertion
import product_identity as identity
from test_agent_memory_records import memory as memory_fixture

memory = memory_fixture
TENANT = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"
USER = identity.User(TENANT, "placeholder-user-a", "member")
KEY = "placeholder-product-key"


class PlaceholderNonces:
    def __init__(self):
        self.seen = set()
    async def claim(self, tenant, nonce, expires):
        key = (tenant, nonce)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


@pytest.mark.asyncio
async def test_signature_rejects_wrong_key_expiry_tenant_product_body_and_replay():
    body = b'{"user_id":"placeholder-attacker"}'
    token = identity.sign("trigger", USER, "POST", "/task", body, key=KEY, now=1000, nonce="placeholder-nonce-0001")
    async def verify(**changes):
        args = dict(key=KEY, product="trigger", tenant_id=TENANT, method="POST", target="/task", body=body,
                    consume_nonce=PlaceholderNonces().claim, now=1001)
        args.update(changes)
        return await verify_assertion(token, **args)
    assert (await verify()).user_id == "placeholder-user-a"
    for bad in ({"key": "placeholder-wrong-key"}, {"now": 1060}, {"now": 999}, {"tenant_id": OTHER},
                {"product": "tisan"}, {"method": "DELETE"}, {"target": "/memory"}, {"body": b"placeholder-tampered"}):
        with pytest.raises(PermissionError):
            await verify(**bad)
    nonces = PlaceholderNonces()
    await verify(consume_nonce=nonces.claim)
    with pytest.raises(PermissionError):
        await verify(consume_nonce=nonces.claim)
    async def unavailable(*args):
        raise OSError("placeholder store unavailable")
    with pytest.raises(PermissionError):
        await verify(consume_nonce=unavailable)


@pytest.mark.asyncio
async def test_two_workers_share_atomic_nonce_wall_after_restart(memory):
    m = memory
    before = await m.pool.fetchval("SHOW search_path")
    first, second = PostgresNonces(m.pool, m.agent), PostgresNonces(m.pool, m.agent)
    await first.setup()
    await second.setup()
    expiry = int(time.time()) + 60
    accepted = await asyncio.gather(first.claim(m.tenant, "placeholder-shared-nonce", expiry),
                                    second.claim(m.tenant, "placeholder-shared-nonce", expiry))
    assert sorted(accepted) == [False, True]
    restarted = PostgresNonces(m.pool, m.agent)
    assert not await restarted.claim(m.tenant, "placeholder-shared-nonce", expiry)
    assert not await restarted.claim(m.other, "placeholder-shared-nonce", expiry)
    assert await m.pool.fetchval("SHOW search_path") == before
    assert await m.pool.fetchval("SELECT to_regclass(quote_ident($1) || '.user_assertion_nonces') IS NOT NULL", first.schema)


@pytest.mark.asyncio
async def test_plain_task_runs_without_identity_memory_controls_refuse_and_body_user_ignored():
    app = FastAPI()
    nonces = PlaceholderNonces()
    memory_calls = []
    @app.post("/task")
    @app.post("/memory")
    async def task(request: Request):
        body = await request.json()
        actor = await signed_user(request, tenant_id=body["tenant_id"], product="trigger", key=KEY,
                                  nonces=nonces, required=request.url.path == "/memory")
        if actor is not None:
            memory_calls.append((actor.tenant_id, actor.user_id))
        return {"task": "placeholder completed", "memory": actor is not None}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        payload = {"tenant_id": TENANT, "user_id": "placeholder-attacker"}
        response = await client.post("/task", json=payload)
        assert response.status_code == 200 and response.json()["memory"] is False
        assert (await client.post("/memory", json=payload)).status_code == 401
        request = client.build_request("POST", "/task", json=payload)
        token = identity.sign("trigger", USER, request.method, "/task", request.content, key=KEY)
        request.headers[identity.HEADER] = token
        assert (await client.send(request)).json()["memory"] is True
        assert memory_calls == [(TENANT, "placeholder-user-a")]
        assert (await client.post("/task", json=payload, headers={identity.HEADER: token})).json()["memory"] is False
        assert len(memory_calls) == 1
        assert (await client.post("/memory", json=payload, headers={identity.HEADER: "placeholder-invalid"})).status_code == 401


@pytest.mark.asyncio
async def test_shared_http_client_signs_only_product_calls_and_never_redirects(monkeypatch):
    import paid_http
    monkeypatch.setenv("TANK_KEY_TRIGGER", KEY)
    seen = []
    async def handle(request):
        seen.append(request)
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"Location": "https://placeholder-external.example/task"})
        return httpx.Response(200, json={})
    actor = SimpleNamespace(tenant_id=uuid.UUID(TENANT), user_id="placeholder-user-a", tenant_admin=True, founder=False)
    async with paid_http.Client(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
        with identity.actor_scope(actor):
            await client.post("http://agent-trigger:8000/task", json={"user_id": "placeholder-attacker"})
            await client.get("http://agent-trigger:8000/redirect")
        await client.get("http://agent-trigger:8000/task")
    assert identity.HEADER in seen[0].headers and identity.HEADER in seen[1].headers
    assert identity.HEADER not in seen[2].headers and identity.HEADER not in seen[3].headers
    req = seen[0]
    verified = await verify_assertion(req.headers[identity.HEADER], key=KEY, product="trigger", tenant_id=TENANT,
        method=req.method, target="/task", body=req.content, consume_nonce=PlaceholderNonces().claim)
    assert verified.user_id == actor.user_id and verified.role == "org:admin"


@pytest.mark.asyncio
async def test_verified_signin_actor_reaches_product_body_identity_never_does(monkeypatch):
    import sys
    import identity_oidc as oidc
    import paid_http
    from trigger_signin_guard import TriggerSigninMiddleware
    from trigger_signin_fakes import Provider, ORG, install_registry
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(TANK_API_KEY="placeholder-workspace-key", box_region=lambda: "us-east"))
    monkeypatch.setenv("TANK_KEY_TRIGGER", KEY)
    provider = Provider("us-east")
    provider.claims["sub"] = "placeholder-user-a"
    install_registry(monkeypatch, [provider], {ORG: TENANT})
    monkeypatch.setattr(oidc, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    oidc._cache.clear()
    seen = []
    async def product(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})
    app = FastAPI()
    app.add_middleware(TriggerSigninMiddleware)
    @app.post("/task")
    async def task(request: Request):
        async with paid_http.Client(transport=httpx.MockTransport(product)) as client:
            await client.post("http://agent-trigger:8000/task", json=await request.json())
        return {"ok": True}
    headers = {"X-Tank-Key": "placeholder-workspace-key", "X-Trigger-Signin-Token": provider.token()}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        payload = {"tenant_id": TENANT, "user_id": "placeholder-attacker", "role": "founder"}
        assert (await client.post("/task", headers=headers, json=payload)).status_code == 200
        assert (await client.post("/task", headers={"X-Tank-Key": "placeholder-workspace-key"}, json=payload)).status_code == 200
        assert (await client.post("/task", headers={**headers, "X-Tervory-User": "placeholder-attacker"}, json=payload)).status_code == 403
    assert len(seen) == 2 and identity.HEADER not in seen[1].headers
    request = seen[0]
    actor = await verify_assertion(request.headers[identity.HEADER], key=KEY, product="trigger", tenant_id=TENANT,
        method="POST", target="/task", body=request.content, consume_nonce=PlaceholderNonces().claim)
    assert actor.user_id == "placeholder-user-a" and actor.role == "org:admin"
    assert identity.current.get() is None


@pytest.mark.asyncio
async def test_signed_product_actor_controls_real_hermes_and_ignores_body_user(memory, monkeypatch):
    from chassis.memory import MemoryClient
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    from test_agent_memory_records import Encoder
    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), KEY)
    hermes = create_app(InMemoryStore(), Encoder(), records=m.records)
    product = FastAPI()
    nonces = PostgresNonces(m.pool, m.agent)
    @product.post("/task")
    async def task(request: Request):
        body = await request.json()
        actor = await signed_user(request, tenant_id=body["tenant_id"], product="trigger", key=KEY, nonces=nonces)
        if actor is not None:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=hermes)) as http:
                client = MemoryClient("http://placeholder-hermes", KEY, m.agent, http, user_id=actor.user_id)
                await client.remember(actor.tenant_id, "placeholder private answer", "placeholder.personal", "placeholder-source")
        return {"task": "placeholder complete", "memory": actor is not None}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=product), base_url="http://placeholder") as client:
        payload = {"tenant_id": m.tenant, "user_id": "placeholder-user-b"}
        request = client.build_request("POST", "/task", json=payload)
        request.headers[identity.HEADER] = identity.sign("trigger", identity.User(m.tenant, "placeholder-user-a", "member"),
            "POST", "/task", request.content, key=KEY)
        assert (await client.send(request)).json()["memory"] is True
        assert (await client.post("/task", json=payload)).json()["memory"] is False
    assert len(await m.records.list(m.agent, m.tenant, user_id="placeholder-user-a")) == 1
    assert await m.records.list(m.agent, m.tenant, user_id="placeholder-user-b") == []


def test_product_origins_are_exact_and_unknown_calls_carry_no_user(monkeypatch):
    monkeypatch.setenv("TANK_KEY_TRIGGER", KEY)
    monkeypatch.setenv("BASE_AGENT_URL", "http://placeholder.invalid:bad")
    for url in ("https://agent-trigger.evil-placeholder.example/task", "http://agent-trigger:8001/task",
                "http://placeholder-provider.example/task"):
        request = httpx.Request("GET", url, headers={identity.HEADER: "placeholder-injected"})
        with identity.actor_scope(SimpleNamespace(tenant_id=TENANT, user_id="placeholder-user", founder=False)):
            identity.attach(request)
        assert identity.HEADER not in request.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("product", sorted(identity.PRODUCTS))
async def test_each_product_uses_its_own_key_and_audience(monkeypatch, product):
    key = "placeholder-" + product + "-key"
    monkeypatch.setenv(identity.key_setting(product), key)
    request = httpx.Request("POST", "http://agent-" + product.replace("_", "-") + ":8000/task", content=b"placeholder-body")
    with identity.actor_scope(SimpleNamespace(tenant_id=TENANT, user_id="placeholder-user", founder=False)):
        identity.attach(request)
    actor = await verify_assertion(request.headers[identity.HEADER], key=key, product=product, tenant_id=TENANT,
        method="POST", target="/task", body=request.content, consume_nonce=PlaceholderNonces().claim)
    assert actor.user_id == "placeholder-user"
    with pytest.raises(PermissionError):
        await verify_assertion(request.headers[identity.HEADER], key="placeholder-other-product-key", product=product,
            tenant_id=TENANT, method="POST", target="/task", body=request.content, consume_nonce=PlaceholderNonces().claim)


@pytest.mark.asyncio
async def test_registry_resolved_product_origin_does_not_survive_external_redirect(monkeypatch):
    import paid_http
    monkeypatch.setenv("TANK_KEY_RIG", KEY)
    seen = []
    async def handle(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://placeholder-external.example/task"}) if len(seen) == 1 else httpx.Response(200)
    base = "http://placeholder-tenant-rig:8003"
    with identity.actor_scope(SimpleNamespace(tenant_id=TENANT, user_id="placeholder-user", founder=False)):
        async with paid_http.Client(transport=httpx.MockTransport(handle), follow_redirects=True) as client:
            await client.get(base + "/task", extensions=identity.product_extensions("rig", base))
    assert identity.HEADER in seen[0].headers
    assert identity.HEADER not in seen[1].headers
