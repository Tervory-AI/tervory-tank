"""ACCESS-1 boundaries. Synthetic secrets are generated, never printed."""
import base64
import hmac
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import access
import vault
from command import Actor
from test_agent1_isolation import browser

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def keys(monkeypatch):
    for name in ("TANK_VAULT_KEY", "ACCESS_BROWSER_KEY_BASE", "ACCESS_BROWSER_KEY_TIGER"):
        monkeypatch.setenv(name, base64.urlsafe_b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("ACCESS_BROWSER_KEY", os.environ["ACCESS_BROWSER_KEY_BASE"])
    monkeypatch.setenv("ACCESS_ROOM", "base")


def make_connection(tenant, room="base", site="https://dealer.example", **fields):
    values = {"username": uuid.uuid4().hex, "password": uuid.uuid4().hex, "totp": ""}
    row = {"tenant_id": tenant, "room": room, "site": site, "terms": "yes", "rotation_days": 30,
           "updated_at": datetime.now(timezone.utc), "version": uuid.uuid4(), "revoked": False,
           "clear_pending": False, "login_config": {"login_path": "/login"},
           "sealed": vault.seal(values, vault.context(tenant, room, site, "login")), **fields}
    return row, values


class MemoryDB:
    def __init__(self):
        self.rows = {}; self.receipts = []; self.nonces = set(); self.queues = []; self.feed_rows = {}

    @asynccontextmanager
    async def acquire(self): yield self

    @asynccontextmanager
    async def transaction(self): yield self

    async def fetchrow(self, sql, *args):
        if "SELECT c.*" in sql: return self.rows.get(tuple(args[:3]))
        if "INSERT INTO tank.access_queue" in sql:
            self.queues.append(args); return {"id": uuid.uuid4()}
        if "SELECT r.data,b.source" in sql:
            return self.feed_rows.get(tuple(args[:3]))
        raise AssertionError("Unexpected read")

    async def fetchval(self, sql, *args):
        if "INSERT INTO tank.access_nonces" in sql:
            if tuple(args) in self.nonces: return None
            self.nonces.add(tuple(args)); return args[1]
        if "access_feed_links" in sql: return "item-1"
        if "access_connections" in sql: return bool(self.rows.get(tuple(args)))
        raise AssertionError("Unexpected value read")

    async def execute(self, sql, *args):
        if "INSERT INTO tank.access_receipts" in sql: self.receipts.append(args)
        elif "UPDATE tank.access_connections SET sealed=NULL" in sql:
            self.rows[tuple(args[:3])].update(sealed=None, revoked=True, clear_pending=True)
        elif "UPDATE tank.access_connections SET clear_pending=false" in sql:
            self.rows[tuple(args[:3])]["clear_pending"] = False
        return "OK"


@pytest.fixture
def app(keys, monkeypatch):
    db = MemoryDB(); monkeypatch.setattr(access, "db", lambda: db)
    actor = Actor(uuid.uuid4(), "owner", True, frozenset({"base", "tiger"}))
    app = FastAPI(); app.include_router(access.router)
    app.dependency_overrides[access.identity] = lambda: actor
    return app, db, actor


@pytest.mark.asyncio
async def test_vault_scope_and_browser_keys_cannot_be_substituted(keys):
    tenant = uuid.uuid4(); row, values = make_connection(tenant)
    for other in (vault.context(uuid.uuid4(), "base", row["site"], "login"),
                  vault.context(tenant, "tiger", row["site"], "login"),
                  vault.context(tenant, "base", "https://other.example", "login")):
        with pytest.raises(HTTPException): vault.open_seal(row["sealed"], other)
    assert hmac.compare_digest(vault.open_seal(row["sealed"], vault.context(tenant, "base", row["site"], "login"))["password"], values["password"])
    request = vault.envelope("base", "request", {"tenant_id": str(tenant)})
    with pytest.raises(HTTPException): vault.open_envelope("tiger", "request", request)
    assert all(value not in row["sealed"] for value in values.values() if value)


@pytest.mark.asyncio
async def test_only_owning_browser_can_release_exact_tenant_site(app, caplog, capsys):
    server, db, actor = app
    row, values = make_connection(actor.tenant_id)
    db.rows[(actor.tenant_id, "base", row["site"])] = row
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        # The ordinary room and Workspace APIs cannot request plaintext.
        invalid = await client.post("/v1/access/browser/base", json={"tenant_id": str(actor.tenant_id)})
        assert invalid.status_code == 422
        for tenant, site, room in ((uuid.uuid4(), row["site"], "base"), (actor.tenant_id, "https://other.example", "base"),
                                   (actor.tenant_id, row["site"], "tiger"), (actor.tenant_id, row["site"], "base")):
            payload = vault.envelope(room, "request", {"tenant_id": str(tenant), "site": site, "action": "release"})
            response = await client.post("/v1/access/browser/" + room, json=payload)
            assert response.status_code == 200
            data = vault.open_envelope(room, "response", response.json())
            correct = tenant == actor.tenant_id and site == row["site"] and room == "base"
            assert ("credential" in data) is correct
            if correct: assert hmac.compare_digest(data["credential"]["password"], values["password"])
            assert all(value not in response.text for value in values.values() if value)
            repeated = await client.post("/v1/access/browser/" + room, json=payload)
            assert repeated.status_code == 409
    observed = caplog.text + capsys.readouterr().out + json.dumps(db.receipts, default=str)
    assert all(value not in observed for value in values.values() if value)


@pytest.mark.asyncio
@pytest.mark.parametrize("fields,state", [({"terms": "no"}, "terms_no"), ({"terms": "unknown"}, "terms_unknown"),
    ({"updated_at": datetime.now(timezone.utc)-timedelta(days=31)}, "rotation_due"), ({"revoked": True}, "revoked"),
    ({"clear_pending": True}, "revoked")])
async def test_terms_rotation_and_revocation_refuse_release(app, fields, state):
    server, db, actor = app
    row, _ = make_connection(actor.tenant_id, **fields); db.rows[(actor.tenant_id, "base", row["site"])] = row
    payload = vault.envelope("base", "request", {"tenant_id": str(actor.tenant_id), "site": row["site"], "action": "release"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        response = await client.post("/v1/access/browser/base", json=payload)
    data = vault.open_envelope("base", "response", response.json())
    assert data["state"] == state and "credential" not in data
    assert db.receipts[-1][4] == "login_refused"


@pytest.mark.asyncio
async def test_sensitive_validation_does_not_echo_input(app, caplog):
    server, _, actor = app
    sensitive = uuid.uuid4().hex
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        response = await client.post("/v1/access/credentials", json={"room": sensitive, "site": "https://dealer.example", "username": sensitive, "password": sensitive})
    assert response.status_code == 422 and sensitive not in response.text and sensitive not in caplog.text


@pytest.mark.asyncio
async def test_revoke_removes_credential_and_only_own_session(app, monkeypatch, tmp_path):
    server, db, actor = app
    row, _ = make_connection(actor.tenant_id); db.rows[(actor.tenant_id, "base", row["site"])] = row
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(browser, "held", {})
    monkeypatch.setattr(browser, "access_locks", {})
    own = browser.storage_for(str(actor.tenant_id), row["site"]); own.write_text("{}")
    other = browser.storage_for(str(uuid.uuid4()), row["site"]); other.write_text("{}")
    async def control(room, data):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url="http://browser") as client:
            response = await client.post("/access/control", json=vault.envelope(room, "control", data))
        assert response.status_code == 200
        return vault.open_envelope(room, "result", response.json())
    monkeypatch.setattr(access, "control", control)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        response = await client.post("/v1/access/revoke", json={"room": "base", "site": row["site"]})
    assert response.status_code == 200
    assert row["sealed"] is None and row["revoked"] and not row["clear_pending"]
    assert not own.exists() and other.exists()
    assert [r[4] for r in db.receipts] == ["revoked", "logout"]


@pytest.mark.asyncio
async def test_failed_session_removal_keeps_revocation_effective(app, monkeypatch):
    server, db, actor = app
    row, _ = make_connection(actor.tenant_id); db.rows[(actor.tenant_id, "base", row["site"])] = row
    async def unavailable(*args): raise HTTPException(503, "Unavailable")
    monkeypatch.setattr(access, "control", unavailable)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        response = await client.post("/v1/access/revoke", json={"room": "base", "site": row["site"]})
    assert response.status_code == 503
    assert row["sealed"] is None and row["revoked"] and row["clear_pending"]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["terms_no", "terms_unknown", "rotation_due"])
async def test_refused_browser_login_enters_queue_without_launching(keys, monkeypatch, tmp_path, state):
    events = []
    async def rpc(tenant, site, action, **kwargs):
        events.append((action, kwargs)); return {"state": state, "queue_id": str(uuid.uuid4())}
    monkeypatch.setattr(browser, "access_rpc", rpc)
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(browser, "held", {})
    result = await browser.visit(browser.Page(url="https://dealer.example"), str(uuid.uuid4()), "", "https://dealer.example")
    assert result["challenge"] and result["html"] == "" and result["login_status"] == "login failed"
    assert events[-1] == ("queue", {"reason": state, "task_id": None})


@pytest.mark.parametrize("distributor,header", [("zanders", "ItemNumber,Price,Quantity,UPC"),
    ("sports_south", "ItemNo,PRC,QTY,UPC"), ("rsr", "RSR Stock Number,RSR Regular Price,Inventory Quantity,UPC Code"),
    ("jerrys", "ItemNumber,DealerPrice,QtyAvailable,UPC")])
def test_distributor_export_adapters(distributor, header):
    body = access.FeedImport(distributor=distributor, site="https://dealer.example", source="ftp_export", format="csv",
                             contents=header + "\nitem-1,12.50,7,000123456789\n")
    result = access.parse_feed(body)
    assert result == [{"sku": "item-1", "price": "12.50", "quantity": "7", "upc": "000123456789", "currency": "USD"}]


def test_edi846_inventory_and_price():
    body = access.FeedImport(distributor="rsr", site="https://dealer.example", source="edi_export", format="edi846",
                             contents="LIN*1*VP*item-1*UP*000123456789~QTY*33*7~CTP**DPR*12.50~")
    assert access.parse_feed(body)[0]["price"] == "12.50"


@pytest.mark.asyncio
async def test_portal_prices_never_cross_tenants(app):
    _, db, actor = app
    db.feed_rows[(actor.tenant_id, "https://dealer.example", "item-1")] = {
        "data": {"price": "12.50"}, "source": "ftp_export", "fetched_at": datetime.now(timezone.utc),
        "row_count": 1, "distributor": "rsr", "id": uuid.uuid4()}
    own = await access.feed_price(actor.tenant_id, "https://dealer.example", "item-1", "", "", "tiger")
    other = await access.feed_price(uuid.uuid4(), "https://dealer.example", "item-1", "", "", "tiger")
    assert own["found"] and not other["found"] and "item" not in other


@pytest.mark.asyncio
async def test_private_feed_dns_is_refused_before_request(monkeypatch):
    import asyncio
    async def resolve(*args, **kwargs): return [(2, 1, 6, "", ("127.0.0.1", 443))]
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(ValueError): await access.public_get("https://dealer.example/export")


def test_separate_browser_keys_and_volumes_are_not_in_brains():
    import yaml
    for room in ("base", "tiger"):
        compose = yaml.safe_load((ROOT / f"agents/{room}/docker-compose.yml").read_text())
        browser_service = compose["services"][room + "-browser"]
        assert browser_service["networks"] == ["browser"]
        assert compose["networks"]["browser"]["internal"] is True
        for name, service in compose["services"].items():
            assert ("ACCESS_BROWSER_KEY" in service.get("environment", {})) == (name == room + "-browser")
            if name != room + "-browser": assert not any("browser_data" in v for v in service.get("volumes", []))


def test_browser_envelope_interoperates_with_tank(keys):
    payload = browser.pack("request", {"tenant_id": str(uuid.uuid4())})
    assert vault.open_envelope("base", "request", payload)["tenant_id"]
    sealed = vault.envelope("base", "control", {"action": "revoke"})
    assert browser.unpack("control", sealed)["action"] == "revoke"


@pytest.mark.asyncio
async def test_hand_back_preserves_same_live_page(keys, monkeypatch, tmp_path):
    tenant = str(uuid.uuid4()); site = "https://dealer.example"; handle = str(uuid.uuid4())
    events = []
    async def rpc(*args, **kwargs): return {"state": "public"}
    monkeypatch.setattr(browser, "access_rpc", rpc)
    async def content(): return "<p>The check is complete</p>"
    async def state(**kwargs): events.append("cookies saved")
    item = browser.LivePage(tenant, site, SimpleNamespace(content=content), SimpleNamespace(storage_state=state), None, None,
                            tmp_path / "cookies", site, "", {"human": True})
    monkeypatch.setattr(browser, "held", {handle: item}); monkeypatch.setattr(browser, "access_locks", {})
    payload = vault.envelope("base", "control", {"action": "live", "tenant_id": tenant, "site": site, "handle": handle,
                                                "input": {"action": "hand_back"}})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url="http://browser") as client:
        response = await client.post("/access/control", json=payload)
    assert response.status_code == 200 and vault.open_envelope("base", "result", response.json())["ready"]
    assert browser.held[handle] is item and item.ready and events == ["cookies saved"]


