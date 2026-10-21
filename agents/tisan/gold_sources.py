"""Persist founder approvals against immutable build and frame snapshots."""

import hashlib
import json
import math
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Header, HTTPException, Query, Request
from pydantic import BaseModel

PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_tisan.page_approvals (
 tenant_id uuid NOT NULL,
 page_id text NOT NULL,
 figma_file_id text NOT NULL,
 figma_frame_id text NOT NULL,
 frame_hash text NOT NULL,
 built_page_path text NOT NULL,
 page_hash text NOT NULL,
 approved_by text NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id, page_id)
);
"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or path.is_symlink():
        raise ValueError("invalid artifact path")
    return path


def require_visual_data(reading: Any) -> None:
    """Gold requires recorded geometry, text and tokens at both review widths."""
    def refuse() -> None:
        raise HTTPException(422, "frame data incomplete")

    frames = reading.get("visual") if isinstance(reading, dict) else None
    if not isinstance(frames, list) or not frames:
        refuse()
    widths = set()
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("incomplete"):
            refuse()
        width = frame.get("width")
        if type(width) not in (int, float) or width not in (375, 1440):
            refuse()
        widths.add(width)
        tokens = frame.get("tokens")
        elements = frame.get("elements")
        if not isinstance(tokens, dict) or not tokens or not isinstance(elements, list) or not elements:
            refuse()
        has_text = False
        for element in elements:
            if not isinstance(element, dict) or not isinstance(element.get("box"), dict):
                refuse()
            box = element["box"]
            for key in ("x", "y", "width", "height"):
                value = box.get(key)
                if type(value) not in (int, float) or not math.isfinite(value):
                    refuse()
                if key in ("width", "height") and value <= 0:
                    refuse()
            has_text = has_text or isinstance(element.get("text"), str) and bool(element["text"].strip())
        if not has_text:
            refuse()
    if widths != {375, 1440}:
        refuse()


def snapshot(root: Path, tenant: str, page_id: str) -> dict[str, Any]:
    tenant = str(uuid.UUID(tenant))
    if not re.fullmatch(r"[a-z0-9-]{1,100}", page_id):
        raise ValueError("invalid page id")
    row = json.loads((root / "reviews" / tenant / f"{page_id}.json").read_text())
    if row["tenant_id"] != tenant or row["region"] not in {"za", "us-east"} or row["region"] != os.environ.get("TANK_REGION", "us-east"):
        raise ValueError("artifact scope mismatch")
    # Resolve only this tenant's artifacts, even if a metadata file is malformed.
    frame_root = root / "readings" / tenant
    build_root = root / "builds" / tenant
    frame = json.loads(safe_path(frame_root, row["frame_path"]).read_text())
    require_visual_data(frame)
    page = json.loads(safe_path(build_root, row["built_page_path"]).read_text())
    return {**row, "page_id": page_id, "frame": frame, "page_structure": page["structure"],
            "html": page["html"], "css": page.get("css", ""), "frame_hash": digest(frame), "page_hash": digest(page)}


