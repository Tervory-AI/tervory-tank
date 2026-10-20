"""A room key or a customer id must never reach the founder approval proxy."""
import secrets

from fastapi.testclient import TestClient
import httpx


def test_proxy_checks_founder_before_contacting_room(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("LITELLM_URL", "http://localhost:4000")
    workspace_key, room_key = secrets.token_hex(24), secrets.token_hex(24)
    monkeypatch.setenv("LITELLM_MASTER_KEY", secrets.token_hex(24))
    monkeypatch.setenv("TANK_API_KEY", workspace_key)
    import tank.main as main
    monkeypatch.setattr(main, "TANK_API_KEY", workspace_key)
    monkeypatch.setenv("TANK_API_KEY", workspace_key)
    monkeypatch.setenv("TANK_KEY_TISAN", room_key)
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-user")
    calls = []

    class HTTP:
        async def request(self, method, target, **kwargs):
            calls.append((method, target, kwargs))
            return httpx.Response(200, json=[])

    monkeypatch.setattr(main, "_http", HTTP())
    client = TestClient(main.app)
    path = "/v1/tisan/gold/pages?tenant_id=00000000-0000-0000-0000-000000000001"
    for key, user in ((room_key, "founder-user"), (workspace_key, "customer")):
        assert client.get(path, headers={"X-Tank-Key": key, "X-Tervory-Admin": user}).status_code in (401, 404)
    assert calls == []
    assert client.get(path, headers={"X-Tank-Key": workspace_key, "X-Tervory-Admin": "founder-user"}).status_code == 200
    assert calls[0][1] == "http://agent-tisan:8000/gold/pages"
    assert calls[0][2]["headers"]["X-Tank-Key"] == room_key
