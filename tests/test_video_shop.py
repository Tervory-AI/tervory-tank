"""Offline video-shop processing, approval and tenant isolation."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'agents/rig'))
from agents.video_shop.video_engine import Engine, Repository, command
from rigbox.store import MemoryStore

TENANT = '20000000-0000-0000-0000-000000000001'
OTHER = '20000000-0000-0000-0000-000000000002'


@pytest.mark.asyncio
async def test_video_review_and_isolation(tmp_path):
    store = MemoryStore()
    await store.upsert_product(TENANT, {'sku': 'red', 'name': 'Red cup', 'active': True,
                                       'price': '10', 'currency': 'USD', 'attributes': {}})
    await store.upsert_product(OTHER, {'sku': 'private', 'name': 'Red cup', 'active': True})
    video = tmp_path / 'sample.mp4'
    await command('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=10',
                  '-pix_fmt', 'yuv420p', str(video))
    image = b'P6\n32 32\n255\n' + bytes([253, 0, 0]) * 1024
    engine = Engine(SimpleNamespace(store=store), Repository(tmp_path / 'data'))
    draft = await engine.ingest(TENANT, video.read_bytes(), [], {'red': image})
    assert draft['moments'] and all(m['product_id'] == 'red' for m in draft['moments'])
    assert draft['moments'][0]['evidence']['vision_score'] >= .96
    assert draft['receipt']['model_calls'] == 0
    assert not any(m['approved'] for m in draft['moments'])
    with pytest.raises(KeyError):
        engine.repository.get(OTHER, draft['id'])
    reviewed = await engine.review(TENANT, draft['id'], 1,
                                  [{**draft['moments'][0], 'approved': True}])
    assert reviewed['revision'] == 2
    with pytest.raises(ValueError, match='review_conflict'):
        await engine.review(TENANT, draft['id'], 1, [])
    with pytest.raises(ValueError, match='product'):
        await engine.review(TENANT, draft['id'], 2,
                            [{'start': 0, 'end': 5, 'product_id': 'private', 'approved': True}])
    assert Repository(tmp_path / 'data').get(TENANT, draft['id']) == reviewed


@pytest.mark.asyncio
async def test_catalogue_images_are_reused_without_reference_upload(tmp_path, monkeypatch):
    from agents.video_shop import video_media
    fixture = ROOT / 'tests/fixtures/video_shop'
    calls = []

    def fetch(url, limit):
        calls.append(url)
        assert limit == 2 * 1024 * 1024
        return (fixture / 'cup.ppm').read_bytes()

    monkeypatch.setattr(video_media, 'download', fetch)
    store = MemoryStore()
    await store.upsert_product(TENANT, {'sku': 'cup', 'name': 'Red cup', 'active': True,
        'image_url': 'https://store.example/cup.ppm', 'price': '10', 'currency': 'USD'})
    engine = Engine(SimpleNamespace(store=store), Repository(tmp_path / 'data'))
    result = await engine.ingest(TENANT, (fixture / 'sample.mp4').read_bytes(), [], {})
    assert calls == ['https://store.example/cup.ppm']
    assert result['receipt']['reference_images'] == 1
    assert len(result['moments']) == 2
    assert all(m['product_id'] == 'cup' for m in result['moments'])


@pytest.mark.parametrize('url', ['http://store.example/video.mp4', 'https://user:pass@store.example/a',
                               'https://store.example:444/a'])
def test_link_rejects_unsafe_schemes_credentials_and_ports(url):
    from agents.video_shop.video_media import download
    with pytest.raises(ValueError):
        download(url)


def test_link_rejects_private_addresses_before_connect(monkeypatch):
    from agents.video_shop import video_media
    monkeypatch.setattr(video_media.socket, 'getaddrinfo', lambda *a, **k:
                        [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='url_address'):
        video_media.download('https://store.example/video.mp4')


@pytest.mark.asyncio
async def test_bad_media_does_not_leave_a_published_file(tmp_path):
    engine = Engine(SimpleNamespace(store=MemoryStore()), Repository(tmp_path))
    with pytest.raises(ValueError, match='media_decode'):
        await engine.ingest(TENANT, b'not video', [], {})
    assert not list(tmp_path.rglob('*.mp4'))
