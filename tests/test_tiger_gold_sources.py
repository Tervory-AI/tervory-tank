"""Candidate provenance, exclusion, image payloads and room authentication."""
import importlib.util
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/tiger"))
sys.path.insert(0, str(ROOT / "agents/_chassis"))
_spec = importlib.util.spec_from_file_location('tiger_gold_sources', ROOT / 'agents/tiger/gold_sources.py')
gold = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gold)


def test_corpus_and_candidates():
    with ZipFile(gold.CORPUS) as archive:
        rows = json.loads(archive.read("manifest.json"))
    assert len(rows) == 109
    output = gold.candidates()
    eligible = [r for r in rows if r['split'] == 'build' and not r['conflict'] and not r['unreadable']]
    assert len(output) == len(eligible) * 2
    assert {r['skill_id'] for r in output} == {'tiger.price_extract', 'tiger.price_ocr'}
    for row in output:
        assert set(row) == {'skill_id', 'input', 'expected', 'label_source', 'region', 'public'}
        assert row['public'] is True and row['region'] == 'us-east'
        assert row['label_source'].startswith('auto:')
        if row['skill_id'].endswith('ocr'):
            import base64
            assert base64.b64decode(row['input']['png_base64']).startswith(b'\x89PNG')
            assert 'text' not in row['input']
    assert gold.candidates(1) == output[:1]
    assert gold.candidates(region='za') == []
    assert gold.candidates(region='invalid') == []
    assert gold.candidates(0) == []


@pytest.mark.parametrize('html,want', [
    ('<h1>Item</h1><p>$9.00</p><script type="application/ld+json">{"@type":"Product","offers":{"price":"9.00"}}</script>', '9.00'),
    ('<p>$9.00</p><meta itemprop="price" content="9">', '9.00'),
    ('<p>$8.00</p><meta itemprop="price" content="9">', None),
    ('<p hidden>$9.00</p><meta itemprop="price" content="9">', None),
    ('<p>$9.00 $8.00</p><meta itemprop="price" content="9">', None),
    ('<script type="application/ld+json">broken</script>', None),
])
def test_independent_agreement(html, want):
    assert gold.agreement(html) == want


@pytest.mark.asyncio
async def test_room_auth_and_limit(monkeypatch):
    monkeypatch.setitem(sys.modules, "gold_sources", gold)
    spec = importlib.util.spec_from_file_location('tiger_gold_app', ROOT / 'agents/tiger/app.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv('TANK_KEY', 'test-room-key')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mod.app), base_url='http://test') as client:
        for headers in ({}, {'X-Tank-Key': 'other-room-key'}, {'X-Tank-Key': 'workspace-key'}):
            assert (await client.get('/gold/candidates', headers=headers)).status_code == 401
        headers = {'X-Tank-Key': 'test-room-key'}
        response = await client.get('/gold/candidates?limit=2', headers=headers)
        assert response.status_code == 200 and len(response.json()) == 2
        for limit in ('0', '-1', '201', 'no'):
            assert (await client.get('/gold/candidates?limit=' + limit, headers=headers)).status_code == 422
        monkeypatch.setenv('TANK_REGION', 'za')
        assert (await client.get('/gold/candidates', headers=headers)).json() == []
        monkeypatch.delenv('TANK_KEY')
        assert (await client.get('/gold/candidates', headers=headers)).status_code == 401


def test_additional_public_snapshots_fail_closed(tmp_path):
    row = dict(public=True, robots_allowed=True, terms_allowed=True, challenge=False,
               authenticated=False, region='us-east', url='https://example.test/item',
               html='<p>$9.00</p><meta itemprop="price" content="9">')
    assert len(gold.snapshot_candidates([row], region='us-east')) == 1
    for key, value in [('public', False), ('robots_allowed', False), ('terms_allowed', False),
                       ('challenge', True), ('authenticated', True), ('region', 'za'),
                       ('url', 'https://example.test/item?session=private'), ('html', '<p>$8.00</p>')]:
        assert gold.snapshot_candidates([{**row, key: value}], region='us-east') == []
    path = tmp_path / 'snapshots.json'
    path.write_text(json.dumps([row]))
    result = gold.candidates(1, snapshots=path)
    assert len(result) == 1 and result[0]['label_source'] == 'auto:visible-structured-agreement'
    path.write_text('{bad')
    assert gold.candidates(1, snapshots=path) == gold.candidates(1)


def test_microdata_text_and_currency_disagreement():
    assert gold.agreement('<p itemprop="price">$9.00</p>') == '9.00'
    assert gold.agreement('<p>£9.00</p><meta itemprop="price" content="9"><meta itemprop="priceCurrency" content="USD">') is None


def test_image_ships_corpus_and_region():
    dockerfile = (ROOT / 'agents/tiger/Dockerfile').read_text()
    assert 'COPY tiger/gold_sources.py /app/gold_sources.py' in dockerfile
    assert 'COPY tiger/gold /app/gold' in dockerfile
    assert 'TANK_REGION: ${TANK_REGION:-us-east}' in (ROOT / 'agents/tiger/docker-compose.yml').read_text()
