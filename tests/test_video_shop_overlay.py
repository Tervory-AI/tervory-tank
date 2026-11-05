"""Public overlay boundaries use real Rig key and origin authentication."""
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'agents/rig'))
from agents.video_shop.video_room import mount
from rigbox.api import mount as mount_rig
from rigbox.service import Service, hash_key
from rigbox.store import MemoryStore

TENANT = '20000000-0000-0000-0000-000000000001'
OTHER = '20000000-0000-0000-0000-000000000002'
KEY = 'rk_pub_offline_video_shop'


@pytest.mark.asyncio
async def test_only_reviewed_current_tenant_products_are_exposed(tmp_path):
    store = MemoryStore()
    await store.put_key(TENANT, hash_key(KEY), 'publishable', ['https://store.example'])
    await store.put_key(OTHER, hash_key(KEY + '_other'), 'publishable', ['https://store.example'])
    await store.upsert_product(TENANT, {'sku': 'cup', 'name': 'Cup', 'price': '10', 'currency': 'USD',
        'active': True, 'attributes': {'unit_cost': 'secret', 'colour': 'red'}})
    app = FastAPI()
    app.state.rig = Service(store)
    mount_rig(app)
    mount(app, tmp_path)
    from agents.video_shop.video_engine import Engine, Repository
    app.state.video_shop = Engine(app.state.rig, Repository(tmp_path))
    body = {'id': 'a' * 32, 'revision': 1, 'status': 'draft', 'receipt': {'private': 'evidence'},
            'moments': [{'start': 0, 'end': 5, 'approved': True, 'product_id': 'cup'},
                        {'start': 5, 'end': 10, 'approved': False, 'product_id': 'cup'}]}
    repo = app.state.video_shop.repository
    repo.save(TENANT, body)
    route = '/v1/rig/video-shop/videos/' + body['id']
    headers = {'X-Rig-Key': KEY, 'Origin': 'https://store.example'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='https://rig.example') as api:
        assert (await api.get(route, headers=headers)).status_code == 404
        body.update(status='reviewed', revision=2)
        repo.save(TENANT, body, expected=1)
        response = await api.get(route, headers=headers)
        assert response.status_code == 200
        assert len(response.json()['moments']) == 1
        assert 'unit_cost' not in response.text and 'receipt' not in response.text
        assert response.headers['access-control-allow-origin'] == 'https://store.example'
        assert (await api.get(route, headers={**headers, 'Origin': 'https://evil.example'})).status_code == 403
        assert (await api.get(route, headers={**headers, 'X-Rig-Key': KEY + '_other'})).status_code == 404
        assert (await api.get(route)).status_code == 401
        assert (await api.get('/v1/rig/video-shop/admin/videos/' + body['id'], headers=headers)).status_code == 403
        await store.upsert_product(TENANT, {'sku': 'cup', 'name': 'Cup', 'active': False})
        assert (await api.get(route, headers=headers)).json()['moments'] == []
