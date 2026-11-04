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
