"""M12 rules-only settings and the real stored-match to draft-PR corridor."""
import base64
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import httpx
import pytest
from fastapi import FastAPI

import command
import ghost_routes
import trigger_routes
from trigger_commands import CONFIRMED
from agents.ghost.app import create_app, PLATFORM_TENANT
from agents.ghost.client_settings import ClientAutumbraSettings, ApplyMode, load_settings
from agents.ghost import patch_pr
from agents.ghost.store import Store

ROOT = Path(__file__).resolve().parents[1]
A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'


def test_fix_mode_legacy_and_shield_modes():
    for mode in ApplyMode:
        assert ClientAutumbraSettings(tenant_id=A, shield_mode=mode).shield_mode == mode
    normalized = ClientAutumbraSettings(tenant_id=A, fix_mode=ApplyMode.auto_when_checks_pass)
    assert normalized.fix_mode == ApplyMode.approve_each
    legacy = {'fix_mode': ApplyMode.auto_when_checks_pass.value, 'shield_mode': ApplyMode.never.value}
    result = load_settings(SimpleNamespace(get_state=lambda *args: legacy), A)
    assert result.fix_mode == ApplyMode.approve_each and result.shield_mode == ApplyMode.never
    assert legacy['fix_mode'] == ApplyMode.auto_when_checks_pass.value


@pytest.mark.asyncio
async def test_stored_matches_dry_run_and_fake_github(tmp_path, monkeypatch):
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.delenv('GHOST_PATCH_PR_ENABLED', raising=False)
    monkeypatch.delenv('PATCH_PR_ENABLED', raising=False)
    app = create_app()
    store = Store(tmp_path / 'placeholder.sqlite3')
    app.state.store = store
    sample = json.loads((ROOT / 'tests/fixtures/autumbra/patch_connect_match.json').read_text())
    sample['flagged_at'] = '2026-11-03T00:00:00Z'
    match, _ = store.open_match(PLATFORM_TENANT, 'placeholder-eligible', sample)
    foreign, _ = store.open_match(PLATFORM_TENANT, 'placeholder-foreign', {**sample, 'repo': 'placeholder/foreign'})
    calls = []
    def fake_send(self, method, url, body=None):
        calls.append((method, url, body))
        assert '/merges' not in url and method != 'PUT'
        if url.endswith('/pulls'):
            assert method == 'POST' and body['draft'] is True
            return 201, {'html_url': 'https://github.com/Tervory-AI/tervory-tank/pull/999999', 'number': 999999}
        if '/contents/' in url:
            return 200, {'content': base64.b64encode(b'requests==2.31.0\n').decode(), 'sha': 'placeholder-file'}
        if '/git/ref/' in url:
            return 200, {'object': {'sha': 'placeholder-base'}}
        if method == 'GET' and '/git/commits/' in url:
            return 200, {'tree': {'sha': 'placeholder-base-tree'}}
        if method == 'GET':
            return 200, {'default_branch': 'main'}
        return (200 if method == 'PATCH' else 201), {'sha': 'placeholder-sha'}
    monkeypatch.setattr(patch_pr.GitHubClient, '_default_send', fake_send)
    monkeypatch.setattr(patch_pr.GitHubClient, '_default_get', lambda self, url: fake_send(self, 'GET', url))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
            headers = {'X-Tank-Key': 'placeholder-room-key'}
            listed = await client.get('/ghost/patch/fixes', headers=headers)
            assert [row['id'] for row in listed.json()['items']] == [match['id']]
            refused = await client.post('/ghost/patch/from-match', headers=headers, json={'match_id': foreign['id']})
            assert refused.status_code == 422
            dry = await client.post('/ghost/patch/from-match', headers=headers, json={'match_id': match['id']})
            assert dry.json()['result']['mode'] == 'dry_run' and not calls
            monkeypatch.setenv('GHOST_PATCH_PR_ENABLED', '1')
            monkeypatch.setenv('GHOST_GITHUB_TOKEN', 'placeholder-github-token')
            opened = await client.post('/ghost/patch/from-match', headers=headers, json={'match_id': match['id']})
            assert opened.status_code == 200
            assert opened.json()['pr_url'].endswith('/999999') and opened.json()['result']['draft']
            assert any(url.endswith('/pulls') for _, url, _ in calls)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_tank_fix_confirmation_and_receipts(monkeypatch):
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    actor = command.Actor(uuid.UUID(A), 'placeholder-founder', True)
    monkeypatch.setattr(command, 'identity', AsyncMock(return_value=actor))
    room = AsyncMock(return_value=httpx.Response(200, json={'items': []}))
    monkeypatch.setattr(ghost_routes, 'call_room', room)
    receipt = AsyncMock(return_value=uuid.UUID(B))
    monkeypatch.setattr(trigger_routes, 'code_receipt', receipt)
    app = FastAPI()
    app.include_router(ghost_routes.router)
    headers = {'X-Tank-Key': 'placeholder-workspace-key', 'X-Tervory-Admin': actor.user_id}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        assert (await client.get('/v1/ghost/autumbra/fixes')).status_code == 404
        assert (await client.get('/v1/ghost/autumbra/fixes', headers=headers)).json()['cost_usd'] == 0
        room.reset_mock()
        body = {'match_id': B}
        assert (await client.post('/v1/ghost/autumbra/fix/approve', headers=headers, json=body)).status_code == 409
        assert not room.called
        token = CONFIRMED.set((actor.tenant_id, actor.user_id, uuid.UUID(B), 'autumbra.fix.approve', body))
        try:
            assert (await client.post('/v1/ghost/autumbra/fix/approve', headers=headers, json=body)).status_code == 200
        finally:
            CONFIRMED.reset(token)
        member = command.Actor(uuid.UUID(A), 'placeholder-member', False, tenant_admin=True)
        monkeypatch.setattr(command, 'identity', AsyncMock(return_value=member))
        assert (await client.post('/v1/ghost/autumbra/fix/approve', headers=headers, json=body)).status_code == 403
