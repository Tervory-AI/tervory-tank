"""Tank lists the models LiteLLM serves, with prices, and never a key. No database, no network."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import httpx

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

SERVED = {
    "data": [
        {
            "model_name": "sol",
            "litellm_params": {"model": "openai/gpt-6-sol", "api_key": "sk-should-never-leave-tank"},
            "model_info": {"input_cost_per_token": 0.000002, "output_cost_per_token": 0.00001},
        },
        {
            "model_name": "luna",
            "litellm_params": {"model": "openai/gpt-6-luna", "api_key": "os.environ/OPENAI_API_KEY"},
            "model_info": {"input_cost_per_token": 0.0000001, "output_cost_per_token": 0.0000005},
        },
        {"model_name": "luna", "litellm_params": {"model": "openai/gpt-6-luna-fallback"}, "model_info": {}},
        {"model_name": "mystery", "litellm_params": {"model": "x/unknown"}, "model_info": {}},
    ]
}


class LiteLLM:
    def __init__(self, status: int = 200, payload: object = SERVED, down: bool = False) -> None:
        self.status, self.payload, self.down = status, payload, down
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs: object) -> SimpleNamespace:
        self.calls.append((url, dict(kwargs.get("headers") or {})))
        if self.down:
            raise httpx.ConnectError("down")
        return SimpleNamespace(status_code=self.status, json=lambda: self.payload)


def _with(fake: LiteLLM):
    import main as tank

    previous = tank._http
    tank._http = fake
    tank._roster_cache = None
    return tank, previous


def test_models_route_lists_served_models_cheapest_first_without_keys() -> None:
    fake = LiteLLM()
    tank, previous = _with(fake)
    try:
        rows = asyncio.run(tank.list_models())
    finally:
        tank._http = previous
        tank._roster_cache = None
    assert [row["name"] for row in rows] == ["mystery", "luna", "sol"]
    luna = next(row for row in rows if row["name"] == "luna")
    assert luna == {"name": "luna", "provider_model": "openai/gpt-6-luna",
                    "input_usd_per_m": 0.1, "output_usd_per_m": 0.5}
    mystery = next(row for row in rows if row["name"] == "mystery")
    assert mystery["input_usd_per_m"] is None and mystery["output_usd_per_m"] is None
    assert "sk-should-never-leave-tank" not in repr(rows) and "api_key" not in repr(rows)
    url, headers = fake.calls[0]
    assert url.endswith("/model/info") and headers["Authorization"].startswith("Bearer ")


def test_models_route_is_behind_the_key() -> None:
    import main as tank

    route = next(r for r in tank.app.routes if getattr(r, "path", "") == "/v1/models")
    assert any(dep.call is tank.require_key for dep in route.dependant.dependencies)


def test_roster_is_cached_and_feeds_the_price_search() -> None:
    fake = LiteLLM()
    tank, previous = _with(fake)
    try:
        quotes = asyncio.run(tank._live_price_quotes())
        asyncio.run(tank._live_price_quotes())
    finally:
        tank._http = previous
        tank._roster_cache = None
    assert len(fake.calls) == 1
    assert {quote.name for quote in quotes} == {"sol", "luna", "mystery"}
    assert next(q for q in quotes if q.name == "luna").price == 0.0000006


def test_litellm_down_falls_back_to_the_file_roster_or_nothing() -> None:
    fake = LiteLLM(down=True)
    tank, previous = _with(fake)
    try:
        rows = asyncio.run(tank.list_models())
    finally:
        tank._http = previous
        tank._roster_cache = None
    assert isinstance(rows, list)
    assert all("api_key" not in repr(row) for row in rows)
