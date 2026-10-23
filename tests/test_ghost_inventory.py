"""GHOST-2 part 1: inventory parsers, the host-report intake and read-only sources. Offline only."""
import asyncio
import ipaddress
import json
import re
from pathlib import Path

import httpx
import pytest

from agents.ghost import inventory as inv
from agents.ghost.app import create_app
from agents.ghost.models import PLATFORM_TENANT
from agents.ghost.store import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ghost"
HOST_REPORT = FIXTURES / "host-a-report-2026-10-23.json"


def by_key(items):
    return {(c.app, c.kind, c.name): c.version for c in items}


def test_committed_host_report_is_sanitised():
    """The repo copy must not carry IP addresses or the real server name."""
    for path in FIXTURES.rglob("*.json"):
        text = path.read_text()
        for token in re.findall(r"[0-9A-Fa-f:.]{7,}", text):
            for candidate in (token.strip(".:"), *token.split(" ")):
                try:
                    address = ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                pytest.fail(f"{path.name} contains an IP address ({address.version})")
        assert "boston" not in text.lower(), path.name
        assert not re.search(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b", text), path.name
    assert json.loads(HOST_REPORT.read_text())["host"] == "host-a"


def test_host_report_fixture_becomes_version_facts():
    items = by_key(inv.from_host_report(json.loads(HOST_REPORT.read_text())))
    assert items[("coolify", "software", "coolify")] == "4.4.7"
    assert items[("coolify", "runtime", "php")] == "8.4.27"
    assert items[("coolify", "runtime", "node")] == "24.22.1"
    assert items[("host", "software", "docker-engine")] == "29.9.0"
    assert items[("host", "runtime", "python")] == "3.14.4"
    assert items[("host", "runtime", "node")] == "22.23.4"
    assert items[("litellm", "package", "litellm")] == "1.106.0"
    assert items[("tank", "runtime", "python")] == "3.12.15"
    assert items[("tiger", "package", "pip")] == "24.2"
    assert items[("chatwoot", "image", "chatwoot/chatwoot")] == "v4.18.0-ce"
    # A bare major tag ("redis:7") is kept as an image but never as a matchable version.
    assert ("redis", "software", "redis") not in items


def test_container_names_lose_coolify_ids_and_timestamps():
    assert inv.container_app("59f8cnpelzwsyte1atyjc4fv-rig-brain-1") == "rig-brain"
    assert inv.container_app("tank-xnmc0jkz8j9i5jh1jwanbsfv-20261022T210127") == "tank"
    assert inv.container_app("coolify") == "coolify"


def test_lockfile_and_dockerfile_parsers():
    reqs = inv.parse_requirements("tank", "fastapi==0.115.6\nuvicorn[standard]==0.32.1  # web\nloose>=1\nZope.Interface===5.0 ; python_version>'3'\n")
    assert by_key(reqs) == {("tank", "package", "fastapi"): "0.115.6", ("tank", "package", "uvicorn"): "0.32.1",
                            ("tank", "package", "zope-interface"): "5.0"}
    v3 = json.dumps({"lockfileVersion": 3, "packages": {"": {"name": "ws"}, "node_modules/next": {"version": "15.1.0"},
                                                         "node_modules/a/node_modules/@scope/b": {"version": "1.0.0-rc.1"},
                                                         "node_modules/linked": {"link": True, "version": "0.0.0"}}})
    assert by_key(inv.parse_package_lock("workspace", v3)) == {("workspace", "package", "next"): "15.1.0",
                                                               ("workspace", "package", "@scope/b"): "1.0.0-rc.1"}
    v1 = json.dumps({"lockfileVersion": 1, "dependencies": {"left-pad": {"version": "1.3.0", "dependencies": {"x": {"version": "2.0.0"}}}}})
    assert len(inv.parse_package_lock("site", v1)) == 2
    pnpm = "lockfileVersion: '9.0'\n\npackages:\n\n  '@babel/core@7.26.0':\n    resolution: {}\n  next@15.1.0(react@19.0.0):\n    x: y\n  /old-style/1.2.3:\n    x: y\nsnapshots:\n  react@19.0.0:\n    x: y\n"
    assert by_key(inv.parse_pnpm_lock("tisan", pnpm)) == {("tisan", "package", "@babel/core"): "7.26.0",
                                                         ("tisan", "package", "next"): "15.1.0",
                                                         ("tisan", "package", "old-style"): "1.2.3",
                                                         ("tisan", "package", "react"): "19.0.0"}
    docker = "ARG PY=3.12.15\nFROM python:${PY}-slim AS build\nFROM node:22-alpine\nFROM scratch\n"
    found = by_key(inv.parse_dockerfile("rig", docker))
    assert found[("rig", "image", "python")] == "3.12.15-slim"
    assert found[("rig", "runtime", "python")] == "3.12.15"
    assert found[("rig", "runtime", "node")] == "22"


def test_scan_repo_reads_this_repo_without_network():
    items = inv.scan_repo(ROOT)
    keys = by_key(items)
    assert keys[("tank", "package", "fastapi")]
    assert any(c.app == "ghost" and c.kind == "image" for c in items)
    assert not any("node_modules" in c.app for c in items)


def test_headers_keep_only_server_and_powered_by():
    items = by_key(inv.header_components("coolify", "coolify.tervory.com",
                                         {"Server": "cloudflare", "X-Powered-By": "PHP/8.4.23", "CF-RAY": "abc",
                                          "Set-Cookie": "session=private"}))
    assert items[("coolify", "edge", "cloudflare")] == "current"
    assert items[("coolify", "runtime", "php")] == "8.4.23"
    assert "private" not in str(items)
    direct = by_key(inv.header_components("rig", "rig.tervory.com", {"Server": "nginx/1.27.3"}))
    assert direct[("rig", "edge", "direct")] == "current" and direct[("rig", "server_header", "nginx")] == "1.27.3"


@pytest.mark.asyncio
async def test_headers_only_from_our_own_sites():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("no call expected"))) as http:
        with pytest.raises(ValueError):
            await inv.fetch_headers(http, "x", "example.com")


