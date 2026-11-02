"""Review of #506, self-review (b)/(c): a CLI credential reaches the CLI corridor only.

personal_tokens.register() replaces command.identity app-wide, and on ZA the CLI
talks to the public Tank directly. This walks every route on the real Tank app and
sends a well-formed CLI token: outside the corridor no token lookup may happen and no
route may answer differently from an anonymous request except with a refusal. Synthetic token, fake database, no network.
"""
from __future__ import annotations

import os
import re
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import httpx
import pytest
from fastapi.routing import APIRoute

import command
import main
import personal_tokens as pat

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000011")
SAMPLE = {"uuid.UUID": str(uuid.UUID(int=7))}
CORRIDOR = {
    ("GET", "/v1/command/models"), ("GET", "/v1/command/tools"), ("GET", "/v1/command/threads"),
    ("GET", "/v1/command/threads/{thread_id}"), ("GET", "/v1/command/threads/{thread_id}/events"),
    ("GET", "/v1/command/tasks/{task_id}/receipts"), ("POST", "/v1/command/threads"),
    ("POST", "/v1/command/threads/{thread_id}/turn"), ("POST", "/v1/command/threads/{thread_id}/actions"),
    ("POST", "/v1/command/cards/{card_id}"), ("POST", "/v1/command/build"), ("PATCH", "/v1/command/threads/{thread_id}"),
}

# Device-login routes authenticate the code, refresh token or presented credential
# themselves (tests/test_device_login.py); /revoke only revokes the token presented.
DEVICE = {("POST", "/v1/command/device/code"), ("POST", "/v1/command/device/token"),
          ("POST", "/v1/command/device/refresh"), ("POST", "/v1/command/device/revoke")}


def endpoints(routes=None, prefix=""):
    """Every (method, path) on the real app, through FastAPI's nested included routers."""
    for route in main.app.routes if routes is None else routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, prefix + route.path
        elif hasattr(route, "include_context"):
            context = route.include_context
            yield from endpoints(context.included_router.routes, prefix + context.prefix)


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.UUID(int=7)), path)


@pytest.fixture
def lookups(monkeypatch):
    seen = []

    class Conn:
        async def fetchrow(self, sql, *args):
            if "tank.personal_tokens" in sql:
                seen.append(sql)
                # A valid, unrevoked CLI credential for an ordinary member.
                return {"token_id": uuid.uuid4(), "user_id": "customer", "stale": False}
            raise AssertionError("no other database work past the corridor check")

        async def fetch(self, *_):
            return []

        async def fetchval(self, *_):
            return None

        async def execute(self, *_):
            return None

    @asynccontextmanager
    async def acquire():
        yield Conn()

    monkeypatch.setattr(command, "db", lambda: SimpleNamespace(acquire=acquire))
    monkeypatch.setattr(main, "box_region", lambda: "za")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder")
    return seen


def test_corridor_list_matches_the_workspace_proxy_plus_founder_roster():
    source = open("workspace/lib/tank.ts").read()
    assert "GET: new RegExp(`^(tools|threads|threads/${id}(/events)?|tasks/${id}/receipts)$`)" in source
    assert "POST: new RegExp(`^(threads|threads/${id}/(turn|actions)|cards/${id}|build)$`)" in source
    assert "PATCH: new RegExp(`^threads/${id}$`)" in source
    routes = set(endpoints())
    assert CORRIDOR <= routes
    for method, path in CORRIDOR:
        assert pat.cli_route(SimpleNamespace(method=method, url=SimpleNamespace(path=concrete(path))))


@pytest.mark.asyncio
async def test_every_tank_route_outside_the_cli_corridor_refuses_a_cli_token(lookups):
    token = f"tv1.za.{TENANT.hex}." + "x" * 43
    transport = httpx.ASGITransport(app=main.app, raise_app_exceptions=False)
    checked = []
    async with httpx.AsyncClient(transport=transport, base_url="http://za.tervory.com") as client:
        for method, path in sorted(set(endpoints())):
            if (method, path) in CORRIDOR or (method, path) in DEVICE:
                continue
            before = len(lookups)
            response = await client.request(method, concrete(path), json={},
                                            headers={"Authorization": f"Bearer {token}"})
            assert len(lookups) == before, (method, path)
            # The token adds nothing: the answer is a refusal, or exactly what the same
            # request gets with no credential at all (public routes such as /health).
            anonymous = await client.request(method, concrete(path), json={})
            if response.status_code != anonymous.status_code:
                assert response.status_code in {401, 403, 404}, (method, path, response.status_code)
            assert token not in response.text
            checked.append((method, path))
    # Includes the routes that use command.identity outside the corridor.
    paths = {p for _, p in checked}
    for path in ("/v1/command/squads", "/v1/command/repo/file", "/v1/command/attachments/{attachment_id}",
                 "/v1/command/threads/{thread_id}/attachments", "/v1/command/builds/{build_id}/followups",
                 "/v1/personal-tokens", "/v1/personal-tokens/{token_id}"):
        assert path in paths, path
    assert len(checked) > 50


@pytest.mark.asyncio
async def test_corridor_routes_do_look_the_token_up(lookups):
    token = f"tv1.za.{TENANT.hex}." + "x" * 43
    transport = httpx.ASGITransport(app=main.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://za.tervory.com") as client:
        response = await client.get("/v1/command/models", headers={"Authorization": f"Bearer {token}"})
    assert len(lookups) == 1
    assert response.status_code == 404  # a customer's token: the roster is founder-only
