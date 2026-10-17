"""tisan.figma 1.0.0 — tokens and a component manifest from one Figma page."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any


def _load():
    candidates: list[Path] = []
    raw = os.environ.get("TISAN_FIGMA", "").strip()
    if raw:
        candidates.append(Path(raw))
    here = Path(__file__).resolve()
    # Repo layout: tank/skills/tisan.figma/1.0.0/run.py
    if len(here.parents) > 4:
        candidates.append(here.parents[4] / "agents" / "tisan" / "figma.py")
    candidates.append(Path("/app/figma.py"))
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("tisan_figma_skill", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("tisan figma reader is not available")


async def run(payload: dict[str, Any], ctx: Any) -> dict[str, Any]:
    tenant = getattr(ctx, "tenant_id", None)
    if tenant is None:
        tenant = (payload or {}).get("tenant_id")
    if tenant is None:
        raise RuntimeError("tenant_id is required")
    # A skill context carries its own env. An empty env stays on the fixture
    # even if the process has a token, so evals do not call Figma.
    env = getattr(ctx, "env", None)
    token = str(env.get("FIGMA_TOKEN") or "") if isinstance(env, dict) else os.environ.get("FIGMA_TOKEN", "")
    client = getattr(ctx, "http", None) if token.strip() else None
    module = _load()
    return await module.execute(payload, str(tenant), client=client, token=token)
