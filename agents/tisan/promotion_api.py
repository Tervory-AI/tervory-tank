"""Founder-only room API; application bindings and checks stay on the server."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import uuid
from pathlib import Path

import httpx
from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field


class Site(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    site: str = Field(pattern=r'^[a-z0-9-]{1,100}$')
    staging: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    production: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    url: str = Field(max_length=500)


class Operation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    site: str = Field(pattern=r'^[a-z0-9-]{1,100}$')
    operation_id: uuid.UUID
    commit: str = Field(pattern=r'^[0-9a-f]{40}$')


async def live_check(url: str) -> dict:
    """Reuse the ops browser check at both widths. No credentials enter Chromium."""
    output = Path(os.environ.get('DATA_DIR', '/data')) / 'promotion-checks' / str(uuid.uuid4())
    output.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parent / 'ops/live_check.mjs'
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp',
           'PLAYWRIGHT_BROWSERS_PATH': '/opt/tisan-browser',
           'LIVE_CHECK_PLAYWRIGHT_PATH': '/opt/tisan-check/node_modules/playwright'}
    process = await asyncio.create_subprocess_exec('node', str(script), '--site-url', url,
        '--output', str(output), env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        await asyncio.wait_for(process.wait(), timeout=110)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    if process.returncode != 0:
        return {'passed': False, 'artifact': output.name}
    rows = json.loads((output / 'results.json').read_text())
    passed = (len(rows) == 1 and rows[0].get('passed') is True
              and {v['width'] for v in rows[0]['viewports']} == {375, 1440}
              and all(v['status'] is not None and 200 <= v['status'] < 300 and not v['reasons']
                      for v in rows[0]['viewports']))
    return {'passed': passed, 'artifact': output.name}


def mount(app, core):
    def authorize(key, actor):
        expected = os.environ.get('TANK_KEY', '')
        founders = {p.strip() for p in os.environ.get('TERVORY_ADMIN_USER_IDS', '').split(',') if p.strip()}
        if not expected or not key or not hmac.compare_digest(key.encode(), expected.encode()) or actor not in founders:
            raise HTTPException(404, 'not found')

    def journal():
        return core.Journal(Path(os.environ.get('DATA_DIR', '/data')) / 'promotion.sqlite3')

    def unavailable():
        raise HTTPException(503, 'Promotion could not be confirmed; inspect its operation status.') from None

    @app.post('/promotion/sites')
    async def register(body: Site, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        authorize(x_tank_key, x_tervory_admin)
        try:
            journal().register(str(body.tenant_id), body.site, {k: getattr(body, k) for k in ('staging', 'production', 'url')})
        except core.Refused:
            raise HTTPException(409, 'Site binding could not be registered.') from None
        return {'registered': True}

    async def service_call(action, body, key, actor):
        authorize(key, actor)
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
            async def gate(tenant, target, artifact):
                response = await http.post(os.environ.get('TANK_URL', 'http://tank:8000').rstrip('/') + '/v1/radix/passive/gate',
                    json={'tenant_id': tenant, 'target': target, 'artifact': artifact},
                    headers={'X-Tank-Key': key, 'X-Tervory-Tenant': tenant, 'X-Tervory-Squad': 'tisan'}, timeout=30)
                if response.status_code != 200:
                    raise core.Refused('Radix gate is unavailable')
                return response.json()
            try:
                service = core.Promotion(journal(), core.Coolify(http,
                    os.environ.get('TISAN_COOLIFY_URL', ''), os.environ.get('TISAN_COOLIFY_TOKEN', '')), live_check, gate)
                if action == 'status':
                    return await service.status(str(body.tenant_id), body.site, str(body.operation_id))
                return await service.run(str(body.tenant_id), body.site, str(body.operation_id), action, actor, body.commit)
            except (core.Refused, httpx.HTTPError, ValueError, OSError, TimeoutError):
                unavailable()

    @app.post('/promotion/promote')
    async def promote(body: Operation, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        return await service_call('promote', body, x_tank_key, x_tervory_admin)

    @app.post('/promotion/rollback')
    async def rollback(body: Operation, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        return await service_call('rollback', body, x_tank_key, x_tervory_admin)

    @app.post('/promotion/status')
    async def status(body: Operation, x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        return await service_call('status', body, x_tank_key, x_tervory_admin)

    @app.get('/promotion/history')
    async def history(tenant_id: uuid.UUID, site: str = Query(pattern=r'^[a-z0-9-]{1,100}$'),
                      x_tank_key: str = Header(default=''), x_tervory_admin: str = Header(default='')):
        authorize(x_tank_key, x_tervory_admin)
        return journal().history(str(tenant_id), site)
