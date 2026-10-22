"""Immutable public widget files and a configured test page on Rig's own host."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response

NAME = re.compile(r"tervory-rig\.[a-f0-9]{64}\.umd\.js")


def root() -> Path:
    return Path(os.environ.get("RIG_WIDGET_DIR", str(Path(__file__).parent / "widget"))).resolve()


def asset(name: str) -> bytes:
    if not NAME.fullmatch(name):
        raise HTTPException(404, "No such widget bundle")
    path = (root() / name).resolve()
    if path.parent != root() or not path.is_file():
        raise HTTPException(404, "No such widget bundle")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != name.split(".")[1] or len(gzip.compress(body)) > 150 * 1024:
        raise HTTPException(503, "Widget bundle failed verification")
    return body


def manifest() -> dict:
    try:
        data = json.loads((root() / "manifest.json").read_text())
        asset(data["file"])
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "Widget bundle is not installed") from None


def mount(application: FastAPI) -> None:
    @application.get("/widget/fonts/{name}", include_in_schema=False)
    async def widget_font(name: str):
        allowed = {"custom-nation.css", "barlow-condensed-latin-600-normal.woff2",
                   "inter-latin-400-normal.woff2", "inter-latin-500-normal.woff2", "inter-latin-600-normal.woff2"}
        if name not in allowed:
            raise HTTPException(404, "No such font")
        body = (Path(__file__).parent / "fonts" / name).read_bytes()
        return Response(body, media_type="text/css" if name.endswith(".css") else "font/woff2",
                        headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*",
                                 "X-Content-Type-Options": "nosniff"})

    @application.get("/widget/manifest.json", include_in_schema=False)
    async def widget_manifest():
        return JSONResponse(manifest(), headers={"Cache-Control": "no-cache", "Access-Control-Allow-Origin": "*"})

    @application.get("/widget/assets/{name}", include_in_schema=False)
    async def widget_asset(name: str):
        return Response(asset(name), media_type="text/javascript", headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Access-Control-Allow-Origin": "*", "X-Content-Type-Options": "nosniff",
        })

    @application.get("/widget/test", include_in_schema=False)
    async def widget_test():
        key = os.environ.get("RIG_WIDGET_PUBLISHABLE_KEY", "")
        if not key:
            raise HTTPException(503, "RIG_WIDGET_PUBLISHABLE_KEY is not configured")
        file = html.escape(manifest()["file"], quote=True)
        public_key = html.escape(key, quote=True)
        return HTMLResponse(f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rig · retailer test page</title><style>body{{margin:0}}tervory-rig{{display:block}}</style>
</head><body><tervory-rig api-base="" rig-key="{public_key}" theme="custom-nation" fonts="/widget/fonts/custom-nation.css"></tervory-rig>
<script src="/widget/assets/{file}"></script></body></html>''', headers={
            "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
            "Content-Security-Policy": "frame-ancestors 'none'",
        })