@pytest.mark.asyncio
async def test_gateway_refuses_brain_or_other_room_peer(monkeypatch):
    from brain import browser_gateway
    import asyncio
    async def resolve(*args, **kwargs): return [(2, 1, 6, "", ("172.20.0.2", 3000))]
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser_gateway.app, client=("172.21.0.3", 5555)), base_url="http://gateway") as client:
        response = await client.post("/access/browser", json={"sealed": "invalid"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_live_control_refuses_ordinary_room_key_and_replay(keys):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url="http://browser") as client:
        response = await client.post("/access/control", json={"action": "live"}, headers={"X-Tank-Key": uuid.uuid4().hex})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_meta_is_off_without_app_review(app):
    server, _, actor = app
    server.dependency_overrides[access.room_identity] = lambda: "base"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        response = await client.post("/v1/access/social", json={"tenant_id": str(actor.tenant_id), "platform": "facebook", "business_id": "12345"})
    assert response.status_code == 200 and response.json() == {"enabled": False, "source": "search_results"}


@pytest.mark.asyncio
async def test_private_site_never_sent_to_archives(app, monkeypatch):
    server, db, actor = app
    row, _ = make_connection(actor.tenant_id); db.rows[(actor.tenant_id, "base", row["site"])] = row
    server.dependency_overrides[access.room_identity] = lambda: "base"
    async def forbidden(*args, **kwargs): raise AssertionError("Private site sent outside")
    monkeypatch.setattr(access, "public_get", forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://test") as client:
        response = await client.post("/v1/access/archives", json={"tenant_id": str(actor.tenant_id), "url": row["site"] + "/inventory"})
    assert response.status_code == 200 and response.json()["found"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("human,safe,success", [(True, True, False), (False, False, False), (False, True, True)])
async def test_login_uses_only_approved_post_form_and_stops_for_captcha(keys, monkeypatch, human, safe, success, caplog):
    tenant = str(uuid.uuid4()); site = "https://dealer.example"; filled = []
    config = {"login_path": "/login", "username_selector": "#account", "password_selector": "#password",
              "submit_selector": "#submit", "success_selector": "#logout", "totp_selector": "#otp"}
    secrets = {"username": uuid.uuid4().hex, "password": uuid.uuid4().hex, "totp": ""}
    sensitive = tuple(v for v in secrets.values() if v)
    async def rpc(*args, **kwargs): return {"state": "allowed", "credential": dict(secrets), "config": config}
    monkeypatch.setattr(browser, "access_rpc", rpc)
    class Field:
        def __init__(self, selector): self.selector = selector
        async def evaluate(self, code): return safe
        async def fill(self, value): filled.append(self.selector)
        async def click(self, **kwargs): pass
        async def count(self): return int(self.selector == "#logout")
        async def evaluate_all(self, code): pass
    class Page:
        url = site + "/login"
        async def goto(self, *args, **kwargs): pass
        async def content(self): return "verify you are human" if human else "Login form"
        async def wait_for_timeout(self, *args): pass
        def locator(self, selector): return Field(selector)
    navigation = {"login": False}
    result = await browser.login(Page(), None, tenant, site, navigation)
    assert result is success and not navigation["login"]
    assert bool(filled) is success
    assert all(value not in caplog.text for value in sensitive)


@pytest.mark.asyncio
async def test_revocation_cancels_an_active_visit_before_removing_cookie(keys, monkeypatch, tmp_path):
    import asyncio
    tenant = str(uuid.uuid4()); site = "https://dealer.example"
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path))
    cookie = browser.storage_for(tenant, site); cookie.write_text("{}")
    stopped = asyncio.Event()
    async def visit():
        try: await asyncio.Future()
        finally:
            cookie.write_text("{}")
            stopped.set()
    task = asyncio.create_task(visit()); await asyncio.sleep(0)
    monkeypatch.setattr(browser, "active_visits", {(tenant, site): task})
    monkeypatch.setattr(browser, "held", {}); monkeypatch.setattr(browser, "access_locks", {})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=browser.app), base_url="http://browser") as client:
        response = await client.post("/access/control", json=vault.envelope("base", "control", {"tenant_id": tenant, "site": site, "action": "revoke"}))
    assert response.status_code == 200 and stopped.is_set() and not cookie.exists()


@pytest.mark.asyncio
async def test_held_page_keeps_one_of_four_browser_slots(monkeypatch):
    import asyncio
    monkeypatch.setattr(browser, "concurrency", asyncio.Semaphore(4))
    monkeypatch.setattr(browser, "site_locks", {}); monkeypatch.setattr(browser, "last_visit", {})
    async with browser.render_slot("dealer.example") as slot:
        slot["retained"] = True
    assert browser.concurrency._value == 3


def test_cookie_files_do_not_cross_http_https_origins(monkeypatch, tmp_path):
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path)); tenant = str(uuid.uuid4())
    assert browser.storage_for(tenant, "https://dealer.example") != browser.storage_for(tenant, "http://dealer.example")


def test_private_cookies_cannot_be_reused_in_an_unconfigured_public_browser(monkeypatch, tmp_path):
    monkeypatch.setenv("BROWSER_DATA_DIR", str(tmp_path)); tenant = str(uuid.uuid4()); site = "https://dealer.example"
    private = browser.storage_for(tenant, site, authenticated=True); private.write_text("{}")
    assert not browser.storage_for(tenant, site).exists()
