"""Gold is authenticated, offline, region-bound fixture truth, never live data."""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents' / 'radix'))
# Other rooms have their own gold_sources; another test in this worker may have
# cached one, so import Radix's fresh and put the cached copy back.
_cached_gold = sys.modules.pop('gold_sources', None)
import gold_sources as gold  # noqa: E402
if _cached_gold is not None:
    sys.modules['gold_sources'] = _cached_gold
from test_radix_business import ENGINE  # noqa: E402
from scanlib import dependencies, static  # noqa: E402
from scanlib import secrets as scanner_secrets  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('RADIX_USE_SYSTEM_TOOLS', '0')
    with patch('socket.create_connection', side_effect=AssertionError('network forbidden')), \
         patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')), \
         patch('subprocess.run', side_effect=AssertionError('subprocess forbidden')):
        yield


def test_frozen_answers_match_skills_and_independent_business_truth():
    rows = gold.candidates()
    assert len(rows) == 13
    assert {r['skill_id'] for r in rows} == set(gold.SKILLS)
    scanners = {'scan.secrets': scanner_secrets, 'scan.dependencies': dependencies, 'scan.static': static}
    for row in rows:
        assert set(row) == {'skill_id', 'input', 'expected', 'label_source', 'label_family', 'region', 'public'}
        assert row['public'] is True and row['region'] == 'us-east'
        assert row['label_source'].startswith('radix:fixture:v1:')
        assert row['label_family'] == f"radix:fixture:v1:{row['skill_id']}"
        if row['skill_id'] in scanners:
            actual = scanners[row['skill_id']].run_skill(row['input'])
        else:
            actual = ENGINE.analyse(row['skill_id'].removeprefix('radix.'), row['input'], row['input']['tenant_id'])
        assert {key: actual[key] for key in row['expected']} == row['expected']
    answers = {r['skill_id']: r['expected'] for r in rows if r['skill_id'].startswith('radix.')}
    assert answers['radix.verify_business']['verification'] == 'verified_from_supplied_register'
    assert {'registered_address', 'registered_agent'} <= set(answers['radix.entity_links']['links'][0]['shared_fields'])
    assert answers['radix.account_links']['links'][0]['possible_returning_operation'] is True
    assert {f['code'] for f in answers['radix.site_risk']['findings']} == {'privacy_notice', 'cookie_notice', 'exposed_admin', 'new_domain', 'lookalike_domain'}
    assert answers['radix.business_risk']['score'] == 95
    assert all(f['sources'] for f in answers['radix.business_risk']['factors'])


def test_limits_determinism_and_no_mutation():
    rows = gold.candidates()
    assert len({r['label_source'] for r in rows}) == len(rows)
    for limit in (1, 8, 13, 200):
        assert gold.candidates(limit) == rows[:limit]
    rows[0]['input'].clear()
    assert gold.candidates()[0]['input']
    for limit in (0, -1, 201):
        with pytest.raises(ValueError):
            gold.candidates(limit)


def test_region_is_not_relabelled(monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'za')
    rows = gold.candidates()
    assert len(rows) == 8
    assert all(r['region'] == 'za' and r['skill_id'].startswith('scan.') for r in rows)
    monkeypatch.setenv('TANK_REGION', 'unknown')
    with pytest.raises(ValueError):
        gold.candidates()


def test_secret_marker_only_in_generated_input_not_labels_files_or_logs(capsys):
    marker = '-'.join(('tvfy', 'example', 'fixture', 'key', '0001'))
    rows = gold.candidates()
    assert marker in json.dumps(rows[0]['input'])
    assert marker not in json.dumps([r['expected'] for r in rows])
    for path in gold.FIXTURES.iterdir():
        assert marker not in path.read_text()
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err


@pytest.mark.asyncio
async def test_room_key_only_limits_and_no_services(monkeypatch):
    key = secrets.token_hex(24)
    monkeypatch.setenv('TANK_KEY', key)
    app = FastAPI()  # No pool, Tank, memory or filesystem client configured.
    gold.attach(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://room') as client:
        for headers in ({}, {'X-Tank-Key': secrets.token_hex(24)}, {'Authorization': f'Bearer {key}'}):
            assert (await client.get('/gold/candidates', headers=headers)).status_code == 401
        headers = {'X-Tank-Key': key}
        response = await client.get('/gold/candidates?limit=1', headers=headers)
        assert response.status_code == 200 and response.json() == gold.candidates(1)
        assert len((await client.get('/gold/candidates', headers=headers)).json()) == 13
        for limit in ('0', '-1', '201', 'abc', '1.5'):
            assert (await client.get('/gold/candidates', params={'limit': limit}, headers=headers)).status_code == 422
        monkeypatch.setenv('TANK_REGION', 'unknown')
        assert (await client.get('/gold/candidates', headers=headers)).status_code == 503
        monkeypatch.setenv('TANK_KEY', '')
        assert (await client.get('/gold/candidates', headers=headers)).status_code == 401


def test_image_packages_route_and_fixtures():
    dockerfile = (ROOT / 'agents/radix/Dockerfile').read_text()
    assert 'COPY radix/gold_sources.py /app/gold_sources.py' in dockerfile
    assert 'COPY radix/evals/gold /app/evals/gold' in dockerfile
    from test_rx1_scans import _load_app
    from http_routes import http_paths
    assert '/gold/candidates' in http_paths(_load_app().app.routes)
