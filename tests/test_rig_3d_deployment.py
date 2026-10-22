"""Boot the actual image CMD, preserve public routes and keep the brain private."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys

from test_rig_postgres import _admin_url, _create_database, _drop_database, _database_url
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]


def test_docker_cmd_preserves_public_api_health_and_private_brain(tmp_path):
    admin, name = _admin_url(), 'rig3d_boot_' + uuid4().hex
    asyncio.run(_create_database(admin, name))
    script = r'''
import importlib, json, os, re, secrets
from pathlib import Path
from fastapi.testclient import TestClient
from uvicorn.importer import import_from_string
from rigbox.three_d.sample import seed, PUBLIC_KEY

root = Path.cwd()
base = importlib.import_module('app').app
routes = [(r.path, r.methods, r.endpoint) for r in base.routes if hasattr(r, 'methods')]
def protected_surface(client):
    responses = {}
    for path, methods, _ in routes:
        concrete = re.sub(r'\{[^}]+\}', 'fixture', path)
        for method in sorted(methods):
            response = client.request(method, concrete)
            assert response.status_code < 500, (method, path, response.status_code)
            responses[(method, path)] = (response.status_code, response.content)
    return responses

with TestClient(base) as client:
    before = protected_surface(client)
    assert client.get('/health').json() == {'ok': True, 'agent': 'rig'}
cmd = json.loads(next(line[4:] for line in (root/'agents/rig/Dockerfile').read_text().splitlines() if line.startswith('CMD ')))
assert cmd == ['uvicorn', 'rigbox.three_d.asgi:app', '--host', '0.0.0.0', '--port', '8000']
deployed = import_from_string(cmd[1])
assert deployed is base
assert all(any(r.path == path and r.methods == methods and r.endpoint is endpoint
               for r in deployed.routes if hasattr(r, 'methods')) for path, methods, endpoint in routes)
with TestClient(deployed) as client:
    assert protected_surface(client) == before
    assert deployed.state.rig_three_d.assets.instance is None
    assert client.get('/health').json() == {'ok': True, 'agent': 'rig'}
    # Seed only this isolated test database. The production lifespan never does.
    client.portal.call(seed, deployed.state.pool, Path(os.environ['DATA_DIR']))
    headers = {'X-Rig-Key': PUBLIC_KEY}
    for path in ['/v1/rig/search?q=centre', '/v1/rig/products/centre', '/v1/rig/graph/centre']:
        assert client.get(path, headers=headers).status_code == 200, path
    setup = client.post('/v1/rig/setups', headers=headers, json={'product_id':'centre'})
    assert setup.status_code == 200
    assert client.post('/v1/rig/compare', headers=headers, json={'product_ids':['centre', 'part-a']}).status_code == 200
    assert client.get('/v1/rig/3d/capabilities', headers=headers).json()['rig_3d'] is True
    assert client.get('/3d/').status_code == 200
    for auth in ({}, headers, {'X-Tank-Key': os.environ['TANK_KEY']}):
        assert client.post('/brain/tasks', headers=auth, json={}).status_code == 404
        for method in ['GET', 'DELETE']:
            assert client.request(method, '/brain/tasks/'+str(__import__('uuid').uuid4()), headers=auth).status_code == 404
    pool = deployed.state.pool
    deployed.state.pool = None
    assert client.get('/health').status_code == 503
    deployed.state.pool = pool
'''
    env = {**os.environ, 'PYTHONPATH': 'agents/rig:agents/_chassis', 'AGENT_NAME': 'rig',
           'DATABASE_URL': _database_url(admin, name), 'DATA_DIR': str(tmp_path),
           'TANK_KEY': uuid4().hex, 'CATALOGUE_DIR': str(tmp_path / 'empty-catalogues')}
    (tmp_path / 'empty-catalogues').mkdir()
    try:
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        asyncio.run(_drop_database(admin, name))
