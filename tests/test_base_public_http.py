"""Offline public-page policy tests using actual HTTPX requests and Base skills."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import uuid

from fastapi import FastAPI
import httpx
import pytest

import agent_skills
import base_public_http as public
import skala

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def quick_pace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public, "HOST_INTERVAL", 0)


@pytest.mark.asyncio
async def test_one_truthful_identity_and_public_cookies_never_forwarded() -> None:
    seen: list[httpx.Request] = []

    def site(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="Public shop: product price $10.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(site), cookies={"session": "offline-fixture"}) as client:
        boundary = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        result = await boundary.get("https://shop.example/products", headers={"user-agent": "Mozilla/5.0", "Authorization": "fixture"})
    assert result.status_code == 200
    assert seen[0].headers["user-agent"] == public.USER_AGENT
    assert "cookie" not in seen[0].headers and "authorization" not in seen[0].headers
    assert [str(request.url) for request in seen] == ["https://shop.example/products"]  # no robots lookup


@pytest.mark.asyncio
async def test_host_pacing_shared_across_tenants_and_parallel_skill_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public, "HOST_INTERVAL", 0.04)
    times: dict[str, list[float]] = {}

    async def site(request: httpx.Request) -> httpx.Response:
        times.setdefault(request.url.host, []).append(asyncio.get_running_loop().time())
        await asyncio.sleep(0.01)
        return httpx.Response(200, text="Public business")

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        one = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        two = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        await asyncio.gather(one.get("https://shop.example/a"), two.get("https://shop.example/b"),
                             one.get("https://other.example/"))
    assert times["shop.example"][1] - times["shop.example"][0] >= 0.045
    assert times["other.example"][0] < times["shop.example"][1]


@pytest.mark.parametrize(("status", "html"), [
    (403, "Forbidden"), (429, "Slow down"), (401, "Sign in"), (402, "Subscribe"),
    (200, '<div class="cf-turnstile">Verify you are human</div>'),
    (200, '<input type="password">Sign in to continue'),
    (200, '<script type="application/ld+json">{"isAccessibleForFree":false}</script>'),
    (200, "Subscribe to read this article"),
])
@pytest.mark.asyncio
async def test_block_stops_get_browser_and_future_calls_for_same_tenant(status: int, html: str) -> None:
    seen: list[str] = []
    tenant = uuid.uuid4()

    def site(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(status, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        boundary = agent_skills.BaseSkillHTTP(client, tenant, None)
        assert (await boundary.get("https://shop.example/contact")).status_code == 403
        assert (await boundary.post(public.BROWSER_RENDER, json={"url": "https://shop.example/contact"})).json()["challenge"]
        await boundary.get("https://another-host.example/alternative")
        later = agent_skills.BaseSkillHTTP(client, tenant, uuid.uuid4())
        assert (await later.get("http://www.shop.example/another-path")).status_code == 403
    assert seen == ["https://shop.example/contact"]


@pytest.mark.asyncio
async def test_redirects_are_checked_and_cannot_switch_back_after_a_block() -> None:
    seen: list[str] = []

    def site(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert request.headers["user-agent"] == public.USER_AGENT
        if request.url.host == "shop.example":
            return httpx.Response(302, headers={"location": "https://blocked.example/check"})
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        boundary = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        assert (await boundary.get("https://shop.example/", follow_redirects=True)).status_code == 403
        await boundary.get("https://shop.example/contact")
        await boundary.post(public.BROWSER_RENDER, json={"url": "https://blocked.example/check"})
    assert seen == ["https://shop.example/", "https://blocked.example/check"]


@pytest.mark.asyncio
async def test_login_redirect_is_never_followed_and_query_is_not_recorded() -> None:
    seen: list[str] = []

    def site(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(302, headers={"location": "/login?continue=fixture"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        boundary = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        result = await boundary.get("https://shop.example/account", follow_redirects=True)
    assert seen == ["/account"]
    assert result.json()["url"] == "https://shop.example/login"


@pytest.mark.asyncio
async def test_browser_block_is_recorded_and_isolated_from_other_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def site(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"challenge": True, "url": "https://shop.example/", "status": 403})

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        one = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        other = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None)
        blocked = await one.post(public.BROWSER_RENDER, json={"url": "https://shop.example/"})
        assert blocked.json()["status"] == "blocked"
        await one.get("https://shop.example/")
        await other.post(public.BROWSER_RENDER, json={"url": "https://shop.example/"})
    assert len(seen) == 2
    assert all(request.headers["user-agent"] == public.USER_AGENT for request in seen)
    assert seen[0].headers["x-tenant-id"] != seen[1].headers["x-tenant-id"]


@pytest.mark.asyncio
async def test_existing_search_service_contract_is_preserved() -> None:
    seen: list[httpx.Request] = []

    def search(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(search)) as client:
        boundary = agent_skills.BaseSkillHTTP(client, uuid.uuid4(), None, ("http://searxng:8080",))
        assert (await boundary.get("http://searxng:8080/search", params={"q": "public shop"})).json() == {"results": []}
    assert seen[0].url.params["q"] == "public shop"
    assert seen[0].headers["user-agent"] == public.USER_AGENT


@pytest.mark.asyncio
async def test_approved_scrape_block_survives_into_pipeline_row_without_archive_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Real approved code, ASGI response hook, room client and enrichment pipeline;
    # only network and registry storage are fixtures. This is not live proof.
    monkeypatch.syspath_prepend(str(ROOT / "agents/base"))
    import pipeline
    import room

    path = ROOT / "tank/skills/base.scrape_site/1.2.0"
    pkg = skala._parse_package(path / "skill.yaml", path)
    find_path = ROOT / "tank/skills/base.find_site/1.7.0"
    finder = skala._parse_package(find_path / "skill.yaml", find_path)
    calls: list[str] = []

    def site(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/":
            return httpx.Response(200, text='<a href="/contact">Contact</a>' + "Public business details. " * 50,
                                  headers={"content-type": "text/html"})
        return httpx.Response(403)

    class Pool:
        @asynccontextmanager
        async def acquire(self) -> Any:
            yield self

        async def fetchrow(self, *_args: Any) -> None:
            return None

    async def approved(*_args: Any) -> str:
        return "approved"

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as upstream:
        app = FastAPI()
        tank = SimpleNamespace(app=app, pool=Pool, box_region=lambda: "us-east", skill_state=approved)
        app.include_router(agent_skills.build_router(tank))

        @app.post("/v1/skala/{skill}/run")
        async def run(skill: str, body: dict[str, Any]) -> dict[str, Any]:
            package = finder if skill == "base.find_site" else pkg
            ctx = SimpleNamespace(http=upstream, env={}, task_id=None)
            req = SimpleNamespace(tenant_id=uuid.UUID(body["tenant_id"]), home_region="us-east", preview=False, input=body["input"])
            await agent_skills.guard_base_run(tank, package, req, ctx)
            return await skala.run_skill(package, req.input, ctx)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank") as api:
            call = room.SkillClient(api, "http://tank", "offline-fixture").bind({"base.scrape_site": "1.2.0"}, False, str(uuid.uuid4()))
            result = await call("base.scrape_site", {"website": "https://shop.example/"})
            assert result["error"] == "blocked" and result["text"] == "" and result["pages"] == []
            assert result["access_error"] == {"status": "blocked", "url": "https://shop.example/contact",
                                               "reason": "http_403", "next": "client_connection"}

            async def steps(skill: str, payload: dict[str, Any]) -> dict[str, Any]:
                if skill == "base.normalize":
                    return {"fields": {"name": {"value": "Public business", "source": "input", "confidence": 100}}}
                if skill == "base.find_site":
                    return {"website": {"value": "https://shop.example/", "source": "input:verified", "confidence": 85}}
                if skill == "base.scrape_site":
                    return result
                if skill == "base.verify":
                    return {"confidence": 0, "checks": {}}
                return {}

            outcome = await pipeline.enrich_one({"name": "Public business"}, None, [], None, steps)
            assert outcome.passes["2b"]["error"] == "blocked"
            assert outcome.passes["2b"]["access_error"]["url"] == "https://shop.example/contact"
            assert "gold_observation" not in outcome.passes["2b"]

            async def find_for(tenant: uuid.UUID, target: str) -> dict[str, Any]:
                find = room.SkillClient(api, "http://tank", "offline-fixture").bind({"base.find_site": "1.7.0"}, False, str(tenant))
                return await find("base.find_site", {"name": "Public Business", "website": target})

            targets = ["https://shop.example/restricted", "https://other.example/restricted"]
            found = await asyncio.gather(*(find_for(uuid.uuid4(), target) for target in targets))
            for item, target in zip(found, targets):
                assert item["blocked_by_check"] == [target]
                assert item["website"]["value"] is None
    assert calls[:2] == ["https://shop.example/", "https://shop.example/contact"]
    assert set(calls[2:]) == {"https://shop.example/restricted", "https://other.example/restricted"}
    assert len(calls) == 4  # no search, guesses, browser, archive or retry after a block
