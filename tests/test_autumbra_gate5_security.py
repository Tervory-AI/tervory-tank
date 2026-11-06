import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from agents.ghost import app as watch, enforce_app, threat_queue, undo_token
from agents.ghost.client_settings import ClientAutumbraSettings, save_settings
from agents.ghost.durable_shields import _atomic_write_json
from agents.ghost.safe_files import file_lock, read_json
from agents.ghost.store import Store
from agents.ghost.tenant_queue import load_mirrored_settings, mirror_settings, queue_path_for_tenant
from agents.ghost.threat_queue import ThreatPayloadQueue, watch_enqueue_undo, watch_enqueue_approve

A, B = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.mark.asyncio
async def test_all_watch_routes_require_service_auth_or_signed_provider_or_owner_token(monkeypatch, tmp_path):
    monkeypatch.setenv("TANK_KEY", "placeholder-service-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = watch.create_app()
    store = Store(tmp_path / "watch.sqlite")
    app.state.store = store
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            paths = []
            for route in app.routes:
                if route.path == "/health":
                    continue
                path = route.path
                for name in route.param_convertors:
                    path = path.replace("{" + name + "}", "google_workspace" if name == "provider" else A)
                for method in route.methods - {"OPTIONS", "HEAD"}:
                    response = await client.request(method, path, json={})
                    assert response.status_code in {400, 401, 403, 404, 422}, (method, path, response.status_code)
                    paths.append((method, path))
            assert len(paths) >= 40
            for path in ("/docs", "/openapi.json", "/redoc"):
                assert (await client.get(path)).status_code == 404
    finally:
        store.close()


@pytest.mark.asyncio
async def test_stream_limit_stops_before_reading_the_rest_and_auth_can_reuse_body():
    chunks = [b"123", b"456", b"must-not-read"]
    calls = []
    async def receive():
        calls.append(True)
        return {"type": "http.request", "body": chunks.pop(0), "more_body": bool(chunks)}
    request = Request({"type": "http"}, receive)
    with pytest.raises(HTTPException) as error:
        await watch.bounded_json(request, 5)
    assert error.value.status_code == 413 and len(calls) == 2
    chunks[:] = [b'{"ok":true}']
    request = Request({"type": "http"}, receive)
    assert await watch.bounded_json(request, 100) == await watch.bounded_json(request, 100) == b'{"ok":true}'
    with pytest.raises(HTTPException):
        await watch.bounded_json(request, 3)


def test_mirror_cannot_change_the_enforce_tenant(tmp_path):
    mirror_settings(ClientAutumbraSettings(tenant_id=B), tmp_path)
    with pytest.raises(ValueError, match="another client"):
        load_mirrored_settings(tmp_path, fallback_tenant_id=A)


@pytest.mark.asyncio
async def test_settings_failure_cannot_fall_back_into_another_clients_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("TANK_KEY", "placeholder-service-key")
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE", str(tmp_path / "client-b"))
    monkeypatch.setenv("TENANT_ID", B)
    app, store = watch.create_app(), Store(tmp_path / "watch.sqlite")
    app.state.store = store
    monkeypatch.setattr(watch, "queue_path_for_tenant", lambda tenant: (_ for _ in ()).throw(OSError("placeholder-private-path")))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            response = await client.post("/ghost/autumbra/settings", headers={"X-Tank-Key": "placeholder-service-key"}, json={"tenant_id": A})
        assert response.status_code == 200
        assert not response.json()["receipt"]["mirrored_to_enforce_box"]
        assert not (tmp_path / "client-b/client_settings.json").exists()
        assert "placeholder-private-path" not in response.text
    finally:
        store.close()


@pytest.mark.asyncio
async def test_signed_receipts_never_include_a_foreign_tenant_even_in_the_wrong_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("TANK_KEY", "placeholder-service-key")
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", "placeholder-signing-key")
    monkeypatch.setenv("THREAT_PAYLOAD_QUEUE_ROOT", str(tmp_path / "queues"))
    queue = ThreatPayloadQueue(queue_path_for_tenant(A))
    for tenant in (A, B):
        queue.write_receipt({"id": tenant, "tenant_id": tenant, "timestamp": datetime.now(timezone.utc).isoformat(), "outcome": "reported"})
    app, store = watch.create_app(), Store(tmp_path / "watch.sqlite")
    app.state.store = store
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            token = undo_token.sign_receipts_token(tenant_id=A)
            response = await client.get("/ghost/autumbra/receipts/weekly/" + A, params={"token": token})
            assert response.status_code == 200 and response.json()["count"] == 1
            assert B not in response.text
            assert (await client.get("/ghost/autumbra/receipts/weekly/" + B, params={"token": token})).status_code == 401
    finally:
        store.close()


@pytest.mark.parametrize("location", ["root", "inbox", "receipts", "lock", "file"])
def test_storage_symlinks_cannot_read_or_overwrite_other_tenants(tmp_path, monkeypatch, location):
    outside = tmp_path / "other-client"
    outside.mkdir()
    private = outside / "private.json"
    private.write_text('{"private":"placeholder-private-value"}')
    root = tmp_path / "client"
    root.mkdir()
    if location == "root":
        (root / A).symlink_to(outside, target_is_directory=True)
        monkeypatch.setenv("THREAT_PAYLOAD_QUEUE_ROOT", str(root))
        with pytest.raises(ValueError):
            queue_path_for_tenant(A)
    elif location in {"inbox", "receipts"}:
        (root / location).symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError):
            ThreatPayloadQueue(root)
    elif location == "lock":
        (root / "state.lock").symlink_to(private)
        with pytest.raises(ValueError), file_lock(root / "state.lock"):
            pytest.fail("unsafe lock opened")
    else:
        link = root / "state.json"
        link.symlink_to(private)
        with pytest.raises(ValueError):
            read_json(link)
        with pytest.raises(ValueError):
            _atomic_write_json(link, {"changed": True})
    assert private.read_text() == '{"private":"placeholder-private-value"}'


