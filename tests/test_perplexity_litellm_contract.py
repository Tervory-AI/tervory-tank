"""Optional gateway contract: install litellm[proxy] at litellm/Dockerfile's pin.

Run this file in an isolated environment with that release and pytest-asyncio.
Only the provider HTTP boundary is mocked; the proxy route, router, provider
transformation and response serialization are the installed LiteLLM code.
"""
from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path
import re

import httpx
import pytest
import yaml
from fastapi import FastAPI

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
litellm = pytest.importorskip("litellm", reason="run in isolated environment with deployed LiteLLM pin")

from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from litellm.proxy import proxy_server
from litellm.proxy.auth.user_api_key_auth import UserAPIKeyAuth, user_api_key_auth
from litellm.proxy.response_api_endpoints.endpoints import router as responses_router

ROOT = Path(__file__).resolve().parents[1]


def test_contract_uses_deployed_version():
    dockerfile = (ROOT / "litellm/Dockerfile").read_text()
    pin = re.search(r"FROM ghcr.io/berriai/litellm:v(\d+\.\d+\.\d+)", dockerfile)
    assert pin and importlib.metadata.version("litellm") == pin[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("preset", ["fast", "low", "medium", "high"])
@pytest.mark.parametrize("upstream_status", [200, 429])
async def test_proxy_preserves_preset_sources_costs_and_disables_fallbacks(monkeypatch, preset, upstream_status):
    config = yaml.safe_load((ROOT / "litellm/config.yaml").read_text())
    entries = [row for row in config["model_list"] if row["model_name"].startswith("research-")]
    for row in entries:
        row["litellm_params"]["api_key"] = "contract-fixture"
    fallbacks = [row for row in config["litellm_settings"]["fallbacks"] if next(iter(row)).startswith("research-")]
    gateway = litellm.Router(model_list=entries, num_retries=0, fallbacks=fallbacks)
    monkeypatch.setattr(proxy_server, "llm_router", gateway)
    seen = []

    async def provider_post(_self, url, **kwargs):
        payload = kwargs["json"]
        seen.append(payload)
        assert url == "https://api.perplexity.ai/v1/responses"
        assert payload["preset"] == preset
        assert "model" not in payload and "models" not in payload
        request = httpx.Request("POST", url)
        if upstream_status != 200:
            httpx.Response(upstream_status, json={"error": {"message": "fixture rate limit"}}, request=request).raise_for_status()
        return httpx.Response(200, request=request, json={
            "id": "resp_fixture", "object": "response", "created_at": 1, "status": "completed",
            "model": "preset/" + preset, "preset": preset,
            "output": [
                {"type": "search_results", "results": [
                    {"id": 7, "source": "web", "url": "https://example.org/source", "title": "Source"}]},
                {"type": "message", "role": "assistant", "id": "msg_fixture", "status": "completed",
                 "content": [{"type": "output_text", "text": "Answer [web:7]", "annotations": []}]},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
                      "cost": {"total_cost": 0.004, "tool_calls_cost": 0.001},
                      "tool_calls_details": {"search_web": {"invocation": 1}}},
        })

    monkeypatch.setattr(AsyncHTTPHandler, "post", provider_post)
    app = FastAPI(exception_handlers=dict(proxy_server.app.exception_handlers))
    app.include_router(responses_router)
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gateway") as client:
        response = await client.post("/v1/responses", json={
            "model": "research-" + preset, "input": "Public question", "max_output_tokens": 128,
            "stream": False, "fallbacks": [], "disable_fallbacks": True,
        })
    assert len(seen) == 1, response.text
    assert response.status_code == upstream_status, response.text
    if upstream_status == 200:
        data = response.json()
        assert data["output"][0]["results"][0]["id"] == 7
        assert data["output"][1]["content"][0]["text"] == "Answer [web:7]"
        assert data["usage"]["cost"] == 0.004
        assert data["usage"]["tool_calls_details"] == {"search_web": {"invocation": 1}}
    gateway.reset()
