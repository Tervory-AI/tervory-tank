"""Resolve the configured image payload without Docker or service activation."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pgserver
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_configured_private_image_imports_handler_and_verifies_sql_nonces(tmp_path):
    service = yaml.safe_load((ROOT / 'agents/market_lab/docker-compose.yml').read_text())['services']['market-lab-brain']
    assert service['profiles'] == ['brain']
    assert service['environment']['MARKET_LAB_BRAIN_ENABLED'] == '${MARKET_LAB_BRAIN_ENABLED:-false}'
    assert service['environment']['DATABASE_URL'] == yaml.safe_load(
        (ROOT / 'agents/market_lab/docker-compose.yml').read_text())['services']['agent-market-lab']['environment']['DATABASE_URL']
    assert service['networks'] == ['gw', 'sandbox']
    assert not service.get('ports')
    assert service['read_only'] and service['cap_drop'] == ['ALL']
    assert service['mem_limit'] == '2g' and service['cpus'] == 1 and service['pids_limit'] == 128
    context = (ROOT / 'agents/market_lab' / service['build']['context']).resolve()
    dockerfile = context / service['build']['dockerfile']
    assert dockerfile == ROOT / 'agents/market_lab/Dockerfile'
    command = service['command']
    assert command[:2] == ['uvicorn', 'market_lab_brain_service:app']
    assert command[command.index('--port') + 1] == '8001'
    # Resolve the actual COPY declarations, rather than injecting test-only
    # modules into the image. Runtime dependencies must come from that payload.
    image = tmp_path / 'image'
    for line in dockerfile.read_text().splitlines():
        if not line.startswith('COPY '):
            continue
        _, source, destination = shlex.split(line)
        source_path = context / source
        target = image / destination.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(source_path, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, target)
    app_dir = image / 'app'
    assert (app_dir / 'market_lab_brain_service.py').read_bytes() == (
        ROOT / 'agents/market_lab/market_lab_brain_service.py').read_bytes()
    requirements = (image / 'tmp/chassis-requirements.txt').read_text()
    for dependency in ('asyncpg==', 'httpx==', 'fastapi==', 'uvicorn['):
        assert dependency in requirements
    server = pgserver.get_server(tmp_path / 'postgres')
    try:
        env = {**os.environ, 'PYTHONPATH': str(app_dir), 'DATABASE_URL': server.get_uri(),
               'MARKET_LAB_BRAIN_ENABLED': 'false', 'TANK_KEY': 'placeholder-packaging-key',
               'TANK_KEY_MARKET_LAB': 'placeholder-packaging-key', 'PACKAGED_HANDLER': command[1]}
        result = subprocess.run([sys.executable, '-c', PROBE], cwd=app_dir, env=env,
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'packaged handler: default-off, signed SQL nonce, restart replay and scope PASS' in result.stdout
    finally:
        server.cleanup()


PROBE = r'''
import asyncio, importlib, json, os
from pathlib import Path
from uuid import uuid4
import httpx
from uvicorn.importer import import_from_string
from chassis.user_assertion import SignedUser, sign_assertion, HEADER

async def main():
    target = os.environ['PACKAGED_HANDLER']
    app = import_from_string(target)
    module = importlib.import_module(target.split(':')[0])
    assert Path(module.__file__).resolve().parent == Path.cwd()
    for name in ('chassis.user_assertion', 'chassis.tank', 'chassis.task_contract'):
        loaded = importlib.import_module(name)
        assert Path.cwd() in Path(loaded.__file__).resolve().parents
    async with app.router.lifespan_context(app):
        pool = app.state.pool
        await pool.execute('CREATE SCHEMA agent_market_lab')
        actor = SignedUser(str(uuid4()), 'placeholder-owner', 'member')
        path = '/tasks?tenant_id=' + actor.tenant_id + '&user_id=' + actor.user_id
        raw = json.dumps({}).encode()
        headers = {'Content-Type':'application/json', 'X-Tank-Key':os.environ['TANK_KEY']}
        async def send(application, body=raw, extra=None, target=path):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://placeholder-private') as http:
                return await http.post(target, content=body, headers={**headers, **(extra or {})})
        assert (await send(app)).status_code == 409
        assert await pool.fetchval("SELECT to_regclass('agent_market_lab.user_assertion_nonces')") is None
        os.environ['MARKET_LAB_BRAIN_ENABLED'] = 'true'  # Isolated transport proof only.
        assert (await send(app)).status_code == 401
        token = sign_assertion('market_lab', actor, 'POST', path, raw, key=os.environ['TANK_KEY'])
        signed = {HEADER:token}
        # A valid assertion reaches real input validation, without model work.
        assert (await send(app, extra=signed)).status_code == 422
        assert await pool.fetchval('SELECT count(*) FROM agent_market_lab.user_assertion_nonces') == 1
        assert (await send(app, extra=signed)).status_code == 401
        fresh = importlib.reload(module).app
        async with fresh.router.lifespan_context(fresh):
            assert (await send(fresh, extra=signed)).status_code == 401
            peer_path = path.replace('user_id=placeholder-owner', 'user_id=placeholder-peer')
            peer = {HEADER:sign_assertion('market_lab', actor, 'POST', peer_path, raw, key=os.environ['TANK_KEY'])}
            assert (await send(fresh, extra=peer, target=peer_path)).status_code == 403
            tampered = {HEADER:sign_assertion('market_lab', actor, 'POST', path, raw, key=os.environ['TANK_KEY'])}
            assert (await send(fresh, body=raw+b' ', extra=tampered)).status_code == 401
    print('packaged handler: default-off, signed SQL nonce, restart replay and scope PASS')

asyncio.run(main())
'''