def test_busy_state_lock_and_nonregular_reads_are_bounded(tmp_path):
    import os
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        read_json(fifo)
    with file_lock(tmp_path / "state.lock"):
        with pytest.raises(TimeoutError), file_lock(tmp_path / "state.lock", timeout=.01):
            pytest.fail("lock acquired twice")


@pytest.mark.parametrize("action", ["undo", "approve"])
def test_concurrent_owner_taps_and_restart_enqueue_one_job(tmp_path, action):
    def click(_):
        queue = ThreatPayloadQueue(tmp_path)
        kwargs = {"queue": queue, "prior_receipt_id": "receipt-one", "site": "tervory.com", "tenant_id": A}
        return watch_enqueue_undo(**kwargs) if action == "undo" else watch_enqueue_approve(**kwargs)
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(click, range(12)))
    assert len(list((tmp_path / "inbox").glob("*.json"))) == 1
    click(None)
    assert len(list((tmp_path / "inbox").glob("*.json"))) == 1
    if action == "undo":
        assert sum(bool(row["queued"]) for row in results) == 1


def test_undo_identifier_cannot_alias_or_escape_another_receipt(tmp_path):
    queue = ThreatPayloadQueue(tmp_path)
    for identity in ("../secret", "receipt/one", "receipt.one", "a" * 201):
        with pytest.raises(ValueError):
            threat_queue.read_undo_used(queue, identity)


@pytest.mark.parametrize("expiry", [True, None, "NaN", "9999999999", [], {}])
def test_signed_token_requires_an_integer_expiry(monkeypatch, expiry):
    monkeypatch.setenv("AUTUMBRA_UNDO_TOKEN_SECRET", "placeholder-signing-key")
    token = undo_token._sign_payload({"tenant_id": A, "receipt_id": "receipt", "exp": expiry})
    with pytest.raises(ValueError):
        undo_token.verify_undo_token(token)


@pytest.mark.asyncio
async def test_untrusted_network_cannot_trigger_enforce_drain(monkeypatch):
    monkeypatch.setattr(enforce_app, "drain_once_for_enforce", lambda **kw: pytest.fail("unauthenticated drain"))
    app = enforce_app.create_enforce_app()
    for peer in ("203.0.113.10", "other-client"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(peer, 1234)), base_url="http://offline") as client:
            assert (await client.post("/v1/drain-once")).status_code == 404


