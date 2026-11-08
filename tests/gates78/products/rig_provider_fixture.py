"""Loopback-only worker corridor; only the model provider's HTTP edge is fake."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from tank_routing.litellm_probe import COMPLETIONS_PATH


@asynccontextmanager
async def worker_corridor(wire, monkeypatch, root: Path):
    if importlib.util.find_spec('run_agent') is None:
        pytest.fail('BLOCKED: install the existing Dockerfile.brain HERMES_COMMIT in the cloud '
                    'Python toolchain; never replace AIAgent or fabricate its child receipt.', pytrace=False)
    import subprocess
    sdk = Path(importlib.util.find_spec('run_agent').origin).parent
    pinned = (root / 'agents/rig/Dockerfile.brain').read_text().split('ARG HERMES_COMMIT=', 1)[1].splitlines()[0]
    assert subprocess.check_output(['git', '-C', str(sdk), 'rev-parse', 'HEAD'], text=True).strip() == pinned
    import main as tank
    import paid_http
    import skala
    from paid_steps_fixtures import configure_paid_auto
    from savings_defaults import initialize
    pool = wire.pool
    await pool.execute((root / 'tank/schema.sql').read_text())
    async with pool.acquire() as conn:
        await initialize(conn)
    monkeypatch.setattr(tank, '_pool', pool)
    monkeypatch.setattr(tank, '_admin_pool', pool)
    monkeypatch.setattr(tank, '_packages', skala.load_packages())
    monkeypatch.setattr(tank, '_roster_cache', None)
    configure_paid_auto(monkeypatch, lambda: pool)
    for package in tank._packages.values():
        if package.agent == 'rig':
            await pool.execute('''INSERT INTO tank.skills(id,version,agent,state,present)
                VALUES($1,$2,'rig','approved',true) ON CONFLICT(id,version)
                DO UPDATE SET state='approved',present=true''', package.id, package.version)
    await pool.execute("""UPDATE tank.policy SET model='placeholder-recorded',
        baseline_model='placeholder-baseline' WHERE task_type='agent.rig.think'""")

    fake = FastAPI()

    @fake.get('/model/info')
    async def roster():
        return {'data': [{'model_name': name, 'litellm_params': {'model': name},
                         'model_info': {'input_cost_per_token': 0.001, 'output_cost_per_token': 0.002}}
                        for name in ('llama-small', 'gpt-oss-small', 'qwen-small', 'gpt-oss', 'llama', 'placeholder-recorded', 'placeholder-baseline')]}

    @fake.post(COMPLETIONS_PATH)
    async def completion(request: Request):
        assert request.url.path == '/litellm' + COMPLETIONS_PATH
        assert request.url.hostname == '127.0.0.1'
        body = await request.json()
        assert body['model'] == 'llama-small'
        # The real Rig protocol adapter parses this JSON, then the real Hermes
        # worker calls the approved skill. No skill or receipt is fabricated here.
        conversation = json.loads(body['messages'][-1]['content'])['conversation']
        ran_skill = any(message.get('role') == 'tool' for message in conversation)
        answer = {'content': 'placeholder catalogue result', 'tool_calls': []} if ran_skill else {
            'content': None, 'tool_calls': [{'name': 'skala_run', 'arguments': {
                'skill_id': 'rig.search', 'version': '1.0.0', 'input': {'query': 'placeholder'}}}]}
        if getattr(wire, 'provider_mode', '') == 'malformed':
            answer = {'invalid': 'placeholder invalid model contract'}
        cost = getattr(wire, 'provider_cost', 0.05)
        wire.provider_calls.append({'cost_usd': cost, 'tokens_in': 10, 'tokens_out': 3,
                                    'model': body['model']})
        return JSONResponse({'id': 'placeholder-completion', 'object': 'chat.completion',
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(answer)}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}},
            headers={'x-litellm-response-cost': str(cost)})

    app = FastAPI()
    wire.sdk_calls = []

    @app.middleware('http')
    async def memory_edge(request, call_next):
        if request.url.path.startswith('/v1/agents/rig/') and request.method == 'POST':
            wire.sdk_calls.append((request.url.path, request.url.query, dict(request.headers), await request.body()))
        # Outage injection is at HTTP, never inside Hermes/SQL/ownership code.
        if request.url.path.startswith('/hermes/') and wire.memory_failure:
            path, status = wire.memory_failure
            if path is None or request.url.path == '/hermes' + path:
                return JSONResponse({'detail': 'placeholder unavailable'}, status_code=status)
        return await call_next(request)

    app.mount('/hermes', wire.stack.app)
    app.mount('/litellm', fake)
    app.mount('/', tank.app)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    origin = 'http://127.0.0.1:' + str(listener.getsockname()[1])
    monkeypatch.setenv('TANK_URL', origin)
    monkeypatch.setenv('HERMES_URL', origin + '/hermes')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setattr(tank, 'LITELLM_URL', origin + '/litellm')
    monkeypatch.setattr(tank, 'LITELLM_MASTER_KEY', 'placeholder-provider-key')
    actual_http = httpx.AsyncHTTPTransport()

    async def outbound(request):
        if request.url.host == '127.0.0.1' and request.url.port == listener.getsockname()[1]:
            return await actual_http.handle_async_request(request)
        if request.url.host == 'rig-brain':
            assert request.url.scheme == 'http' and request.url.port == 8001
            assert request.url.path.startswith(('/tasks', '/delegate'))
            import rig_brain.service as brain
            return await httpx.ASGITransport(app=brain.app).handle_async_request(request)
        if request.url.host == 'agent-rig':
            return await httpx.ASGITransport(app=wire.product).handle_async_request(request)
        raise AssertionError('Unrecorded external network destination')

    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level='error', lifespan='off'))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    async with paid_http.Client(transport=httpx.MockTransport(outbound), timeout=15) as http:
        monkeypatch.setattr(tank, '_http', http)
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                        raise RuntimeError('Loopback fixture did not start')
                    await asyncio.sleep(0.01)
            yield
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=10)
            listener.close()
            await actual_http.aclose()
