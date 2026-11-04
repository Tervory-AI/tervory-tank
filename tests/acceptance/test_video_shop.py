"""Video -> reviewed moments -> Rig cart -> store-owned checkout, offline."""
import base64
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'agents/rig'))
from agents.video_shop.video_room import mount
from agents.video_shop.video_engine import Repository
from rigbox.api import mount as mount_rig
from rigbox.cart_api import mount as mount_cart
from rigbox.service import hash_key
from rigbox.catalogue import parse_products_csv
from test_rig_cart import TENANT, setup

FIXTURES = ROOT / 'tests/fixtures/video_shop'
PUBLIC = 'rk_pub_offline_video_acceptance'
ADMIN = 'offline-video-review-fixture'


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['upload', 'link'])
async def test_video_produces_timestamps_and_store_cart_line(tmp_path, monkeypatch, source):
    cart, store_platform, _, _, _, transport_client = await setup(monkeypatch)
    rig = cart.service
    rig.cart = cart
    catalogue = parse_products_csv((FIXTURES / 'catalogue.csv').read_text())
    assert not catalogue['rejected']
    for product in catalogue['rows']:
        await rig.store.upsert_product(TENANT, product)
    await rig.store.put_key(TENANT, hash_key(PUBLIC), 'publishable', ['https://store.example'])
    await rig.store.put_key(TENANT, hash_key(ADMIN), 'admin', [])
    app = FastAPI()
    app.state.rig = rig
    mount_rig(app)
    mount_cart(app)
    mount(app, tmp_path / 'durable')
    admin = {'X-Rig-Key': ADMIN}
    shopper = {'X-Rig-Key': PUBLIC, 'Origin': 'https://store.example'}
    prefix = '/v1/rig/video-shop'
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='https://rig.example') as api:
            from agents.video_shop import video_routes
            if source == 'link':
                monkeypatch.setattr(video_routes, 'download', lambda url: (FIXTURES / 'sample.mp4').read_bytes())
                source_data = {'url': 'https://store.example/sample.mp4'}
            else:
                source_data = {'video_base64': base64.b64encode((FIXTURES / 'sample.mp4').read_bytes()).decode()}
            created = await api.post(prefix + '/admin/videos', headers=admin, json={
                **source_data,
                'references': {'stock': base64.b64encode((FIXTURES / 'cup.ppm').read_bytes()).decode()},
                'transcript': [{'start': 0, 'end': 5, 'text': 'Red cup'}]})
            assert created.status_code == 200, created.text
            draft = created.json()
            assert draft['receipt']['model_calls'] == 0
            assert [m['start'] for m in draft['moments']] == [0, 5]
            assert draft['moments'][0]['evidence']['transcript']
            assert draft['moments'][0]['evidence']['vision_score'] >= .96
            identifier = draft['id']
            assert (await api.get(prefix + '/admin/videos', headers=admin)).json()['videos'][0]['id'] == identifier
            preview = await api.get(prefix + '/admin/videos/' + identifier + '/media', headers=admin)
            assert preview.status_code == 200 and preview.content == (FIXTURES / 'sample.mp4').read_bytes()
            public_route = prefix + '/videos/' + identifier
            assert (await api.get(public_route, headers=shopper)).status_code == 404
            edited = [{'start': 1, 'end': 7, 'product_id': 'stock', 'approved': True}]
            reviewed = await api.put(prefix + '/admin/videos/' + identifier, headers=admin,
                                     json={'revision': 1, 'moments': edited})
            assert reviewed.status_code == 200, reviewed.text
            assert Repository(tmp_path / 'durable').get(TENANT, identifier)['moments'] == edited
            timeline = (await api.get(public_route, headers=shopper)).json()
            assert timeline['moments'] == edited and set(timeline['products']) == {'stock'}
            media = await api.get(public_route + '/media', headers=shopper)
            assert media.status_code == 200 and media.content == (FIXTURES / 'sample.mp4').read_bytes()
            session = (await api.post('/v1/rig/cart/session', headers=shopper, json={})).json()['session']
            added = await api.post('/v1/rig/cart/add', headers=shopper,
                                   json={'session': session, 'product_id': 'stock', 'quantity': 1})
            assert added.status_code == 200, added.text
            assert added.json()['lines'][0]['product_id'] == 'stock'
            checkout = await api.post('/v1/rig/cart/checkout', headers=shopper, json={'session': session})
            assert checkout.status_code == 200, checkout.text
            assert checkout.json()['checkout_url'].startswith('https://store.example/')
            line = store_platform.orders['1']['line_items'][0]
            assert line['product_id'] == 1 and line['quantity'] == 1 and line['total'] == '10.00'
    finally:
        await transport_client.aclose()
