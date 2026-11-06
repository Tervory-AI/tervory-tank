import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket

import httpx
import pytest
import uvicorn
from fastapi import Query

from test_tiger import ROOT, TENANT_A, _load
from tiger_sheet.patch_source import source
from tiger_works.fixture import saved_page, extract, no_paid_call
from watch import MemoryStore, DomainLimiter, run_check


@pytest.mark.asyncio
@pytest.mark.parametrize('width', [375, 1440])
async def test_client_journeys_in_browser_with_real_room_and_fake_external_page(tmp_path, monkeypatch, width):
    agent = _load('gate5_journey_'+str(width), ROOT/'agents/tiger/app.py')
    store = MemoryStore()
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setattr(agent, '_store', lambda: store)
    monkeypatch.setattr(agent, 'check_url', lambda url: url)
    @agent.app.post('/fixture/settle')
    async def settle(body: dict):
        for watch in await store.enabled_watches(TENANT_A):
            async def render(*args):
                if body.get('failure'):
                    raise httpx.ReadTimeout('placeholder transport failure')
                return {'ok': True, 'html': saved_page(str(body.get('price', 120)), 'InStock')}
            await run_check(store, TENANT_A, watch, 'tiger', render, extract, no_paid_call, no_paid_call,
                            DomainLimiter(0), now=lambda: datetime.now(timezone.utc))
        return {'ok': True}
    project = Path(os.environ['TIGER_PROJECT_ROOT'])
    files = set()
    for patch in (project/'tank-patches').glob('gate[45]-workspace.patch'):
        files.update(re.findall(r'^\+\+\+ b/(.+)$', patch.read_text(), re.MULTILINE))
    proposed = tmp_path/'source.json'
    proposed.write_text(json.dumps({name: source(name) for name in files}))
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config(agent.app, log_level='warning', lifespan='off'))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        for _ in range(100):
            if server.started: break
            await asyncio.sleep(.01)
        assert server.started
        env = {**os.environ, 'TIGER_JOURNEY_API': f'http://127.0.0.1:{listener.getsockname()[1]}',
               'TIGER_JOURNEY_TENANT': TENANT_A}
        process = await asyncio.create_subprocess_exec('node', str(ROOT/'tests/tiger_sheet/gate5_journeys.cjs'),
            str(proposed), str(width), cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(process.communicate(), 110)
        assert process.returncode == 0, out.decode()+err.decode()
        assert 'journeys passed' in out.decode()
        assert len(await store.list_watches(TENANT_A)) == 1
        assert len(store.observations) == 3
        assert all(row['tenant_id'] == TENANT_A for row in store.observations)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 5)
        listener.close()
