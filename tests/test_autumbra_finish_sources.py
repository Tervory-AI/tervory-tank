from contextlib import asynccontextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from agents.ghost import inventory, market_lab_intel
from agents.ghost.deployments import deployment_observation
from agents.ghost.models import Look
from agents.ghost.probes import Probes


@pytest.mark.asyncio
@pytest.mark.parametrize('status, failing', [('failed', True), ('finished', False), ('cancelled', True)])
async def test_coolify_real_response_contract_is_read_only_and_uses_latest_deployment(monkeypatch, status, failing):
    monkeypatch.setenv('COOLIFY_URL_GHOST', 'https://coolify.example.test')
    monkeypatch.setenv('COOLIFY_TOKEN_GHOST', 'fixture-read-only')
    calls = []

    def source(request):
        calls.append(request)
        assert request.method == 'GET'
        assert request.headers['authorization'] == 'Bearer fixture-read-only'
        if request.url.path == '/api/v1/applications':
            return httpx.Response(200, json=[{'name': 'main', 'uuid': 'app-one', 'fqdn': 'https://app.tervory.com'}])
        assert request.url.path == '/api/v1/deployments/applications/app-one'
        return httpx.Response(200, json={'deployments': [
            {'status': 'failed', 'created_at': '2026-11-01T12:00:00Z', 'logs': 'not retained'},
            {'status': status, 'created_at': '2026-11-05T12:00:00Z'}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(source)) as http:
        tank = AsyncMock()
        result = await Probes(http, tank, '').reproduce(Look(target='workspace', signal='deploy'))
    assert result.failing is failing and result.count == 1
    assert len(calls) == 2 and 'not retained' not in result.model_dump_json()
    tank.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_coolify_partial_or_redirected_data_never_claims_success(monkeypatch):
    monkeypatch.setenv('COOLIFY_TOKEN_GHOST', 'fixture-read-only')
    monkeypatch.setenv('COOLIFY_URL_GHOST', 'https://coolify.example.test')
    calls = []

    def bad(request):
        calls.append(request)
        return httpx.Response(302, headers={'location': 'https://unrelated.example/'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(bad)) as http:
        with pytest.raises(RuntimeError):
            await deployment_observation(http, 'tank')
    assert len(calls) == 1
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as http:
        with pytest.raises(RuntimeError):
            await inventory.fetch_coolify(http)


def test_market_lab_unknown_source_rejected_and_missing_bundle_id_is_stable():
    raw = {'schema_version': 'market_lab.ioc.v1', 'paid': False,
           'sources': [{'id': 'nvd', 'name': 'NVD'}],
           'indicators': [{'kind': 'cve', 'value': 'CVE-2026-12345', 'source_ids': ['nvd']}]}
    assert market_lab_intel.accept_ioc_bundle(raw)['bundle_id'] == market_lab_intel.accept_ioc_bundle(raw)['bundle_id']
    raw['indicators'][0]['source_ids'] = ['invented']
    with pytest.raises(ValueError):
        market_lab_intel.accept_ioc_bundle(raw)


def patch_module():
    # Compile the proposed new module directly from its diff. Never apply the patch.
    patch = (Path(__file__).resolve().parents[1] / 'tank-patches/finish.patch').read_text()
    section = patch.split('diff --git a/tank/ghost_evidence.py b/tank/ghost_evidence.py\n')[1]
    code = '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+') and not line.startswith('+++'))
    module = ModuleType('proposed_ghost_evidence')
    exec(compile(code, 'tank-patches/finish.patch:ghost_evidence.py', 'exec'), module.__dict__)
    assert 'return await observation(runtime(), body.target, body.signal)' in patch
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize('target,signal,values,expected', [
    ('tank', 'errors', [3], 3), ('workspace', 'errors', [0], 0),
    ('tank', 'radix', [True, 2], 2), ('tank', 'radix', [False], None),
])
async def test_tank_patch_reads_real_tenant_scoped_counts_without_raw_details(target, signal, values, expected):
    evidence = patch_module()
    conn = AsyncMock()
    conn.fetchval.side_effect = values

    @asynccontextmanager
    async def transaction(**kwargs):
        assert kwargs == {'readonly': True}
        yield

    conn.transaction = transaction

    @asynccontextmanager
    async def acquire():
        yield conn

    core = SimpleNamespace(PLATFORM_TENANT='00000000-0000-0000-0000-000000000001',
        box_region=lambda: 'us-east', tank_sha=lambda: 'a'*40, pool=lambda: SimpleNamespace(acquire=acquire))
    if expected is None:
        with pytest.raises(HTTPException) as error:
            await evidence.observation(core, target, signal)
        assert error.value.status_code == 503
    else:
        result = await evidence.observation(core, target, signal)
        assert result == {'target': target, 'signal': signal, 'count': expected, 'failing': expected > 0}
    for call in conn.fetchval.await_args_list:
        assert 'tenant_id=$1' in call.args[0]
        assert call.args[1] == core.PLATFORM_TENANT
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('state, complete, moved, expected', [
    ('success', True, False, False), ('failure', True, False, True),
    ('pending', True, False, None), ('success', False, False, None), ('success', True, True, None),
])
async def test_tank_patch_ci_reads_exact_main_and_refuses_incomplete_evidence(monkeypatch, state, complete, moved, expected):
    import command_repo
    evidence = patch_module()

    @asynccontextmanager
    async def github():
        yield object()

    monkeypatch.setattr(command_repo, 'github', github)
    monkeypatch.setattr(command_repo, '_get', AsyncMock(side_effect=[
        ({'object': {'sha': 'a'*40}}, False), ({'object': {'sha': ('b' if moved else 'a')*40}}, False)]))
    monkeypatch.setattr(command_repo, '_checks', AsyncMock(return_value={'checks_state': state, 'checks_complete': complete}))
    if expected is None:
        with pytest.raises(HTTPException) as error:
            await evidence.observation(None, 'tank', 'ci')
        assert error.value.status_code == 503
    else:
        assert (await evidence.observation(None, 'tank', 'ci'))['failing'] is expected
    assert all(call.args[1] == 'git/ref/heads/main' for call in command_repo._get.await_args_list)