def _month(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = value.isoformat() if hasattr(value, "isoformat") else str(value).strip()
    if len(text) < 7 or text[4] != "-" or not (text[:4].isdigit() and text[5:7].isdigit()):
        return None
    if not 1 <= int(text[5:7]) <= 12:
        return None
    return text[:7]


def page_family(approved_at: Any, *, synthetic: bool = False) -> str | None:
    """One family per approval month. A planted wrong page is its own family."""
    month = _month(approved_at)
    if month is None:
        return None
    family = f"founder-approved-page:{month}"
    if synthetic:
        return family.replace(":", "-synthetic:", 1)
    return family


def matches(row: dict[str, Any], approval: Any) -> bool:
    return (row["frame_hash"] == approval["frame_hash"] and row["page_hash"] == approval["page_hash"]
            and row["figma_file_id"] == approval["figma_file_id"]
            and row["figma_frame_id"] == approval["figma_frame_id"]
            and row["built_page_path"] == approval["built_page_path"])


def room_key(value: str) -> None:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not value or not secrets.compare_digest(value.encode(), expected.encode()):
        raise HTTPException(401, "room key required")


def founder(value: str, user: str) -> None:
    room_key(value)
    allowed = {part.strip() for part in os.environ.get("TERVORY_ADMIN_USER_IDS", "").split(",") if part.strip()}
    if not user or user not in allowed:
        raise HTTPException(404, "not found")


class Approval(BaseModel):
    tenant_id: uuid.UUID
    page_id: str
    frame_hash: str
    page_hash: str


def mount(app: Any) -> None:
    prior = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance: Any):
        async with prior(instance):
            async with instance.state.pool.acquire() as conn:
                await conn.execute(SCHEMA)
            yield
    app.router.lifespan_context = lifespan

    def root() -> Path:
        return Path(os.environ.get("DATA_DIR", "/data"))

    @app.get("/gold/pages")
    async def pages(tenant_id: uuid.UUID, x_tank_key: str = Header(default=""),
                    x_tervory_admin: str = Header(default="")) -> list[dict[str, Any]]:
        founder(x_tank_key, x_tervory_admin)
        result = []
        for path in sorted((root() / "reviews" / str(tenant_id)).glob("*.json"))[:200]:
            try:
                result.append(snapshot(root(), str(tenant_id), path.stem))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return result

    @app.post("/gold/approve")
    async def approve(body: Approval, request: Request, x_tank_key: str = Header(default=""),
                      x_tervory_admin: str = Header(default="")) -> dict[str, Any]:
        founder(x_tank_key, x_tervory_admin)
        try:
            row = snapshot(root(), str(body.tenant_id), body.page_id)
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(404, "page not found") from None
        if body.frame_hash != row["frame_hash"] or body.page_hash != row["page_hash"]:
            raise HTTPException(409, "page or frame changed; review again")
        async with request.app.state.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO agent_tisan.page_approvals
                (tenant_id,page_id,figma_file_id,figma_frame_id,frame_hash,built_page_path,page_hash,approved_by)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                ON CONFLICT (tenant_id,page_id) DO UPDATE SET
                figma_file_id=EXCLUDED.figma_file_id,figma_frame_id=EXCLUDED.figma_frame_id,
                frame_hash=EXCLUDED.frame_hash,built_page_path=EXCLUDED.built_page_path,
                page_hash=EXCLUDED.page_hash,approved_by=EXCLUDED.approved_by,approved_at=now()
            """, body.tenant_id, body.page_id, row["figma_file_id"], row["figma_frame_id"],
                row["frame_hash"], row["built_page_path"], row["page_hash"], x_tervory_admin)
        return {"approved": True}

    @app.get("/gold/candidates")
    async def candidates(request: Request, tenant_id: uuid.UUID = uuid.UUID(PLATFORM_TENANT),
                         limit: int = Query(default=200, ge=1, le=200),
                         x_tank_key: str = Header(default="")) -> list[dict[str, Any]]:
        room_key(x_tank_key)
        try:
            cap = max(0, min(limit, int(os.environ.get("GOLD_AUTO_MAX", "200"))))
        except ValueError:
            cap = 0
        if not cap:
            return []
        async with request.app.state.pool.acquire() as conn:
            approvals = await conn.fetch("SELECT * FROM agent_tisan.page_approvals WHERE tenant_id=$1 ORDER BY page_id", tenant_id)
        result = []
        for approval in approvals:
            try:
                row = snapshot(root(), str(tenant_id), approval["page_id"])
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if not matches(row, approval):
                continue
            try:
                approved_at = approval["approved_at"]
            except (KeyError, IndexError, TypeError):
                continue
            family = page_family(approved_at, synthetic=row.get("synthetic") is True)
            if family is None:
                continue
            for skill in ("tisan.figma", "tisan.scaffold"):
                result.append({"skill_id": skill, "input": row["frame"], "expected": row["page_structure"],
                               "label_source": "auto:founder-approved-page:" + row["page_hash"],
                               "label_family": family,
                               "region": row["region"], "public": row.get("public") is True and str(tenant_id) == PLATFORM_TENANT})
                if len(result) == cap:
                    return result
        return result
