"""Offline execution of the unchanged skills through preview, eval and room paths."""
from contextlib import asynccontextmanager
from dataclasses import replace
import json
import os
from types import SimpleNamespace
import uuid

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")
import main
import agent_skills
import base_public_http
import skala


class Connection:
    async def execute(self, *args):
        return "OK"

    async def fetchval(self, *args):
        return "candidate"


class Pool:
    @asynccontextmanager
    async def acquire(self):
        yield Connection()


@pytest.mark.asyncio
@pytest.mark.parametrize("skill,version,payload", [
    ("base.scrape_site", "1.3.0", {"website": "https://routing.example"}),
    ("base.find_site", "1.7.1", {"name": "Routing Observatory", "website": "https://routing.example"}),
])
@pytest.mark.parametrize("mode", ["preview", "evals", "base"])
async def test_base_render_stays_in_its_room(monkeypatch, skill, version, payload, mode):
    pkg = skala.load_packages()[(skill, version)]
    seen = []
    tenant = uuid.uuid4()
    task = uuid.uuid4()
    html = "<html><body>Routing Observatory public business contact hello@routing.example</body></html>"

    def transport(request):
        seen.append(request)
        if request.method == "POST":
            assert str(request.url) == "http://base-browser-gateway:3000/render"
            assert request.headers["X-Tenant-ID"] == str(main.PLATFORM_TENANT if mode == "evals" else tenant)
            assert request.headers["X-Home-Region"] == "us-east"
            assert request.headers["X-Tank-Key"] == "offline-base-placeholder"
            if mode == "base":
                assert request.headers["X-Task-ID"] == str(task)
            return httpx.Response(200, json={"ok": True, "html": html, "text": "Routing Observatory", "title": "Routing Observatory", "final_url": "https://routing.example", "status": 200})
        raise httpx.ReadTimeout("offline slow page", request=request)

    async def noop(*args, **kwargs):
        return None

    async def state(*args):
        return "approved" if mode == "base" else "candidate"

    async def policy(*args):
        return {"priority": "standard"}

    async def receipt(*args, **kwargs):
        return SimpleNamespace(ledger_id=uuid.uuid4(), model_dump=lambda **kw: {})

    monkeypatch.setenv("TANK_KEY_BASE", "offline-base-placeholder")
    monkeypatch.setattr(base_public_http, "HOST_INTERVAL", 0)
    monkeypatch.setattr(main, "SKILL_ENV", {"TIGER_URL": "http://tiger-ocr:3000"})
    monkeypatch.setattr(main, "get_package", lambda *args: pkg)
    monkeypatch.setattr(main, "skill_state", state)
    monkeypatch.setattr(main, "load_policy", policy)
    monkeypatch.setattr(main, "_preflight_mask", noop)
    monkeypatch.setattr(main, "_record_local", receipt)
    monkeypatch.setattr(main, "pool", lambda: Pool())
    monkeypatch.setattr(agent_skills, "guard_submission_owner", noop)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        monkeypatch.setattr(main, "_http", client)
        if mode == "evals":
            pkg = replace(pkg, cases=[{"name": "browser routing", "input": payload, "expected": {}}])
            result = await main.run_skill_evals(skill, version)
            assert result["passed"] == 1, result
        else:
            body = main.SkillRun(tenant_id=tenant, input={**payload, **({"_base_brain_task": str(task)} if mode == "base" else {})}, version=version, preview=mode == "preview")
            await main._run_one_skill(skill, body, "base" if mode == "base" else None)
    assert any(request.method == "POST" for request in seen)
    assert all(request.url.host != "tiger-ocr" for request in seen)


@pytest.mark.asyncio
async def test_ocr_unchanged_png_cases_use_ocr_corridor(monkeypatch):
    pkg = skala.load_packages()[("tiger.price_ocr", "1.0.1")]
    seen = []
    def transport(request):
        seen.append(request)
        assert str(request.url) == "http://tiger-ocr:3000/ocr"
        assert "png_base64" in json.loads(request.content)
        return httpx.Response(200, json={"text": "Routing Item $12.50"})
    monkeypatch.setattr(main, "SKILL_ENV", {"TIGER_URL": "http://tiger-ocr:3000"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        monkeypatch.setattr(main, "_http", client)
        out = await skala.run_skill(pkg, {"png_base64": "offline", "url": "https://routing.example"}, main.make_ctx(pkg, uuid.uuid4()))
    assert seen and out["items"][0]["price"] == "12.50"
