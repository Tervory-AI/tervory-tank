"""market.series_fetch — one series from fred, csv, xlsx, or a monthly listing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load() -> Any:
    here = Path(__file__).resolve()
    names = (
        "agents/market_lab/core/pure.py",
        "skills/market.series_fetch/1.0.0/pure.py",
        "market.series_fetch/1.0.0/pure.py",
    )
    for parent in here.parents:
        for name in names:
            path = parent / name
            if not path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("market_lab_pure", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("market lab logic is missing")


async def _read_fred(payload: dict[str, Any], ctx: Any) -> dict[str, Any]:
    env = getattr(ctx, "env", None) or {}
    key = str(env.get("FRED_API_KEY") or "") if isinstance(env, dict) else ""
    if not key.strip():
        import os

        key = os.environ.get("FRED_API_KEY", "")
    key = key.strip()
    if not key:
        raise RuntimeError("FRED_API_KEY is not set")
    series_id = str(payload.get("series_id") or payload.get("ref") or "")
    try:
        response = await ctx.http.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": key, "file_type": "json"},
        )
    except Exception:  # noqa: BLE001 — the key must not appear in the error
        raise RuntimeError("fred read failed") from None
    status = getattr(response, "status_code", 500)
    if status >= 400:
        raise RuntimeError("fred read failed")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("fred read failed")
    return body


async def run(payload: dict, ctx) -> dict:
    data = dict(payload or {})
    if data.get("adapter") == "fred" and "observations" not in data and "body" not in data:
        data["body"] = await _read_fred(data, ctx)
    return _load().series_fetch(data)
