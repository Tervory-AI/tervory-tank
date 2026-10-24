"""Review regressions: public/control isolation and existing ACCESS behavior."""

import hmac
import json
import secrets
from uuid import UUID

import httpx
import pytest
import yaml
from fastapi import FastAPI
from pydantic import ValidationError

from test_rig_feeds_retailer import ROOT, SITE, TENANT, OTHER, access, prepared
from command import Actor
from rigbox.feeds import mapper
from rigbox.retailer_server import create_retailer_app, serve_retailer


@pytest.mark.asyncio
async def test_public_retailer_paths_are_404_even_with_valid_control_or_room_keys(monkeypatch):
    from test_rig import _load_rig_app
    room_key, control_key = secrets.token_hex(32), secrets.token_hex(32)
    monkeypatch.setenv("TANK_KEY", room_key)
    monkeypatch.setenv("RIG_RETAILER_KEY", control_key)
    app = _load_rig_app().app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://rig.tervory.com") as client:
        for operation in ("panel", "import", "mapping", "price-rule", "exchange-rate", "templates", "approve", "reject", "suggest", "tiger"):
            for headers in ({}, {"x-tank-key": room_key}, {"x-rig-retailer-key": control_key}):
                response = await client.post("/internal/retailer/" + operation, headers=headers,
                    json={"tenant_id": OTHER, "founder": True, "data": {}})
                assert response.status_code == 404


@pytest.mark.asyncio
async def test_brain_key_cannot_control_retailer_even_on_private_port(monkeypatch):
    retailer = await prepared()
    room_key, control_key = secrets.token_hex(32), secrets.token_hex(32)
    monkeypatch.setenv("TANK_KEY", room_key)
    monkeypatch.setenv("RIG_RETAILER_KEY", control_key)
    app = create_retailer_app(retailer.service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://private") as client:
        for headers in ({"x-tank-key": room_key}, {"x-rig-retailer-key": room_key}, {}):
            response = await client.post("/internal/retailer/exchange-rate", headers=headers,
                json={"tenant_id": TENANT, "founder": True, "data": {"currency": "USD", "rate": "1"}})
            assert response.status_code == 401
        response = await client.post("/internal/retailer/panel", headers={"x-rig-retailer-key": control_key},
            json={"tenant_id": TENANT})
        assert response.status_code == 200
        monkeypatch.delenv("RIG_RETAILER_KEY")
        assert (await client.post("/internal/retailer/panel", headers={"x-rig-retailer-key": control_key},
            json={"tenant_id": TENANT})).status_code == 401


@pytest.mark.asyncio
async def test_private_listener_starts_and_stops_with_its_context(monkeypatch):
    retailer = await prepared()
    control_key = secrets.token_hex(32)
    monkeypatch.setenv("RIG_RETAILER_KEY", control_key)
    async with httpx.AsyncClient(trust_env=False) as client:
        async with serve_retailer(retailer.service, host="127.0.0.1", port=0) as port:
            url = f"http://127.0.0.1:{port}/internal/retailer/panel"
            assert (await client.post(url, json={"tenant_id": TENANT})).status_code == 401
            assert (await client.post(url, headers={"x-rig-retailer-key": control_key}, json={"tenant_id": TENANT})).status_code == 200
        with pytest.raises(httpx.ConnectError):
            await client.post(url, json={"tenant_id": TENANT})


def test_control_key_only_reaches_tank_and_agent_rig_and_proxy_only_serves_public_port():
    tank = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    rig = yaml.safe_load((ROOT / "agents/rig/docker-compose.yml").read_text())["services"]
    assert {name for name, cfg in tank.items() if "RIG_RETAILER_KEY" in cfg.get("environment", {})} == {"tank"}
    assert {name for name, cfg in rig.items() if "RIG_RETAILER_KEY" in cfg.get("environment", {})} == {"agent-rig"}
    assert "ports" not in rig["agent-rig"]
    labels = dict(line.split("=", 1) for line in rig["agent-rig"]["labels"])
    assert labels["traefik.http.services.rig.loadbalancer.server.port"] == "8000"


@pytest.mark.asyncio
async def test_tank_supplies_actor_founder_status_and_separate_control_credential(monkeypatch):
    control_key = secrets.token_hex(32)
    monkeypatch.setenv("RIG_RETAILER_KEY", control_key)
    monkeypatch.setenv("TANK_KEY_RIG", secrets.token_hex(32))
    seen = []
    def respond(request):
        assert str(request.url) == "http://agent-rig:8003/internal/retailer/templates"
        assert hmac.compare_digest(request.headers["x-rig-retailer-key"], control_key)
        assert "x-tank-key" not in request.headers
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"saved": True})
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs))
    for founder in (False, True):
        actor = Actor(UUID(TENANT), "server-user", founder, frozenset({"rig"}))
        await access.rig_request(actor, "templates", {"founder": not founder, "tenant_id": OTHER})
        assert seen[-1]["founder"] is founder
        assert seen[-1]["tenant_id"] == TENANT