@pytest.mark.asyncio
async def test_coolify_without_token_makes_no_call(monkeypatch):
    monkeypatch.delenv("COOLIFY_TOKEN_GHOST", raising=False)
    calls = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))) as http:
        assert await inv.fetch_coolify(http) is None
    assert calls == []


@pytest.mark.asyncio
async def test_coolify_is_read_only_and_token_never_stored(monkeypatch):
    sentinel = "sentinel-coolify-value-123"
    monkeypatch.setenv("COOLIFY_TOKEN_GHOST", sentinel)
    monkeypatch.setenv("COOLIFY_URL_GHOST", "https://coolify.example.test")
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/api/v1/applications":
            return httpx.Response(200, json=[{"name": "tervory-tank", "fqdn": "https://app.tervory.com",
                                              "docker_registry_image_name": "ghcr.io/berriai/litellm",
                                              "docker_registry_image_tag": "v1.106.0", "ports_mappings": "8080:80"}])
        if request.url.path == "/api/v1/services":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json="4.4.7")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        items = by_key(await inv.fetch_coolify(http))
    assert {r.method for r in seen} == {"GET"} and {r.url.host for r in seen} == {"coolify.example.test"}
    assert items[("coolify", "software", "coolify")] == "4.4.7"
    assert items[("tervory-tank", "domain", "app.tervory.com")] == "current"
    assert items[("tervory-tank", "port", "8080")] == "public"
    assert items[("tervory-tank", "software", "litellm")] == "1.106.0"
    assert sentinel not in str(items)
    monkeypatch.setenv("COOLIFY_URL_GHOST", "http://insecure.example.test")
    with pytest.raises(ValueError):
        inv.coolify_settings()


@pytest.fixture
def room(tmp_path, monkeypatch):
    monkeypatch.setenv("TANK_KEY", "ghost-test")
    app = create_app()
    store = Store(tmp_path / "ghost.sqlite3")
    app.state.store, app.state.advisory_lock = store, asyncio.Lock()
    yield app, store
    store.close()


@pytest.mark.asyncio
async def test_intake_needs_ghost_key_rejects_extras_and_replaces_snapshot(room):
    app, store = room
    before = json.loads((FIXTURES / "php2shell/inventory-before.json").read_text())
    after = json.loads(HOST_REPORT.read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ghost") as client:
        denied = await client.post("/ghost/inventory/report", json={"source": "host", "host_report": before})
        assert denied.status_code == 404
        key = {"X-Tank-Key": "ghost-test"}
        bad = await client.post("/ghost/inventory/report", headers=key,
                                json={"source": "host", "components": [], "secret": "private-value"})
        assert bad.status_code == 422 and "private-value" not in bad.text
        bad_source = await client.post("/ghost/inventory/report", headers=key, json={"source": "docker.sock", "host_report": before})
        assert bad_source.status_code == 422
        first = await client.post("/ghost/inventory/report", headers=key, json={"source": "host:host-a", "host_report": before})
        assert first.status_code == 200 and first.json()["current"] == 3
        second = await client.post("/ghost/inventory/report", headers=key, json={"source": "host:host-a", "host_report": after})
        assert second.status_code == 200 and second.json()["retired"] >= 2
        listed = (await client.get("/ghost/inventory", headers=key)).json()["components"]
        php = [c for c in listed if c["app"] == "coolify" and c["name"] == "php"]
        assert [c["version"] for c in php] == ["8.4.27"]
        history = (await client.get("/ghost/inventory", headers=key, params={"history": "true"})).json()["components"]
        assert {c["version"] for c in history if c["app"] == "coolify" and c["name"] == "php"} == {"8.4.23", "8.4.27"}
    assert store.inventory("another-tenant") == []


def test_inventory_is_tenant_scoped(tmp_path):
    store = Store(tmp_path / "g.sqlite3")
    try:
        store.replace_inventory(PLATFORM_TENANT, "host", [{"app": "a", "kind": "runtime", "name": "php", "version": "8.4.23"}], "t1")
        assert len(store.inventory(PLATFORM_TENANT)) == 1
        assert store.inventory("00000000-0000-0000-0000-000000000002") == []
        store.replace_inventory("00000000-0000-0000-0000-000000000002", "host", [], "t2")
        assert len(store.inventory(PLATFORM_TENANT)) == 1
    finally:
        store.close()


def test_compose_adds_names_only_and_keeps_the_seal():
    import yaml
    room = yaml.safe_load((ROOT / "agents/ghost/docker-compose.yml").read_text())
    env = room["services"]["agent-ghost"]["environment"]
    assert env["COOLIFY_TOKEN_GHOST"] == "${COOLIFY_TOKEN_GHOST:-}"
    assert env["COOLIFY_URL_GHOST"] == "${COOLIFY_URL_GHOST:-}"
    for service in room["services"].values():
        assert "ports" not in service and not service.get("privileged")
        assert not any("docker.sock" in str(v) for v in service.get("volumes", []))
        assert service["networks"] == ["gw"]
    assert "COOLIFY_TOKEN_GHOST_ACTIONS" not in str(room)
