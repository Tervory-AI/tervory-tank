"""The deployed terminal boots from defaults and saves only with admin authority."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
import httpx
import pytest

from rigbox.api import mount
from rigbox.service import RigError
from rigbox.three_d import page

TENANT = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
KEY = 'rk_pub_offline_page'


@pytest.fixture
def application(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.delenv('RIG_ROOM_TENANT', raising=False)
    app = FastAPI(); mount(app); app.include_router(page.router)
    async def admin(key):
        if key != 'rk_admin_offline':
            raise RigError('unauthorized', 'Administrator authorization is required.', 401)
        return {'tenant_id': TENANT}
    async def authenticate(key):
        if key not in {KEY, 'rk_pub_foreign'}:
            raise RigError('unauthorized', 'That key is not valid.', 401)
        return {'tenant_id': TENANT if key == KEY else OTHER}
    app.state.rig = SimpleNamespace(authenticate_admin=AsyncMock(side_effect=admin),
        authenticate=AsyncMock(side_effect=authenticate), product=AsyncMock())
    return app


@pytest.mark.asyncio
async def test_no_file_serves_empty_defaults_without_auth_or_writes(application):
    del application.state.rig
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://offline') as client:
        result = await client.get('/3d/config')
    assert result.status_code == 200 and result.headers['cache-control'] == 'no-store'
    assert result.json() == {'configured': False, 'publishable_key': '', 'photo_key': '',
                             'product_id': '', 'kiosk_id': None}
    assert not page.filename().exists()


@pytest.mark.asyncio
async def test_first_admin_save_creates_settings_checks_tenant_and_survives_reload(application):
    data = {'publishable_key': KEY}
    url = '/v1/rig/admin/3d/page'
    headers = {'X-Rig-Key': 'rk_admin_offline'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://offline') as client:
        for rejected in ({}, {'X-Rig-Key': KEY}):
            assert (await client.post(url, json=data, headers=rejected)).status_code == 401
        assert not page.filename().exists()
        assert (await client.post(url, json={'publishable_key': 'rk_pub_foreign'}, headers=headers)).status_code == 403
        assert (await client.post(url, json={'publishable_key': 'rk_admin_offline'}, headers=headers)).status_code == 422
        assert not page.filename().exists()
        saved = await client.post(url, json=data, headers=headers)
        assert saved.status_code == 200 and saved.json()['configured']
        assert page.filename().stat().st_mode & 0o777 == 0o600
        assert json.loads(page.filename().read_text())['tenant_id'] == TENANT
        assert (await client.get('/3d/config')).json() == saved.json()
        assert 'tenant_id' not in saved.json()
        before = page.filename().read_bytes()
        with pytest.raises(RigError) as failure:
            await page.save(application.state.rig, OTHER, page.PageConfig())
        assert failure.value.status == 403 and page.filename().read_bytes() == before
        page.initialize(OTHER)  # Ordinary settings never replace an existing display.
        assert page.filename().read_bytes() == before
        # A saved owner can replace a subsequently revoked publishable key.
        application.state.rig.authenticate.side_effect = RigError('unauthorized', 'That key is not valid.', 401)
        assert (await client.get('/3d/config')).status_code == 401
        reset = await client.post(url, json={}, headers=headers)
        assert reset.status_code == 200 and reset.json()['configured'] is False
        assert (await client.get('/3d/config')).status_code == 200


@pytest.mark.asyncio
async def test_existing_retailer_settings_create_day_zero_file_only_after_authenticated_save(tmp_path, monkeypatch):
    from test_rig_feeds_retailer import prepared
    from rigbox.retailer_server import create_retailer_app
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('RIG_RETAILER_KEY', 'placeholder-offline-retailer')
    monkeypatch.delenv('RIG_ROOM_TENANT', raising=False)
    retailer = await prepared()
    app = create_retailer_app(retailer.service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        body = {'tenant_id': TENANT, 'data': {'name': 'Offline shop', 'email': 'offline@example.invalid'}}
        assert (await client.post('/internal/retailer/settings', json=body)).status_code == 401
        assert not page.filename().exists()
        result = await client.post('/internal/retailer/settings', json=body,
                                   headers={'X-Rig-Retailer-Key': 'placeholder-offline-retailer'})
        assert result.status_code == 200
    assert page.filename().exists() and page.load().tenant_id is not None
    assert page.public(page.load())['configured'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_file', ['symlink', 'invalid', 'oversized'])
async def test_existing_invalid_settings_fail_closed_without_overwrite(application, tmp_path, bad_file):
    target = tmp_path / 'unchanged'; target.write_text('private')
    if bad_file == 'symlink': page.filename().symlink_to(target)
    else: page.filename().write_text('x' * (20_000 if bad_file == 'oversized' else 1))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://offline') as client:
        assert (await client.get('/3d/config')).status_code == 503
        assert (await client.post('/v1/rig/admin/3d/page', json={},
            headers={'X-Rig-Key': 'rk_admin_offline'})).status_code == 503
    assert target.read_text() == 'private' and not list(tmp_path.glob('.rig-3d-*'))
