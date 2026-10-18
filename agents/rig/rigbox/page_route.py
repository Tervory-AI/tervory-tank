"""Shopper and dealer pages. Calls this host's /v1/rig. Never logs a key."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

_PAGE = Path(__file__).resolve().parent / "page"
_CN = _PAGE / "cn"
_CN_MEDIA = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
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


def _cn_html() -> HTMLResponse:
    html = (_CN / "index.html").read_text(encoding="utf-8")
    publish = archon_publish()
    html = html.replace("__CN_KEY__", json.dumps(archon_key()))
    html = html.replace("__CN_EMAIL__", json.dumps(str(publish.get("email") or "")))
    html = html.replace("__CN_PHONE__", json.dumps(str(publish.get("phone") or "")))
    html = html.replace("__CN_NAME__", json.dumps(str(publish.get("name") or "Custom Nation")))
    return HTMLResponse(html)


def _shopper_html() -> HTMLResponse:
    html = (_PAGE / "index.html").read_text(encoding="utf-8")
    html = html.replace("__RIG_PUBLISHABLE_KEY__", json.dumps(house_key()))
    return HTMLResponse(html)


def mount_page(application: FastAPI) -> None:
    @application.get("/", include_in_schema=False)
    async def search_page() -> HTMLResponse:
        return _shopper_html()

    @application.get("/product/{product_id}", include_in_schema=False)
    async def product_page(product_id: str) -> HTMLResponse:
        del product_id
        return _shopper_html()

    @application.get("/cn", include_in_schema=False)
    @application.get("/cn/{rest:path}", include_in_schema=False)
    async def cn_page(rest: str = "") -> HTMLResponse:
        del rest
        return _cn_html()

    @application.get("/page/cn/{name:path}", include_in_schema=False)
    async def cn_asset(name: str) -> FileResponse:
        media = _CN_MEDIA.get(Path(name).suffix.lower())
        path = (_CN / name).resolve()
        root = _CN.resolve()
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