def test_provider_retry_budget_survives_restart_and_stops(monkeypatch, tmp_path):
    from agents.ghost.cloudflare_edge import CloudflareEdgeError
    from agents.ghost.threat_payload import accept_threat_payload
    def unavailable(*args, **kwargs):
        raise CloudflareEdgeError("placeholder-private-upstream")
    monkeypatch.setattr(threat_queue, "undo_from_payload", unavailable)
    q = ThreatPayloadQueue(tmp_path)
    q.put(accept_threat_payload({"schema_version": "ghost.threat.v1", "action": "undo_shield",
        "tenant_id": A, "site": "tervory.com", "rule_id": "a" * 32, "prior_receipt_id": "receipt-one"}))
    for attempt in range(1, 4):
        q = ThreatPayloadQueue(tmp_path)
        with pytest.raises(CloudflareEdgeError):
            threat_queue.enforce_drain_once(q, settings=ClientAutumbraSettings(tenant_id=A), data_dir=tmp_path)
        latest = max(q.list_receipts(), key=lambda row: row["retry_attempts"])
        assert latest["retry_attempts"] == attempt
        assert latest["retry_exhausted"] is (attempt == 3)
        assert "placeholder-private-upstream" not in json.dumps(q.list_receipts())
    assert not list((tmp_path / "inbox").glob("*.json"))
    assert threat_queue.enforce_drain_once(q, settings=ClientAutumbraSettings(tenant_id=A)) is None


@pytest.mark.asyncio
async def test_invalid_connect_flags_and_receipt_paths_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setenv('TANK_KEY', 'placeholder-service-key')
    app, store = watch.create_app(), Store(tmp_path / 'watch.sqlite')
    app.state.store = store
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline',
                                     headers={'X-Tank-Key':'placeholder-service-key'}) as client:
            for connected in ['false', 1, None, {}, []]:
                response = await client.post('/ghost/autumbra/hands', json={'tenant_id':A, 'hand':'host_firewall', 'connected':connected})
                assert response.status_code == 422
            response = await client.get('/ghost/autumbra/undo/status', params={'tenant_id':A,'prior_receipt_id':'../private'})
            assert response.status_code == 400
    finally:
        store.close()


@pytest.mark.asyncio
async def test_scheduler_failure_is_visible_without_logging_exception_details(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv('TANK_KEY', 'placeholder-service-key')
    app, store = watch.create_app(), Store(tmp_path / 'watch.sqlite')
    app.state.store, app.state.monitor = store, {'running':True, 'unavailable_checks':0}
    async def unavailable(*args):
        raise RuntimeError('placeholder-private-upstream')
    async def stop(*args):
        raise asyncio.CancelledError()
    monkeypatch.setattr(watch, 'deliver_act_owner_updates', unavailable)
    monkeypatch.setattr(watch.asyncio, 'sleep', stop)
    try:
        with pytest.raises(asyncio.CancelledError):
            await watch._act_owner_email_loop(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
            health = await client.get('/health')
            panel = await client.get('/incidents', headers={'X-Tank-Key':'placeholder-service-key'})
        assert health.json()['owner_actions']['unavailable'] == 1
        assert panel.json()['monitor']['unavailable_checks'] == 1
        assert 'placeholder-private-upstream' not in health.text + panel.text + caplog.text
    finally:
        store.close()


def test_dogfood_transport_failure_cannot_put_secrets_in_a_receipt(monkeypatch):
    from agents.ghost import dogfood_hf
    monkeypatch.setattr(dogfood_hf, 'live_armed', lambda: True)
    monkeypatch.setattr(dogfood_hf, 'hf_token', lambda: True)
    async def unavailable(*args):
        raise httpx.ConnectError('placeholder-private-upstream')
    monkeypatch.setattr(dogfood_hf, 'call_tank_inference', unavailable)
    receipt = dogfood_hf.dogfood_watch_triage(live=True, soft_live=True)
    assert receipt['hf_error'] == 'Tank request did not finish.'
    assert 'placeholder-private-upstream' not in json.dumps(receipt)
