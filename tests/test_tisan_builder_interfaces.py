"""Exercise dependency source through ASGI and a real built Next.js server.

Before dependency merges, point TISAN_TRIGGER_ROUTES at #567's actual module and
TISAN_TEMPLATE at #570's actual template. Neither is replaced with a fixture.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import html
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tarfile
from types import SimpleNamespace
import uuid

from fastapi import FastAPI
import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
TENANT = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest_asyncio.fixture
async def interface(monkeypatch):
    path = Path(os.environ.get('TISAN_TRIGGER_ROUTES', ROOT / 'tank/trigger_routes.py'))
    routes = module_at('tisan_actual_trigger_routes_test', path)
    if not hasattr(routes, 'accepted_copy'):
        pytest.skip('actual #567 copy endpoint has not been merged; set TISAN_TRIGGER_ROUTES to its source')
    accepted = {}
    reads = []

    async def fetchrow(sql, write_id, tenant):
        # Only the DB is a test double. Request parsing/auth/SQL/response are real.
        assert "w.tenant_id=$2" in sql and "feedback_status='accepted'" in sql
        assert "'confirmed'" in sql
        reads.append((str(write_id), str(tenant)))
        text = accepted.get((str(write_id), str(tenant)))
        return {'draft': text} if text is not None else None

    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(fetchrow=fetchrow)

    pool = SimpleNamespace(acquire=acquire)
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(box_region=lambda: 'us-east', pool=lambda: pool))
    monkeypatch.setenv('TANK_KEY_TISAN', 'test-room-key')
    monkeypatch.setenv('TANK_KEY', 'test-room-key')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    app = FastAPI()
    app.include_router(routes.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank:8000') as client:
        yield SimpleNamespace(http=client, accepted=accepted, reads=reads)


@pytest.mark.asyncio
async def test_actual_copy_route_requires_and_receives_query_tenant(interface):
    builder = module_at('tisan_interface_builder_copy', ROOT / 'agents/tisan/builder.py')
    wid = str(uuid.uuid4())
    interface.accepted[wid, TENANT] = 'Accepted integration copy'
    headers = {'X-Tank-Key': 'test-room-key', 'X-Tervory-Tenant': TENANT, 'X-Tervory-Home-Region': 'us-east'}
    missing_query = await interface.http.get('/v1/trigger/copy/' + wid, headers=headers)
    assert missing_query.status_code == 422
    assert await builder.accepted_copy(interface.http, TENANT, wid, base='http://tank:8000', key='test-room-key', region='us-east') == 'Accepted integration copy'
    assert interface.reads == [(wid, TENANT)]
    with pytest.raises(ValueError, match='HTTP 404'):
        await builder.accepted_copy(interface.http, OTHER, wid, base='http://tank:8000', key='test-room-key', region='us-east')
    assert interface.reads[-1] == (wid, OTHER)
    with pytest.raises(ValueError, match='HTTP 403'):
        await builder.accepted_copy(interface.http, TENANT, wid, base='http://tank:8000', key='test-room-key', region='za')
    mismatch = await interface.http.get('/v1/trigger/copy/' + wid, params={'tenant_id': OTHER}, headers=headers)
    assert mismatch.status_code == 403
    denied = await interface.http.get('/v1/trigger/copy/' + wid, params={'tenant_id': TENANT}, headers={**headers, 'X-Tank-Key': 'wrong-test-key'})
    assert denied.status_code == 401


def test_policy_survives_actual_schema_generator(tmp_path):
    generator = module_at('tisan_schema_generator_test', ROOT / 'hermes/record_schema.py')
    original = (ROOT / 'tank/schema.sql').read_text()
    (tmp_path / 'tank').mkdir()
    (tmp_path / 'tank/schema.sql').write_text(original)
    generator.update_files(tmp_path)
    assert (tmp_path / 'tank/schema.sql').read_text() == original
    assert "'tisan.plan'" in original.split(generator.BEGIN)[0]
    assert original.endswith(generator.END + '\n')


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get('TISAN_RUN_BUILD') != '1', reason='explicit real build and loopback server check')
async def test_built_custom_route_uses_accepted_content_and_keeps_contact_api(interface, tmp_path):
    builder = module_at('tisan_interface_builder_build', ROOT / 'agents/tisan/builder.py')
    scaffold = builder._scaffold()
    template = scaffold.template_dir()
    if not (template / 'app/[[...path]]/page.tsx').is_file():
        pytest.skip('actual #570 content renderer has not been merged; set TISAN_TEMPLATE to its source')
    pages = [{'name': name, 'path': '/' if name == 'home' else '/' + name,
              'sections': [{'id': 'hero-1', 'type': 'hero', 'props': {}}] if name in {'support', 'about'} else []}
             for name in ['home', 'support', 'about', 'contact', 'privacy']]
    plan = {'nav': [{'href': page['path']} for page in pages], 'ui': {}, 'pages': pages}
    copy_ids = {}
    for key, _, _, _, _, image in builder.slots(plan, builder.manifest()):
        assert not image
        wid = str(uuid.uuid4())
        copy_ids[key] = wid
        interface.accepted[wid, TENANT] = 'Accepted ' + key.replace('/', ' ')
    payload = {'name': 'Integration build', 'slug': 'integration-build', 'brand': {
        'colours': {'ink': '#001840', 'paper': '#F4F6FB', 'accent': '#E80008', 'line': '#B8BFD0'},
        'fonts': {'heading': 'Jost', 'body': 'Inter'}}, 'plan': plan, 'copy': copy_ids}
    result = await builder.execute(payload, TENANT, http=interface.http, data_root=tmp_path / 'data')
    print(json.dumps(result, indent=2))
    assert result['ok'], result
    assert [item['name'] for item in result['checks']] == ['npm ci', 'npm run lint', 'npm run build', 'npm test']
    assert all(item['ok'] for item in result['checks'])
    assert len(interface.reads) == len(copy_ids)
    project = tmp_path / 'serve'
    project.mkdir()
    with tarfile.open(result['archive']) as archive:
        archive.extractall(project, filter='data')
    assert (project / 'app/[[...path]]/page.tsx').is_file()
    assert not (project / 'app/support/page.tsx').exists()
    assert not (project / 'app/about/page.tsx').exists()
    assert (project / 'app/contact/page.tsx').is_file()
    assert (project / 'app/privacy/page.tsx').is_file()
    assert (project / 'app/api/contact/route.ts').is_file()
    content = json.loads((project / 'content/site.json').read_text())
    assert content['pages'][1]['sections'][0]['props']['heading'] == 'Accepted support hero-1 heading'
    # The archive excludes .next/node_modules by scaffold contract. Build the
    # extracted archive unchanged, then serve its actual production routes.
    checks, detail = await scaffold.run_checks(project)
    assert not detail and all(item['ok'] for item in checks), (checks, detail)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    with (tmp_path / 'next-start.log').open('wb') as log:
        server = await asyncio.create_subprocess_exec('npm', 'run', 'start', '--', '--hostname', '127.0.0.1', '--port', str(port), cwd=project, env=scaffold._check_env(), stdout=log, stderr=log, start_new_session=True)
        try:
            async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', trust_env=False) as client:
                for _ in range(100):
                    try:
                        response = await client.get('/support')
                        break
                    except httpx.ConnectError:
                        if server.returncode is not None:
                            pytest.fail((tmp_path / 'next-start.log').read_text())
                        await asyncio.sleep(0.1)
                else:
                    pytest.fail('built Next server did not start')
                assert response.status_code == 200
                assert '<title>Accepted support title</title>' in html.unescape(response.text)
                about = await client.get('/about')
                assert about.status_code == 200
                assert '<title>Accepted about title</title>' in html.unescape(about.text)
                assert (await client.get('/privacy')).status_code == 200
                contact = await client.get('/contact')
                assert contact.status_code == 200 and '/api/contact' in contact.text
                posted = await client.post('/api/contact', data={'name': 'Test', 'email': 'test@example.invalid', 'message': 'Test'})
                assert posted.status_code == 202 and posted.json() == {'ok': True}
                assert (await client.get('/not-a-planned-page')).status_code == 404
        finally:
            import signal
            os.killpg(server.pid, signal.SIGTERM)
            await asyncio.wait_for(server.wait(), timeout=10)
