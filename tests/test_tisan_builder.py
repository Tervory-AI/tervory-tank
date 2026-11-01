"""Builder contract and archive tests. All copy responses are test doubles."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import tarfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
TENANT = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


def load(path=ROOT / 'agents/tisan/builder.py'):
    spec = importlib.util.spec_from_file_location('test_builder_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def builder():
    return load()


def plan():
    return {'nav': [{'href': '/'}], 'ui': {}, 'pages': [
        {'name': 'home', 'path': '/', 'sections': [{'id': 'hero-1', 'type': 'hero', 'props': {}}]}]}


def payload():
    return {'name': 'Test build', 'slug': 'test-build', 'locale': 'en', 'brand': {
        'colours': {'ink': '#001840', 'paper': '#F4F6FB', 'accent': '#E80008', 'line': '#B8BFD0'},
        'fonts': {'heading': 'Jost', 'body': 'Inter'}}, 'plan': plan()}


def copy_for(builder, value):
    return {key: str(uuid.uuid4()) for key, _, _, _, _, image in builder.slots(value, builder.manifest()) if not image}


def client_for(tenant=TENANT, *, text='Accepted test copy', wrong_write=False, status=200):
    def respond(request):
        wid = request.url.path.rsplit('/', 1)[-1]
        return httpx.Response(status, json={'tenant_id': tenant, 'write_id': str(uuid.uuid4()) if wrong_write else wid, 'text': text})
    return httpx.AsyncClient(transport=httpx.MockTransport(respond))


@pytest.mark.asyncio
async def test_copy_needed_has_purpose_and_no_work(builder, tmp_path):
    p = payload()
    result = await builder.execute(p, TENANT, data_root=tmp_path)
    needed = {item['key']: item for item in result['copy_needed']}
    assert needed['home/hero-1/heading'] == {'key': 'home/hero-1/heading', 'section_type': 'hero', 'purpose': "the section's heading"}
    assert 'site/nav/0/label' in needed and 'home/title' in needed
    assert not list(tmp_path.iterdir())
    assert p == payload()


@pytest.mark.parametrize('mutate', [
    lambda p: p['pages'][0]['sections'][0].update(type='invented'),
    lambda p: p['pages'][0]['sections'][0]['props'].update(unknown='x'),
    lambda p: p['pages'][0]['sections'].append(copy.deepcopy(p['pages'][0]['sections'][0])),
    lambda p: p['pages'][0].update(title='Unaccepted text'),
    lambda p: p['pages'][0]['sections'][0]['props'].update(heading='Unaccepted text'),
    lambda p: p['pages'][0].update(path='/../escape'),
    lambda p: p.update(extra=True),
    lambda p: p['nav'][0].update(href='javascript:alert(1)'),
])
def test_refuse_invalid_plan(builder, mutate):
    p = plan()
    mutate(p)
    with pytest.raises(ValueError):
        builder.validate_plan(p, builder.manifest())


@pytest.mark.asyncio
async def test_request_retries_once_and_supplies_purposes(builder):
    tank = SimpleNamespace(route=AsyncMock(side_effect=[{'content': '{}'}, {'content': json.dumps(plan())}]))
    result = await builder.make_plan({'request': 'one page'}, TENANT, builder.manifest(), tank)
    assert result == plan() and tank.route.await_count == 2
    first = tank.route.call_args_list[0].args
    assert first[:2] == (TENANT, 'tisan.plan')
    assert 'purpose' in first[2][0]['content']
    assert 'validation errors' in tank.route.call_args_list[1].args[2][-1]['content']


@pytest.mark.asyncio
async def test_invalid_retry_fails_without_third_call(builder):
    tank = SimpleNamespace(route=AsyncMock(return_value={'content': 'invalid json'}))
    with pytest.raises(ValueError, match='invalid plan after retry'):
        await builder.make_plan({'request': 'one page'}, TENANT, builder.manifest(), tank)
    assert tank.route.await_count == 2


@pytest.mark.asyncio
async def test_given_plan_never_routes(builder):
    tank = SimpleNamespace(route=AsyncMock(side_effect=AssertionError('no model for a written plan')))
    assert await builder.make_plan({'plan': plan(), 'request': 'ignored'}, TENANT, builder.manifest(), tank) == plan()
    tank.route.assert_not_awaited()


def test_array_slot_expansion_and_media(builder):
    p = plan()
    p['logo'] = {}
    p['pages'][0]['sections'] = [{'type': 'gallery', 'id': 'photos', 'props': {'images': [{}, {}]}}]
    builder.validate_plan(p, builder.manifest())
    values = {s[0]: s for s in builder.slots(p, builder.manifest())}
    assert values['home/photos/images/1/alt'][2] == 'what each image shows'
    assert values['home/photos/images/0/src'][5] is True
    assert values['site/logo/src'][5] is True


@pytest.mark.asyncio
async def test_media_needed_is_not_invented(builder, tmp_path):
    p = payload()
    p['plan']['logo'] = {}
    p['copy'] = copy_for(builder, p['plan'])
    result = await builder.execute(p, TENANT, data_root=tmp_path)
    assert result['media_needed'][0]['key'] == 'site/logo/src'
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('url', ['http://example.com/x', 'https://user:pass@example.com/x', '/media/../private', 'data:image/png;base64,x', '//example.com/x'])
def test_unsafe_media_refused(builder, url):
    assert not builder._media_url(url)


@pytest.mark.parametrize('url', ['https://example.com/photo.png', '/media/photo.png'])
def test_supplied_media_allowed(builder, url):
    assert builder._media_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize('foreign,wrong_write,status', [(True, False, 200), (False, True, 200), (False, False, 404), (False, False, 409)])
async def test_copy_isolation_and_acceptance(builder, foreign, wrong_write, status):
    async with client_for(OTHER if foreign else TENANT, wrong_write=wrong_write, status=status) as client:
        with pytest.raises(ValueError):
            await builder.accepted_copy(client, TENANT, str(uuid.uuid4()), base='http://tank:8000', key='test-room-key', region='za')


@pytest.mark.asyncio
async def test_copy_headers_and_redirects(builder):
    wid = str(uuid.uuid4())
    def respond(request):
        assert request.headers['X-Tervory-Tenant'] == TENANT
        assert request.headers['X-Tervory-Home-Region'] == 'za'
        assert request.headers['X-Tank-Key'] == 'test-room-key'
        assert request.url.path == '/v1/trigger/copy/' + wid
        assert request.url.params['tenant_id'] == TENANT
        return httpx.Response(200, json={'tenant_id': TENANT, 'write_id': wid, 'text': 'Accepted test copy'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await builder.accepted_copy(client, TENANT, wid, base='http://tank:8000', key='test-room-key', region='za') == 'Accepted test copy'


@pytest.mark.asyncio
async def test_invalid_copy_id_has_no_http_read(builder):
    http = SimpleNamespace(get=AsyncMock())
    with pytest.raises(ValueError):
        await builder.accepted_copy(http, TENANT, '../other', base='http://tank:8000', key='', region='us-east')
    http.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_check_returns_output_without_archive(builder, monkeypatch, tmp_path):
    scaffold = builder._scaffold()
    scaffold.run_checks = AsyncMock(return_value=([{'name': 'npm ci', 'ok': False}], 'offline cache missing'))
    monkeypatch.setattr(builder, '_scaffold', lambda: scaffold)
    p = payload()
    p['copy'] = copy_for(builder, p['plan'])
    async with client_for() as client:
        result = await builder.execute(p, TENANT, http=client, data_root=tmp_path)
    assert result == {'ok': False, 'checks': [{'name': 'npm ci', 'ok': False}], 'detail': 'offline cache missing'}
    assert not list(tmp_path.rglob('*.tar.gz'))
    scaffold.run_checks.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_contains_accepted_content(builder, monkeypatch, tmp_path):
    scaffold = builder._scaffold()
    scaffold.run_checks = AsyncMock(return_value=([{'name': 'test check double', 'ok': True}], ''))
    monkeypatch.setattr(builder, '_scaffold', lambda: scaffold)
    p = payload()
    p['copy'] = copy_for(builder, p['plan'])
    async with client_for() as client:
        result = await builder.execute(p, TENANT, http=client, data_root=tmp_path)
    assert result['ok'] and result['archive'] == str(tmp_path / 'builds' / TENANT / 'test-build/1.tar.gz')
    with tarfile.open(result['archive']) as archive:
        name = next(n for n in archive.getnames() if n.endswith('content/site.json'))
        content = json.load(archive.extractfile(name))
    assert content['schema'] == 'tisan.content/1'
    assert content['pages'][0]['title'] == 'Accepted test copy'
    assert content['pages'][0]['sections'][0]['props']['heading'] == 'Accepted test copy'
    assert content['nav'][0]['label'] == 'Accepted test copy'
    assert json.loads(Path(result['archive']).with_suffix('').with_suffix('.json').read_text())['ok']


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get('TISAN_RUN_BUILD') != '1', reason='explicit offline npm build check')
async def test_full_build_with_real_checks(builder, tmp_path):
    p = payload()
    p['plan']['pages'].append({'name': 'privacy', 'path': '/privacy', 'sections': []})
    p['plan']['nav'].append({'href': '/privacy'})
    p['copy'] = copy_for(builder, p['plan'])
    async with client_for() as client:
        result = await builder.execute(p, TENANT, http=client, data_root=tmp_path)
    print(json.dumps(result, indent=2))
    assert result['ok'], result
    assert [c['name'] for c in result['checks']] == ['npm ci', 'npm run lint', 'npm run build', 'npm test']
    assert all(c['ok'] for c in result['checks'])
