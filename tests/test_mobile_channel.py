from contextlib import asynccontextmanager
import base64
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

import mobile
import mobile_push
from command import Actor
from tenant_db import bind_tenant_endpoints, _tenant


class Store:
    def __init__(self, devices=()):
        self.devices = list(devices)
        self.calls = []
        self.code = None
        self.session = None

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetch(self, sql, *args):
        self.calls.append((sql, args, _tenant.get()))
        assert "tenant_id=$1" in sql
        return self.devices

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args, _tenant.get()))
        assert "tenant_id=$1" in sql
        if "mobile_codes" in sql:
            return self.code if self.code and args[1] == self.code["hash"] else None
        return self.session

    async def execute(self, sql, *args):
        self.calls.append((sql, args, _tenant.get()))
        if "DELETE FROM tank.mobile_codes" in sql:
            self.code = None


@pytest.mark.asyncio
async def test_general_notify_route_reaches_fake_device_with_link_and_removes_dead(monkeypatch):
    tenant = uuid4()
    store = Store([dict(user_id="user-1", token_hash="hash", token="sealed", platform="ios", session_hash="session")])
    monkeypatch.setattr(mobile, "db", lambda: store)
    monkeypatch.setattr(mobile_push.vault, "open_seal", lambda value, context: {"token": "fake-phone"})
    received = []

    async def deliver(self, platform, token, notification):
        received.append((platform, token, notification.link))
        return "sent" if len(received) == 1 else "dead"

    monkeypatch.setattr(mobile_push.PushProviders, "deliver", deliver)
    app = FastAPI()
    app.include_router(mobile_push.router)
    app.dependency_overrides[mobile_push.sender] = lambda: None
    bind_tenant_endpoints(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://testserver") as client:
        payload = dict(tenant_id=str(tenant), user_id="user-1", title="An update", body="Your update is ready.", link="/chats?thread=proof")
        result = await client.post("/v1/mobile/notify", json=payload)
        assert result.json() == dict(sent=1, dead=0, failed=0, unavailable=0)
        assert received == [("ios", "fake-phone", "/chats?thread=proof")]
        assert (await client.post("/v1/mobile/notify", json=payload)).json()["dead"] == 1
        assert all(call[2] == str(tenant) for call in store.calls)
        assert all(call[1][0] == tenant for call in store.calls)
        assert "DELETE FROM tank.mobile_devices" in store.calls[-1][0]


@pytest.mark.parametrize("link", ["https://evil.test", "//evil.test", "/\\evil.test", "javascript:alert(1)", "https://app.tervory.com@evil.test", "/chats\n"])
def test_notify_refuses_external_links(link):
    with pytest.raises(ValidationError):
        mobile_push.Notification(tenant_id=uuid4(), title="Test", body="Test", link=link)


@pytest.mark.asyncio
async def test_apns_payload_and_dead_token_response(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    key = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    monkeypatch.setenv("MOBILE_APNS_KEY", key)
    monkeypatch.setenv("MOBILE_APNS_TEAM_ID", "fake-team")
    monkeypatch.setenv("MOBILE_APNS_KEY_ID", "fake-key")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(410, json={"reason": "Unregistered"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        message = mobile_push.Notification(tenant_id=uuid4(), title="Update", body="Ready", link="/chats")
        assert await mobile_push.PushProviders(client).deliver("ios", "fake-phone", message) == "dead"
    import json
    assert json.loads(requests[0].content)["path"] == "/chats"
    assert requests[0].headers["apns-push-type"] == "alert"


@pytest.mark.asyncio
async def test_fcm_unregistered_removes_only_dead_tokens(monkeypatch):
    monkeypatch.setenv("MOBILE_FCM_SERVICE_ACCOUNT_JSON", '{"project_id":"fake-project"}')
    async def bearer(self, account):
        return "fake-access"
    monkeypatch.setattr(mobile_push.PushProviders, "fcm_bearer", bearer)
    responses = [httpx.Response(404, json={"error": {"details": [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}]}}), httpx.Response(401, json={"error": {}})]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: responses.pop(0))) as client:
        provider = mobile_push.PushProviders(client)
        message = mobile_push.Notification(tenant_id=uuid4(), title="Update", body="Ready")
        assert await provider.deliver("android", "fake-phone", message) == "dead"
        assert await provider.deliver("android", "fake-phone", message) == "failed"


@pytest.mark.asyncio
async def test_session_exchange_pkce_single_use_and_tenant_scope(monkeypatch):
    tenant = uuid4()
    verifier = "v" * 43
    code = str(tenant) + "_" + "c" * 43
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    store = Store()
    store.code = dict(hash=mobile.digest(code), challenge=challenge, identity={"userId": "user-1"})
    monkeypatch.setattr(mobile, "db", lambda: store)
    bad = mobile.Exchange(code=code, code_verifier="x" * 43, redirect_uri=mobile.CALLBACK)
    with pytest.raises(HTTPException) as failure:
        await mobile.exchange(bad)
    assert failure.value.status_code == 401
    good = mobile.Exchange(code=code, code_verifier=verifier, redirect_uri=mobile.CALLBACK)
    assert (await mobile.exchange(good))["token"].startswith(str(tenant) + "_")
    with pytest.raises(HTTPException):
        await mobile.exchange(good)
    assert all(call[2] == str(tenant) for call in store.calls)


@pytest.mark.asyncio
async def test_device_cannot_register_for_other_session_user(monkeypatch):
    tenant = uuid4()
    async def principal(token):
        return dict(tenantId=str(tenant), userId="other")
    monkeypatch.setattr(mobile, "session_identity", principal)
    request = SimpleNamespace(headers={"x-mobile-session": "fake"})
    with pytest.raises(HTTPException) as failure:
        await mobile.register_device(mobile.Device(platform="ios", token="a" * 64), request, Actor(tenant, "user-1", False))
    assert failure.value.status_code == 403


@pytest.mark.asyncio
async def test_device_registration_uses_server_identity_and_encrypted_token(monkeypatch):
    tenant = uuid4()
    store = Store()
    async def principal(token):
        return dict(tenantId=str(tenant), userId="user-1")
    monkeypatch.setattr(mobile, "session_identity", principal)
    monkeypatch.setattr(mobile, "db", lambda: store)
    monkeypatch.setenv("TANK_VAULT_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode())
    app = FastAPI()
    app.include_router(mobile.router)
    app.dependency_overrides[mobile.identity] = lambda: Actor(tenant, "user-1", False)
    bind_tenant_endpoints(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://testserver") as client:
        assert (await client.post("/v1/mobile/devices", json={"platform": "ios", "token": "a" * 64}, headers={"x-mobile-session": "fake-session"})).status_code == 200
        assert (await client.post("/v1/mobile/devices", json={"platform": "ios", "token": "a" * 64, "user_id": "other"})).status_code == 422
    sql, values, scope = store.calls[0]
    assert "INSERT INTO tank.mobile_devices" in sql
    assert values[:2] == (tenant, "user-1")
    assert scope == str(tenant)
    assert values[3] != "a" * 64
    assert mobile.vault.open_seal(values[3], f"mobile:{tenant}:user-1:{values[2]}")["token"] == "a" * 64


def test_shared_files_are_bounded_and_inert():
    body = mobile.Share(share_id="id", text="https://example.org", files=[mobile.SharedFile(name="proof.txt", data="aGVsbG8=")])
    assert mobile.share_files(body) == [("proof.txt", b"hello")]
    with pytest.raises(HTTPException):
        mobile.share_files(mobile.Share(share_id="id", files=[mobile.SharedFile(name="../proof", data="aGVsbG8=")]))
