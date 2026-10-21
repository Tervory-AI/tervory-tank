"""tisan.scaffold 1.0.0 — a Next.js project from a short brief. Pure code."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any


def _load():
    candidates: list[Path] = []
    raw = os.environ.get("TISAN_SCAFFOLD", "").strip()
    if raw:
        candidates.append(Path(raw))
    here = Path(__file__).resolve()
    # Repo layout: tank/skills/tisan.scaffold/1.0.0/run.py
    if len(here.parents) > 4:
        candidates.append(here.parents[4] / "agents" / "tisan" / "scaffold.py")
    candidates.append(Path("/app/scaffold.py"))
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("tisan_scaffold_skill", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("tisan scaffold is not available")


async def run(payload: dict[str, Any], ctx: Any) -> dict[str, Any]:
    tenant = getattr(ctx, "tenant_id", None)
    if tenant is None:
        tenant = (payload or {}).get("tenant_id")
    if tenant is None:
        raise RuntimeError("tenant_id is required")
    module = _load()
    return await module.execute(payload, str(tenant))
