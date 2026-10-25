"""Shopper and dealer pages. Calls this host's /v1/rig. Never logs a key."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

_PAGE = Path(__file__).resolve().parent / "page"
_V5 = _PAGE / "v5"
_V5_MEDIA = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}
_V5_SKINS = {"rig", "cn"}
_ASSETS = {
    "search.js": "text/javascript",
    "search.css": "text/css",
    "admin.js": "text/javascript",
    "tervory-logo-on-white.png": "image/png",
}


def house_key() -> str:
    """Publishable key for the catalogue on the Tervory page.

    The sheet lives in catalogues/customnation. The page keeps the Tervory
    skin. The example catalogue stays a separate tenant and is not this page.
    """
    publish = Path(__file__).resolve().parents[1] / "catalogues" / "customnation" / "publish.json"
    try:
        data = json.loads(publish.read_text(encoding="utf-8"))
    except OSError:
        return ""
    keys = data.get("keys") or []
    if not keys or not isinstance(keys[0], dict):
        return ""
    return str(keys[0].get("key") or "")


def archon_publish() -> dict:
    path = Path(__file__).resolve().parents[1] / "catalogues" / "archon" / "publish.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def archon_key() -> str:
    keys = archon_publish().get("keys") or []
    if not keys or not isinstance(keys[0], dict):
        return ""
    return str(keys[0].get("key") or "")


def _v5_html(skin: str) -> HTMLResponse:
    """The v5 shopper page from the approved Figma. One page, two skins.

    Both skins search the Archon demo catalogue through /v1/rig on this host.
    """
    html = (_V5 / "index.html").read_text(encoding="utf-8")
    publish = archon_publish()
    html = html.replace("__RIG_SKIN__", skin if skin in _V5_SKINS else "rig")
    html = html.replace("__RIG_KEY__", json.dumps(archon_key()))
    html = html.replace("__RIG_SHOP__", json.dumps(str(publish.get("name") or "Custom Nation")))
    return HTMLResponse(html)


def _shopper_html() -> HTMLResponse:
    html = (_PAGE / "index.html").read_text(encoding="utf-8")
    html = html.replace("__RIG_PUBLISHABLE_KEY__", json.dumps(house_key()))
    return HTMLResponse(html)


def mount_page(application: FastAPI) -> None:
    @application.get("/", include_in_schema=False)
    async def search_page() -> HTMLResponse:
        # Root is the built Rig product surface (v5 shopper, Archon fixtures).
        return _v5_html("rig")

    @application.get("/product/{product_id}", include_in_schema=False)
    async def product_page(product_id: str) -> HTMLResponse:
        del product_id
        return _shopper_html()

    @application.get("/cn-classic", include_in_schema=False)
    async def cn_classic_page() -> HTMLResponse:
        """Classic Custom Nation sheet UI (rk_pub_customnation). Secondary path."""
        return _shopper_html()

    @application.get("/house", include_in_schema=False)
    async def house_page() -> HTMLResponse:
        """Alias of /cn-classic for the house catalogue page."""
        return _shopper_html()

    @application.get("/v5", include_in_schema=False)
    async def v5_page(skin: str = "rig") -> HTMLResponse:
        return _v5_html(skin)

    @application.get("/v5/cn", include_in_schema=False)
    async def v5_cn_page() -> HTMLResponse:
        return _v5_html("cn")

    @application.get("/page/v5/{name:path}", include_in_schema=False)
    async def v5_asset(name: str) -> FileResponse:
        media = _V5_MEDIA.get(Path(name).suffix.lower())
        path = (_V5 / name).resolve()
        root = _V5.resolve()
        if media is None or root not in path.parents or not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type=media)

    @application.get("/admin", include_in_schema=False)
    async def admin_page() -> HTMLResponse:
        return HTMLResponse((_PAGE / "admin.html").read_text(encoding="utf-8"))

    @application.get("/page/{name}", include_in_schema=False)
    async def search_asset(name: str) -> FileResponse:
        media = _ASSETS.get(name)
        path = (_PAGE / name).resolve()
        if media is None or path.parent != _PAGE.resolve() or not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type=media)
