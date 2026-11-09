"""Tisan-only optional runtime adapter. Tank owns discovery and signed dispatch."""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode, urlsplit

import httpx
from agent_skills import local_region, room_key
from agent_tasks import DelegatedTask
from command_tools._user_assertion import PostgresNonces, signed_user
from fastapi import APIRouter, HTTPException, Request
from product_identity import actor_scope
from task_contract import check_receipt, origin


def build_router(tank):
    router = APIRouter()
    @router.post('/v1/agents/tisan/delegate')
    async def delegate(body: DelegatedTask, request: Request):
        room_key('tisan', request.headers.get('authorization', ''), request.headers.get('x-tank-key', ''))
        if os.environ.get('TISAN_BRAIN_ENABLED', 'false').lower() not in {'true', '1', 'yes'}:
            raise HTTPException(409, 'Tisan brain is off')
        region = local_region(tank, request.headers.get('x-home-region'), room='tisan')
        actor = await signed_user(request, tenant_id=str(body.tenant_id), product='tisan', required=True,
                                  nonces=PostgresNonces(tank.pool(), 'tank'))
        if actor.user_id != body.user_id:
            raise HTTPException(403, 'Actor mismatch')
        if body.task_key != 'tisan.plan' or set(body.input) != {'request', 'contract'} or body.recall:
            raise HTTPException(422, 'Invalid planning task')
        prompt = body.input['request']
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 16000 or not isinstance(body.input['contract'], dict):
            raise HTTPException(422, 'Invalid planning task')
        try:
            base = origin(os.environ.get('TISAN_BRAIN_URL', 'http://tisan-brain:8001'))
            parsed = urlsplit(base)
            if parsed.scheme != 'http' or parsed.hostname != 'tisan-brain' or parsed.port != 8001:
                raise ValueError('Invalid private origin')
        except ValueError:
            raise HTTPException(503, 'Tisan task unavailable') from None
        target = '/tasks/plan?' + urlencode({'tenant_id': actor.tenant_id, 'user_id': actor.user_id})
        content = json.dumps({'task_key': body.task_key, 'input': body.input,
                              'recall': body.recall, 'run_id': str(body.run_id)}).encode()
        if len(content) > 1_000_000:
            raise HTTPException(413, 'Task is too large')
        try:
            with actor_scope(actor):
                response = await tank._http.post(base + target, content=content,
                    headers={'Content-Type': 'application/json', 'X-Tank-Key': os.environ['TANK_KEY_TISAN'],
                             'X-Home-Region': region},
                    extensions={'tervory_product_origin': ('tisan', (parsed.scheme, parsed.hostname, parsed.port))},
                    timeout=70, follow_redirects=False)
            response.raise_for_status()
            data = response.json()
            check_receipt(data, actor.tenant_id, actor.user_id, str(body.run_id), 'tisan')
            if data['receipt']['region'] != region:
                raise ValueError('Receipt region mismatch')
            return data
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise HTTPException(status if 400 <= status < 600 else 502, 'Tisan task unavailable') from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
            raise HTTPException(502, 'Tisan task unavailable') from None

    return router
