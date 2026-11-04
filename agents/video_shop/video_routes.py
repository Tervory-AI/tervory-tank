"""Rig-authenticated review and shopper routes. Mount on the Rig host."""
from __future__ import annotations

import asyncio
import base64
import json

from fastapi import APIRouter, HTTPException, Request
from rigbox.api import _admin, _ok, _tenant, _service
from .video_engine import Engine, Repository, MAX_BYTES
from .video_media import download

router = APIRouter(prefix='/v1/rig/video-shop')


def engine(request):
    if not hasattr(request.app.state, 'video_shop'):
        request.app.state.video_shop = Engine(_service(request), Repository(request.app.state.video_shop_root))
    return request.app.state.video_shop


async def body(request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES * 2:
            raise HTTPException(413, 'media_limit')
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise HTTPException(422, 'invalid') from None


@router.post('/admin/videos')
async def create(request: Request):
    await _admin(request)
    data = await body(request)
    try:
        if bool(data.get('video_base64')) == bool(data.get('url')):
            raise ValueError('one_source')
        video = (await asyncio.to_thread(download, data['url']) if data.get('url')
                 else base64.b64decode(data['video_base64'], validate=True))
        references = {sku: base64.b64decode(value, validate=True)
                      for sku, value in data.get('references', {}).items()}
        result = await engine(request).ingest(_tenant(request), video, data.get('transcript', []), references)
        return _ok(request, result)
    except (ValueError, KeyError, TypeError, IndexError):
        raise HTTPException(422, 'invalid_media') from None


@router.get('/admin/videos/{identifier}')
async def draft(identifier: str, request: Request):
    await _admin(request)
    try:
        return _ok(request, engine(request).repository.get(_tenant(request), identifier))
    except KeyError:
        raise HTTPException(404, 'video') from None


@router.put('/admin/videos/{identifier}')
async def review(identifier: str, request: Request):
    await _admin(request)
    data = await body(request)
    try:
        if type(data['revision']) is not int:
            raise ValueError('revision')
        return _ok(request, await engine(request).review(_tenant(request), identifier,
                                                       data['revision'], data['moments']))
    except KeyError:
        raise HTTPException(404, 'video_or_field') from None
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, str(exc)) from None


def mount(app, root):
    app.state.video_shop_root = str(root)
    app.include_router(router)