@pytest.mark.parametrize("encoding", [None, "utf-8", "utf-16"])
@pytest.mark.parametrize("declaration", ['<!DOCTYPE rss [<!ENTITY a "' + 'x' * 2048 + '">]>', '<!ENTITY a "unsafe">'], ids=["dtd", "entity"])
def test_merchant_declarations_are_rejected_before_xml_parsing(monkeypatch, encoding, declaration):
    def forbidden_parse(_):
        pytest.fail("XML parser must not see a declaration")
    monkeypatch.setattr(mapper.ET, "fromstring", forbidden_parse)
    raw = declaration + '<rss><channel><item>&a;</item></channel></rss>'
    result = mapper.map_google_merchant(raw.encode(encoding) if encoding else raw)
    assert result["rows"] == [] and result["rejected"]


@pytest.mark.asyncio
async def test_general_feed_routes_cannot_target_rig_and_tiger_auth_precedes_parsing():
    app = FastAPI()
    app.include_router(access.router)
    actor = Actor(UUID(TENANT), "member", False, frozenset())
    app.dependency_overrides[access.identity] = lambda: actor
    bodies = {
        "import": {"source": "ftp_export", "format": "csv", "contents": "sku,price\na,1"},
        "connect": {"format": "csv", "endpoint": SITE + "/feed.csv", "official_read_only": True},
        "refresh": {},
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for operation, fields in bodies.items():
            actor = Actor(UUID(TENANT), "member", False, frozenset({"rig"}))
            assert (await client.post("/v1/access/feeds/" + operation, content="bad json")).status_code == 403
            actor = Actor(UUID(TENANT), "member", False, frozenset({"rig", "tiger"}))
            result = await client.post("/v1/access/feeds/" + operation,
                json={"target": "rig", "distributor": "zanders", "site": SITE, **fields})
            assert result.status_code == 403


@pytest.mark.parametrize("model", [access.FeedImport, access.FeedConnection])
def test_rig_feed_options_do_not_expand_tiger_formats_or_column_limit(model):
    fields = {"source": "ftp_export", "contents": ""} if model == access.FeedImport else {"endpoint": SITE + "/feed", "official_read_only": True}
    base = {"distributor": "zanders", "site": SITE, "format": "csv", **fields}
    assert model(**base, columns={str(n): str(n) for n in range(5)}).target == "tiger"
    with pytest.raises(ValidationError):
        model(**base, columns={str(n): str(n) for n in range(6)})
    assert model(**base, target="rig", columns={str(n): str(n) for n in range(20)})
    with pytest.raises(ValidationError):
        model(**base, target="rig", columns={str(n): str(n) for n in range(21)})
    xml = {**base, "distributor": "google", "format": "xml"}
    with pytest.raises(ValidationError):
        model(**xml)
    assert model(**xml, target="rig")


@pytest.mark.parametrize("mode", ["none", "basic", "shopify"])
def test_new_authentication_modes_are_rig_only(mode):
    body = {"distributor": "zanders", "site": SITE, "endpoint": SITE + "/feed", "format": "csv", "official_read_only": True, "auth_mode": mode}
    with pytest.raises(ValidationError):
        access.FeedConnection(**body)
    assert access.FeedConnection(**body, target="rig")
