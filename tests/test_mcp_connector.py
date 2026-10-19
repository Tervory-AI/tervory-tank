"""Claude connector: OAuth, the six tools, and tenant scoping. No network, no live keys."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

import httpx
from fastapi.testclient import TestClient

from connector.app import create_app
from connector.oauth import Settings, redirect_allowed
from connector.store import MemoryStore
from connector.tank import HttpTank, TankError
from connector.tenant import tenant_id_for
from connector.tokens import code_challenge, code_verifier, sign_access

ACCEPT = "application/json, text/event-stream"
CLAUDE = "https://claude.ai/api/mcp/auth_callback"
PUBLIC = "https://mcp.tervory.com"
RESOURCE = PUBLIC + "/mcp"
NAMESPACE = bytes.fromhex("7f3b1c2e9a4d4c1e8f2a5b6d7e8f9a0b")


def _reference_tenant(org_id: str) -> str:
    """Same UUID v5 the Workspace builds in tenant.ts, written out here on purpose."""
    digest = hashlib.sha1(NAMESPACE + org_id.encode("utf-8")).digest()
    raw = bytearray(digest[:16])
    raw[6] = (raw[6] & 0x0F) | 0x50
    raw[8] = (raw[8] & 0x3F) | 0x80
    text = raw.hex()
    return f"{text[:8]}-{text[8:12]}-{text[12:16]}-{text[16:20]}-{text[20:]}"


def _settings(**overrides: str) -> Settings:
    values = {
        "public_url": PUBLIC,
        "issuer": PUBLIC,
        "resource_url": RESOURCE,
        "tank_url": "http://tank.test",
        "tank_api_key": "dummy-tank-key",
        "clerk_secret_key": "dummy-clerk-secret",
        "clerk_frontend_api": "https://clerk.example.test",
        "clerk_oauth_client_id": "client-dummy",
        "clerk_oauth_client_secret": "dummy-oauth-secret",
        "signing_key": "dummy-signing-key-ok",
        "tenant_aliases": "org_new=org_old",
        "redis_url": "",
    }
    values.update(overrides)
    return Settings(**values)


class FakeTank:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        self.calls.append({"method": method, "path": path, "body": body, "params": params})
        if path.endswith("/zenas.scope/run"):
            text = str((body or {}).get("input", {}).get("text") or "")
            if "theft" in text.casefold():
                return {
                    "in_scope": False,
                    "criminal": True,
                    "jurisdiction": "us",
                    "area": "",
                    "reason": "Criminal law is not offered.",
                    "model": "flash-lite",
                    "_cost_usd": 0.001,
                }
            return {
                "in_scope": True,
                "criminal": False,
                "jurisdiction": "za",
                "area": "company",
                "reason": "In scope.",
                "model": "flash-lite",
                "_cost_usd": 0.001,
            }
        if path.endswith("/zenas.retrieve/run"):
            return {
                "passages": [{"citation": "Companies Act 71 of 2008 s 1", "text": "A company is ...", "heading": "Definitions"}],
                "model": "code",
                "_cost_usd": 0,
            }
        if path == "/v1/route":
            return {
                "model": "sonar",
                "content": "CLAIM: Widget demand rose\nURL: https://example.com/brief\nDATE: 2026-04-01\n",
                "cost_usd": 0.02,
            }
        if path == "/v1/base/records":
            return [
                {
                    "id": "rec-1",
                    "batch": "batch-a",
                    "status": "done",
                    "confidence": 0.9,
                    "profile": {"site": {"value": "https://example.com", "source": "https://example.com"}},
                }
            ]
        if path == "/v1/base/run":
            return {"task": {"id": "task-1"}, "records": len((body or {}).get("records") or [])}
        if path == "/v1/tiger/watchlist":
            sent = body or {}
            return {"id": "watch-1", "url": sent.get("url"), "label": sent.get("label"), "every": sent.get("every")}
        return {"results": [{"id": "sku-1", "name": "Brass widget"}], "model": "code", "_cost_usd": 0}


def _app(tank: FakeTank | None = None, **overrides: str):
    return create_app(settings=_settings(**overrides), store=MemoryStore(), tank=tank or FakeTank())


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}", "accept": ACCEPT}


def _token(org_id: str, *, aliases: str = "org_new=org_old", user_id: str = "user_one") -> str:
    tenant = tenant_id_for(org_id, aliases)
    return sign_access(
        secret="dummy-signing-key-ok",
        issuer=PUBLIC,
        audience=RESOURCE,
        user_id=user_id,
        org_id=org_id,
        tenant_id=tenant,
    )


def _rpc(client: TestClient, token: str, method: str, params: dict[str, Any] | None = None, request_id: int = 1):
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", headers=_headers(token), json=body)


def _result(response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "error" not in payload, payload
    return payload["result"]


def test_uuid_matches_the_workspace_rule() -> None:
    assert tenant_id_for("org_old") == _reference_tenant("org_old")
    assert tenant_id_for("org_new", "org_new=org_old") == _reference_tenant("org_old")
    assert tenant_id_for("org_new") != tenant_id_for("org_new", "org_new=org_old")


def test_missing_token_is_401_with_resource_metadata() -> None:
    with TestClient(_app()) as client:
        denied = client.post("/mcp", headers={"accept": ACCEPT}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert denied.status_code == 401
    header = denied.headers["www-authenticate"]
    assert 'resource_metadata="https://mcp.tervory.com/.well-known/oauth-protected-resource/mcp"' in header
    assert "scope=" in header
    assert "dummy" not in header


def test_token_in_the_query_is_refused() -> None:
    token = _token("org_old")
    with TestClient(_app()) as client:
        denied = client.post("/mcp?access_token=present", headers=_headers(token), json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert denied.status_code == 401


def test_discovery_lists_this_server_and_public_clients() -> None:
    with TestClient(_app()) as client:
        resource = client.get("/.well-known/oauth-protected-resource/mcp")
        server = client.get("/.well-known/oauth-authorization-server")
    assert resource.status_code == 200
    assert resource.json()["resource"] == RESOURCE
    assert resource.json()["authorization_servers"] == [PUBLIC]
    assert resource.json()["bearer_methods_supported"] == ["header"]
    meta = server.json()
    assert meta["registration_endpoint"] == PUBLIC + "/register"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["token_endpoint_auth_methods_supported"] == ["none"]
    assert "offline_access" in meta["scopes_supported"]
    assert "client_credentials" not in meta["grant_types_supported"]


def test_loopback_ignores_port_and_treats_both_hosts_as_one() -> None:
    registered = ["http://localhost/callback"]
    assert redirect_allowed("http://127.0.0.1:3118/callback", registered)
    assert redirect_allowed("http://localhost:9/callback", registered)
    assert not redirect_allowed("http://localhost:3118/other", registered)
    assert not redirect_allowed("https://claude.ai.evil.example/api/mcp/auth_callback", [CLAUDE])
    assert redirect_allowed(CLAUDE, [CLAUDE])


def test_register_rejects_a_foreign_redirect_and_machine_tokens() -> None:
    with TestClient(_app()) as client:
        foreign = client.post("/register", json={"redirect_uris": ["https://evil.example/callback"]})
        machine = client.post("/register", json={"redirect_uris": [CLAUDE], "grant_types": ["client_credentials"]})
        secret = client.post("/register", json={"redirect_uris": [CLAUDE], "token_endpoint_auth_method": "client_secret_basic"})
    assert foreign.status_code == 400
    assert machine.status_code == 400
    assert secret.status_code == 400


def test_oauth_code_exchange_and_refresh_rotation(monkeypatch) -> None:
    async def fake_identity(http, settings, code, verifier):
        del http, code, verifier
        return {
            "user_id": "user_review",
            "org_id": "org_new",
            "tenant_id": tenant_id_for("org_new", settings.tenant_aliases),
        }

    monkeypatch.setattr("connector.oauth._clerk_identity", fake_identity)
    verifier = code_verifier()
    with TestClient(_app()) as client:
        registered = client.post("/register", json={"redirect_uris": [CLAUDE, "http://127.0.0.1/callback"], "client_name": "Claude"})
        assert registered.status_code == 201
        client_id = registered.json()["client_id"]
        assert "client_secret" not in registered.json()
        page = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": CLAUDE,
                "state": "client-state",
                "code_challenge": code_challenge(verifier),
                "code_challenge_method": "S256",
                "resource": RESOURCE,
            },
        )
        assert page.status_code == 200
        assert "claude.ai" in page.text
        txn = re.search(r'name="txn" value="([^"]+)"', page.text)
        assert txn is not None
        continued = client.post("/authorize/continue", data={"txn": txn.group(1)}, follow_redirects=False)
        assert continued.status_code == 302
        clerk = continued.headers["location"]
        assert clerk.startswith("https://clerk.example.test/oauth/authorize?")
        assert "client_secret" not in clerk
        assert "dummy-oauth-secret" not in clerk
        callback = client.get("/oauth/clerk/callback", params={"code": "from-idp", "state": txn.group(1)}, follow_redirects=False)
        assert callback.status_code == 302
        back = parse_qs(urlparse(callback.headers["location"]).query)
        assert back["state"] == ["client-state"]
        exchanged = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": back["code"][0],
                "redirect_uri": CLAUDE,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": RESOURCE,
            },
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert exchanged.status_code == 200, exchanged.text
        issued = exchanged.json()
        assert issued["token_type"] == "Bearer"
        assert issued["refresh_token"]
        reused = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": back["code"][0],
                "redirect_uri": CLAUDE,
                "client_id": client_id,
                "code_verifier": verifier,
            },
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert reused.status_code == 400
        assert reused.json()["error"] == "invalid_grant"
        wrong = client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": issued["refresh_token"],
                "client_id": client_id,
                "code_verifier": "not-the-verifier",
            },
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        # Refresh does not use the code verifier. A wrong one must not block rotation.
        assert wrong.status_code == 200
        rotated = wrong.json()
        assert rotated["refresh_token"] != issued["refresh_token"]
        replay = client.post(
            "/token",
            data={"grant_type": "refresh_token", "refresh_token": issued["refresh_token"], "client_id": client_id},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert replay.status_code == 400
        assert replay.json()["error"] == "invalid_grant"
        stolen = client.post(
            "/token",
            data={"grant_type": "refresh_token", "refresh_token": rotated["refresh_token"], "client_id": client_id},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert stolen.status_code == 400
        listed = _result(client.post("/mcp", headers=_headers(issued["access_token"]), json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
    names = [tool["name"] for tool in listed["tools"]]
    assert names == ["rig_search", "base_lookup", "base_enrich", "zenas_research", "market_lab_brief", "tiger_watch"]


def test_wrong_pkce_verifier_is_invalid_grant(monkeypatch) -> None:
    async def fake_identity(http, settings, code, verifier):
        del http, code, verifier
        return {"user_id": "user_review", "org_id": "org_old", "tenant_id": tenant_id_for("org_old", settings.tenant_aliases)}

    monkeypatch.setattr("connector.oauth._clerk_identity", fake_identity)
    verifier = code_verifier()
    with TestClient(_app()) as client:
        client_id = client.post("/register", json={"redirect_uris": [CLAUDE]}).json()["client_id"]
        page = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": CLAUDE,
                "state": "s",
                "code_challenge": code_challenge(verifier),
                "code_challenge_method": "S256",
            },
        )
        txn = re.search(r'name="txn" value="([^"]+)"', page.text).group(1)
        client.get("/oauth/clerk/callback", params={"code": "from-idp", "state": txn}, follow_redirects=False)
        # The callback above consumed the transaction. Start again for the bad verifier.
        page = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": CLAUDE,
                "state": "s2",
                "code_challenge": code_challenge(verifier),
                "code_challenge_method": "S256",
            },
        )
        txn = re.search(r'name="txn" value="([^"]+)"', page.text).group(1)
        back = client.get("/oauth/clerk/callback", params={"code": "from-idp", "state": txn}, follow_redirects=False)
        code = parse_qs(urlparse(back.headers["location"]).query)["code"][0]
        denied = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CLAUDE,
                "client_id": client_id,
                "code_verifier": code_verifier(),
            },
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    assert denied.status_code == 400
    assert denied.json()["error"] == "invalid_grant"


def test_tools_have_titles_and_one_hint_each() -> None:
    token = _token("org_old")
    with TestClient(_app()) as client:
        tools = _result(_rpc(client, token, "tools/list"))["tools"]
    assert len(tools) == 6
    for tool in tools:
        assert len(tool["name"]) <= 64
        assert tool["title"]
        assert tool["description"]
        hints = tool["annotations"]
        assert hints["title"] == tool["title"]
        assert (hints.get("readOnlyHint") is True) ^ (hints.get("destructiveHint") is True)
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["rig_search"]["title"] == "Search a catalogue"
    assert by_name["rig_search"]["annotations"]["readOnlyHint"] is True
    assert by_name["base_lookup"]["title"] == "Look up records"
    assert by_name["base_lookup"]["annotations"]["readOnlyHint"] is True
    assert by_name["base_enrich"]["title"] == "Enrich a list"
    assert by_name["base_enrich"]["annotations"]["destructiveHint"] is True
    assert by_name["zenas_research"]["title"] == "Research a legal question"
    assert by_name["zenas_research"]["annotations"]["readOnlyHint"] is True
    assert by_name["market_lab_brief"]["title"] == "Write a market brief"
    assert by_name["market_lab_brief"]["annotations"]["readOnlyHint"] is True
    assert by_name["tiger_watch"]["title"] == "Watch a price"
    assert by_name["tiger_watch"]["annotations"]["destructiveHint"] is True


def _call(client: TestClient, token: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _result(_rpc(client, token, "tools/call", {"name": name, "arguments": arguments}))
    body = json.loads(result["content"][0]["text"])
    body["_is_error"] = result["isError"]
    return body


def test_each_tool_is_scoped_to_the_callers_tenant() -> None:
    tank = FakeTank()
    old = _reference_tenant("org_old")
    other = _reference_tenant("org_other")
    assert tenant_id_for("org_new", "org_new=org_old") == old
    with TestClient(_app(tank)) as client:
        search = _call(client, _token("org_new"), "rig_search", {"query": "brass", "limit": 3})
        lookup = _call(client, _token("org_other", aliases=""), "base_lookup", {"query": "example", "batch": "batch-a"})
        enrich = _call(client, _token("org_old"), "base_enrich", {"records": [{"name": "Ada"}]})
        legal = _call(client, _token("org_old"), "zenas_research", {"question": "What is a company?", "jurisdiction": "SA"})
        brief = _call(client, _token("org_old"), "market_lab_brief", {"topic": "brass widgets"})
        watch = _call(client, _token("org_old"), "tiger_watch", {"url": "https://example.com/widget", "label": "Widget", "every": "1d", "threshold_percent": 5})
    assert search["_is_error"] is False
    assert search["model"] == "code"
    assert search["cost_usd"] == 0
    assert search["sources"][0]["title"] == "Brass widget"
    assert lookup["records"][0]["id"] == "rec-1"
    assert lookup["sources"][0]["detail"] == "https://example.com"
    assert enrich["batch_id"]
    assert enrich["task_id"] == "task-1"
    assert legal["sources"][0]["title"] == "Companies Act 71 of 2008 s 1"
    assert "Companies Act" in legal["answer"]
    assert brief["sources"] == [{"title": "Widget demand rose", "url": "https://example.com/brief", "detail": "2026-04-01"}]
    assert brief["model"] == "sonar"
    assert brief["cost_usd"] == 0.02
    assert watch["id"] == "watch-1"
    tenants = []
    paths = []
    for call in tank.calls:
        paths.append(call["path"])
        if call["body"] is not None:
            tenants.append(call["body"]["tenant_id"])
        if call["params"] is not None:
            tenants.append(call["params"]["tenant_id"])
    assert set(tenants) == {old, other}
    assert paths == [
        "/v1/skala/rig.search/run",
        "/v1/base/records",
        "/v1/base/run",
        "/v1/skala/zenas.scope/run",
        "/v1/skala/zenas.retrieve/run",
        "/v1/route",
        "/v1/tiger/watchlist",
    ]
    rig = tank.calls[0]["body"]
    assert rig["tenant_id"] == old
    assert rig["input"]["tenant_id"] == old
    assert rig["input"]["q"] == "brass"
    assert tank.calls[1]["params"]["tenant_id"] == other
    assert tank.calls[2]["body"]["tenant_id"] == old
    assert tank.calls[2]["body"]["created_by"] == "user_one"
    assert tank.calls[3]["body"]["input"]["jurisdiction"] == "za"
    route = tank.calls[5]["body"]
    assert route["tenant_id"] == old
    assert route["agent"] == "market_lab"
    assert route["task_type"] == "market.research"
    tiger = tank.calls[6]["body"]
    assert tiger["tenant_id"] == old
    assert tiger["threshold"] == 0.05
    assert tiger["every"] == "1d"
    assert tiger["enabled"] is True


def test_criminal_research_stops_before_retrieval() -> None:
    tank = FakeTank()
    with TestClient(_app(tank)) as client:
        body = _call(client, _token("org_old"), "zenas_research", {"question": "Defend a theft charge", "jurisdiction": "us"})
    assert body["_is_error"] is False
    assert body["scope"]["criminal"] is True
    assert body["passages"] == []
    assert body["answer"] == "Criminal law is not offered."
    assert [call["path"] for call in tank.calls] == ["/v1/skala/zenas.scope/run"]
    assert tank.calls[0]["body"]["tenant_id"] == _reference_tenant("org_old")


def test_bad_input_does_not_call_tank() -> None:
    tank = FakeTank()
    rows = [{"name": str(i)} for i in range(101)]
    with TestClient(_app(tank)) as client:
        token = _token("org_old")
        empty = _call(client, token, "rig_search", {"query": "  "})
        huge = _call(client, token, "base_enrich", {"records": rows})
        local = _call(client, token, "tiger_watch", {"url": "http://127.0.0.1/secret"})
        plain = _rpc(client, token, "tools/call", {"name": "missing", "arguments": {}})
    assert empty["_is_error"] is True
    assert huge["_is_error"] is True
    assert "100" in huge["message"]
    assert local["_is_error"] is True
    assert tank.calls == []
    missing = json.loads(_result(plain)["content"][0]["text"])
    assert missing["ok"] is False


def test_a_token_for_another_audience_or_tenant_is_refused() -> None:
    wrong_tenant = sign_access(
        secret="dummy-signing-key-ok",
        issuer=PUBLIC,
        audience=RESOURCE,
        user_id="user_one",
        org_id="org_new",
        tenant_id=_reference_tenant("org_other"),
    )
    other_audience = sign_access(
        secret="dummy-signing-key-ok",
        issuer=PUBLIC,
        audience="https://mcp.tervory.com/other",
        user_id="user_one",
        org_id="org_old",
        tenant_id=_reference_tenant("org_old"),
    )
    with TestClient(_app()) as client:
        mismatched = client.post("/mcp", headers=_headers(wrong_tenant), json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        foreign = client.post("/mcp", headers=_headers(other_audience), json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        evil = client.post(
            "/mcp",
            headers={**_headers(_token("org_old")), "origin": "https://evil.example"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
    assert mismatched.status_code == 401
    assert foreign.status_code == 401
    assert evil.status_code == 403


def test_tank_errors_do_not_repeat_credential_words() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["header"] = request.headers.get("x-tank-key", "")
        return httpx.Response(401, json={"detail": "authorization was rejected"})

    async def run() -> str:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            tank = HttpTank("http://tank.test", "dummy-tank-key", http)
            try:
                await tank.call("GET", "/v1/base/records", params={"tenant_id": "x"})
            except TankError as exc:
                return exc.detail
        return ""

    assert asyncio.run(run()) == "Tank refused the call."
    assert seen["header"] == "dummy-tank-key"


def test_tool_logs_omit_the_tank_key(caplog) -> None:
    del caplog
    marker = "dummy-tank-key"
    sink: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            sink.append(record.getMessage())

    log = logging.getLogger("tervory.mcp")
    handler = Grab()
    log.addHandler(handler)
    try:
        with TestClient(_app(FakeTank(), tank_api_key=marker)) as client:
            _call(client, _token("org_old"), "rig_search", {"query": "brass"})
    finally:
        log.removeHandler(handler)
    assert sink
    assert marker not in "\n".join(sink)


def test_listing_files_use_the_real_mark_and_name_support() -> None:
    logo = (ROOT / "workspace/public/brand/tervory-logo.png").read_bytes()
    icon = (ROOT / "docs/mcp/icon.png").read_bytes()
    assert icon == logo
    assert icon.startswith(b"\x89PNG")
    page = (ROOT / "docs/mcp/index.html").read_text(encoding="utf-8")
    privacy = (ROOT / "docs/mcp/privacy.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs/mcp/reviewer.md").read_text(encoding="utf-8")
    for name in ("rig_search", "base_lookup", "base_enrich", "zenas_research", "market_lab_brief", "tiger_watch"):
        assert name in page
    assert "support@tervory.com" in page
    assert "support@tervory.com" in privacy
    assert "https://mcp.tervory.com/mcp" in page
    lowered = privacy.casefold()
    for word in ("collect", "storage", "third", "retention", "contact"):
        assert word in lowered
    assert "founder" in guide.casefold()
    assert "sk_" not in guide and "sk_" not in page
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    block = compose.split("  mcp:\n", 1)[1].split("\nvolumes:", 1)[0]
    assert "tervory-gw" not in block
    assert "- default" in block
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("MCP_PUBLIC_URL", "CLERK_FRONTEND_API", "CLERK_OAUTH_CLIENT_ID", "CLERK_OAUTH_CLIENT_SECRET", "MCP_TOKEN_SIGNING_KEY"):
        assert name in example
