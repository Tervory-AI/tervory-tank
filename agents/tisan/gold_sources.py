"""Read reviewed, platform-owned frame/page pairs. No inferred approvals."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def candidates(root: Path, region: str, limit: int = 200) -> list[dict[str, Any]]:
    """Only reviewed non-client records from this region may cross this room boundary.

    Files are installed by the trusted approval process, never by a job input.
    Approval binds the exact frame and built page structure, not just a page name.
    """
    if region not in {"za", "us-east"}:
        return []
    try:
        cap = max(0, min(int(os.environ.get("GOLD_AUTO_MAX", "200")), 200))
    except ValueError:
        return []
    limit = min(max(0, limit), cap)
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if not limit or not root.is_dir():
        return result
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(row, dict):
            continue
        if (row.get("tenant_id") != PLATFORM_TENANT or row.get("region") != region
                or row.get("non_client") is not True or type(row.get("public")) is not bool):
            continue
        frame, page, approval = row.get("frame"), row.get("page_structure"), row.get("approval")
        if not all(isinstance(value, dict) and value for value in (frame, page, approval)):
            continue
        if (row.get("built") is not True or approval.get("role") != "founder"
                or approval.get("status") != "approved" or not approval.get("reference")
                or approval.get("frame_sha256") != digest(frame)
                or approval.get("page_sha256") != digest(page)):
            continue
        identity = (digest(frame), digest(page))
        if identity in seen:
            continue
        seen.add(identity)
        # Content digest identifies the evidence without exposing reviewer identities or URLs.
        for skill in ("tisan.figma", "tisan.scaffold"):
            result.append({"skill_id": skill, "input": frame, "expected": page,
                           "label_source": "auto:founder-approved-page:" + identity[1],
                           "region": region, "public": row["public"]})
            if len(result) == limit:
                return result
    return result


def mount(app: Any) -> None:
    """Keep authentication local to this route; do not change chassis behavior."""
    import secrets
    from fastapi import Header, HTTPException, Query
    from starlette.concurrency import run_in_threadpool

    @app.get("/gold/candidates")
    async def gold_candidates(
        limit: int = Query(default=200, ge=1, le=200),
        x_tank_key: str | None = Header(default=None),
    ) -> list[dict[str, Any]]:
        key = os.environ.get("TANK_KEY", "")
        if not key or not x_tank_key or not secrets.compare_digest(key.encode(), x_tank_key.encode()):
            raise HTTPException(status_code=401, detail="room key required")
        root = Path(os.environ.get("DATA_DIR", "/data")) / "gold" / "approved-pages"
        return await run_in_threadpool(candidates, root, os.environ.get("TANK_REGION", "us-east"), limit)
