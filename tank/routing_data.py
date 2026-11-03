"""Policy routing data; gateway-only options never enter generation fingerprints."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

_CACHE: tuple[tuple, float, dict] | None = None


def _catalog(rows: list, fallbacks: list) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        name = row.get("model_name")
        info = row.get("model_info") or {}
        if isinstance(name, str):
            groups.setdefault(name, []).append({"id": info.get("id"), "host": info.get("host")})
    chains = {name: chain for entry in fallbacks for name, chain in entry.items()}
    return {"groups": groups, "chains": chains}


async def catalog(tank: Any) -> dict:
    """Only retain public names, deployment IDs, hosts and configured chains."""
    global _CACHE
    key = (tank.LITELLM_URL, id(tank._http), str(tank._roster_path()))
    if _CACHE is not None and _CACHE[0] == key and time.monotonic() - _CACHE[1] < 300:
        return _CACHE[2]
    if tank._http is not None and hasattr(tank._http, "get"):
        try:
            headers = {"Authorization": f"Bearer {tank.LITELLM_MASTER_KEY}"}
            roster = await tank._http.get(f"{tank.LITELLM_URL}/model/info", headers=headers, timeout=10)
            settings = await tank._http.get(f"{tank.LITELLM_URL}/router/settings", headers=headers, timeout=10)
            roster.raise_for_status()
            settings.raise_for_status()
            values = settings.json()["current_values"]
            data = _catalog(roster.json()["data"], values["fallbacks"] or [])
            _CACHE = (key, time.monotonic(), data)
            return data
        except (KeyError, TypeError, ValueError, AttributeError, __import__("httpx").HTTPError):
            pass
    path = Path(tank._roster_path())
    if path.is_file():
        import yaml
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return _catalog(raw.get("model_list", []), (raw.get("litellm_settings") or {}).get("fallbacks", []))
    # No metadata must never mean unchecked gateway defaults or unknown hosts.
    return {"groups": {}, "chains": {}}


async def validate_fallbacks(tank: Any, model: str, names: list[str] | None) -> None:
    if names is None:
        return
    rows = {row["name"]: row for row in await tank.list_models()}
    if (len(names) > 7 or len(names) != len(set(names)) or model in names
            or any(name not in rows or tank.is_build_only_model(name)
                   or name.startswith(("skill:", "cache:", "tool:", "routellm:")) for name in names)):
        raise HTTPException(422)
    prices = []
    for name in names:
        row = rows[name]
        a, b = row["input_usd_per_m"], row["output_usd_per_m"]
        if a is None or b is None:
            raise HTTPException(422)
        prices.append(a + b)
    if prices != sorted(prices):
        raise HTTPException(422)


def _direct(tank: Any, data: dict, name: str, tenant: str) -> str | None:
    """Restrictive model lists must explicitly include each secondary host too."""
    allow = tank.tenant_allowlist(tenant)
    deployments = data["groups"].get(name, [])
    if allow is None or not any(row["host"] and row["host"] not in allow for row in deployments):
        # Missing dual-deployment metadata fails closed for restricted tenants.
        if allow is not None and name in {"kimi", "kimi-lite"} and not deployments:
            raise HTTPException(503)
        return None
    direct = deployments[0]
    if direct["host"] and direct["host"] not in allow or not direct["id"]:
        raise HTTPException(503)
    return str(direct["id"])


async def dispatch(tank: Any, *, policy: dict, model: str, generation: dict,
                   offpeak: bool, text: str, refusal_args: dict) -> dict:
    data = await catalog(tank)
    tenant = refusal_args["tenant_id"]
    direct = _direct(tank, data, model, tenant)
    if direct is not None:
        return {"model": direct, "disable_fallbacks": True}
    if "disable_fallbacks" in generation or offpeak:
        return {}
    names = policy.get("fallbacks")
    if names is None:
        names = data["chains"].get(model, [])
    chain = []
    for name in names:
        if tank.model_call_refusal(text, name, **refusal_args):
            continue
        deployment = _direct(tank, data, name, tenant)
        chain.append({"model": deployment, "disable_fallbacks": True} if deployment else name)
    # Override every configured exception chain too: they are not permission checked.
    return {"fallbacks": chain, "context_window_fallbacks": [], "content_policy_fallbacks": []}
