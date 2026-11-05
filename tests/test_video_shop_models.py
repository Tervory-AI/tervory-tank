"""Local asset integrity and inference failure boundaries."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.video_shop.prepare_models import verify
from agents.video_shop.video_models import LocalModels, ModelsUnavailable


def test_missing_weights_fail_closed_without_loading_engines(tmp_path):
    with pytest.raises(ModelsUnavailable):
        LocalModels(tmp_path)._load()


def test_modified_weight_is_rejected_before_inference(tmp_path):
    manifest = json.loads((ROOT / 'agents/video_shop/models.json').read_text())
    for name in manifest:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'modified model')
    with pytest.raises(ValueError, match='local_model_checksum'):
        verify(tmp_path)


@pytest.mark.asyncio
async def test_real_embeddings_reject_unrelated_image_and_silent_video_has_no_transcript(tmp_path):
    import os
    from types import SimpleNamespace
    sys.path.insert(0, str(ROOT / 'agents/rig'))
    from agents.video_shop.video_engine import Engine, Repository
    from rigbox.store import MemoryStore
    from video_shop_support import cpu_models
    root = os.environ.get('VIDEO_SHOP_TEST_MODELS')
    if not root:
        pytest.skip('CPU weights staged in dedicated offline test')
    store = MemoryStore()
    for sku, name in [('cup', 'Red cup'), ('unrelated', 'Black poster')]:
        await store.upsert_product('local-test', {'sku': sku, 'name': name, 'active': True})
    fixtures = ROOT / 'tests/fixtures/video_shop'
    engine = Engine(SimpleNamespace(store=store), Repository(tmp_path), models=cpu_models(root))
    draft = await engine.ingest('local-test', (fixtures / 'sample.mp4').read_bytes(), references={
        'cup': (fixtures / 'cup.ppm').read_bytes(),
        'unrelated': b'P6\n32 32\n255\n' + bytes(32 * 32 * 3)})
    assert draft['transcript'] == []
    assert draft['receipt']['audio'] is False
    assert draft['receipt']['model_calls'] == 1
    assert [moment['product_id'] for moment in draft['moments']] == ['cup', 'cup']
    assert all('transcript' not in moment['evidence'] for moment in draft['moments'])
